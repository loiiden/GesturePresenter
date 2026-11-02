import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from simple_mode import (PinchSequence, SimpleModeController, pinch_distance_ratio,
                         MAX_PINCH_DISTANCE_RATIO)
from config import AppConfig
from research.recorder import build_plan
import json
from pathlib import Path


def hand_with_gap(gap=0.1, scale=1.0, aspect=1.0):
    points = [SimpleNamespace(x=0.0, y=0.0, z=0.0) for _ in range(21)]
    points[9].y = scale
    points[8].x = gap * scale / aspect
    return points


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.tracker = PinchSequence()
        self.events = []

    def frame(self, closed, t):
        event = self.tracker.update(closed, t)
        if event:
            self.events.append(event)
        return event

    def stable(self, closed, t):
        self.frame(closed, t)
        self.frame(closed, t + .06)

    def test_release_emits_without_double_pinch_wait(self):
        self.stable(False, 0)
        self.stable(True, .1)
        self.frame(False, .2)
        self.assertEqual(self.events, [])
        self.assertEqual(self.frame(False, .246), 'release')
        self.assertIsNone(self.frame(False, .3))

    def test_two_quick_pinches_are_two_releases(self):
        self.stable(False, 0)
        for t in (.1, .3):
            self.stable(True, t)
            self.stable(False, t + .1)
        self.assertEqual(self.events, ['release', 'release'])

    def test_flicker_and_long_hold(self):
        self.stable(False, 0)
        self.frame(True, .1)
        self.stable(False, .12)
        self.assertEqual(self.events, [])
        self.stable(True, .3)
        self.frame(True, 5)
        self.assertEqual(self.events, [])
        self.stable(False, 5.1)
        self.frame(False, 6)
        self.assertEqual(self.events, ['release'])

    def test_tracking_loss_cancels_and_requires_open_hand(self):
        self.stable(False, 0)
        self.stable(True, .1)
        self.frame(None, .2)
        self.stable(True, .3)
        self.stable(False, .4)
        self.assertEqual(self.events, [])
        self.stable(True, .5)
        self.stable(False, .6)
        self.assertEqual(self.events, ['release'])


class IntegrationTests(unittest.TestCase):
    def test_training_uses_all_original_labels_as_binary_examples(self):
        from research.train_simple import select_rows
        labels = ['pinch', 'none', 'point', 'index_thumb', 'pinch_right',
                  'fist', 'open_palm', 'v_sign', 'two_finger_scroll',
                  'fist_thumb_up', 'fist_thumb_left', 'fist_thumb_right']
        rows = [dict(hand=hand, gesture=label)
                for hand in ['Right', 'Left'] for label in labels]
        original = [dict(r) for r in rows]
        self.assertEqual(select_rows(rows), [
            {'hand': 'Right', 'gesture': 'pinch' if label == 'pinch' else 'none'}
            for label in labels])
        self.assertEqual(rows, original)

    def test_fresh_pinches_replace_old_positives_without_mutating_sources(self):
        from research.train_simple import select_rows
        old = [dict(hand='Right', gesture=g, session_id='S01')
               for g in ['pinch', 'none', 'point', 'pinch_right']]
        fresh = [dict(hand='Right', gesture='pinch', session_id='PINCH_V2_01')]
        selected = select_rows(old, fresh)
        self.assertEqual([r for r in selected if r['gesture'] == 'pinch'], fresh)
        self.assertEqual(len([r for r in selected if r['gesture'] == 'none']), 3)
        self.assertEqual(old[0]['gesture'], 'pinch')
        self.assertEqual(old[2]['gesture'], 'point')
        for invalid in ([], [dict(fresh[0], gesture='none')],
                        [dict(fresh[0], session_id='S01')]):
            with self.assertRaises(ValueError):
                select_rows(old, invalid)

    def test_distance_limit_is_scale_and_aspect_independent(self):
        for scale in (.05, .2, 1):
            for aspect in (.75, 1, 16/9):
                self.assertAlmostEqual(pinch_distance_ratio(
                    hand_with_gap(.4, scale, aspect), aspect), .4)
        self.assertGreater(pinch_distance_ratio(hand_with_gap(scale=0)),
                           MAX_PINCH_DISTANCE_RATIO)

    def test_separated_fingers_release_despite_model_staying_pinch(self):
        controller = SimpleModeController()
        controller.classifier.classify = Mock(return_value=(None, {
            'label': 'pinch', 'probs': {'pinch': .99}}))
        controller.classifier.reset = Mock()
        apart = hand_with_gap(.5)
        closed = hand_with_gap(.1)
        # Geometry can arm the controller even if the model would say pinch.
        controller.update(apart, None, 1, 0)
        controller.update(apart, None, 1, .05)
        controller.classifier.classify.assert_not_called()
        controller.update(closed, None, 1, .1)
        controller.update(closed, None, 1, .16)
        self.assertTrue(controller.sequence.closed)
        controller.update(apart, None, 1, .2)
        self.assertEqual(controller.update(apart, None, 1, .26), 'next')
        self.assertFalse(controller.sequence.closed)
        self.assertIn('fingers apart', controller.status)
        self.assertIsNone(controller.update(apart, None, 1, .62))
        self.assertIsNone(controller.update(apart, None, 1, .9))
        controller.classifier.reset.assert_called()

    def test_two_right_pinches_advance_twice_with_sticky_model(self):
        controller = SimpleModeController()
        controller.classifier.classify = Mock(return_value=(None, {'label': 'pinch'}))
        events = []
        for gap, start in [(.5, 0), (.1, .1), (.5, .2), (.1, .4), (.5, .5)]:
            for t in (start, start + .06):
                event = controller.update(hand_with_gap(gap), None, 1, t)
                if event:
                    events.append(event)
        self.assertEqual(events, ['next', 'next'])
        self.assertIsNone(controller.update(hand_with_gap(.5), None, 1, 1))

    def test_left_release_goes_back_and_tracking_states_are_independent(self):
        right = SimpleModeController()
        left = SimpleModeController(hand='Left', network=right.classifier.network)
        self.assertIs(right.classifier.network, left.classifier.network)
        self.assertEqual(left.classifier.hand, 'Left')
        for controller in (right, left):
            controller.classifier.classify = Mock(return_value=(None, {'label': 'pinch'}))
            controller.update(hand_with_gap(.5), None, 1, 0)
            controller.update(hand_with_gap(.5), None, 1, .06)
            controller.update(hand_with_gap(.1), None, 1, .1)
            controller.update(hand_with_gap(.1), None, 1, .16)
        right.update(None, None, 1, .2)
        self.assertFalse(right.sequence.closed)
        self.assertTrue(left.sequence.closed)
        left.update(hand_with_gap(.5), None, 1, .2)
        self.assertEqual(left.update(hand_with_gap(.5), None, 1, .26), 'previous')

    def test_mirrored_left_input_has_same_model_probabilities(self):
        import numpy as np
        rng = np.random.default_rng(42)
        image = rng.uniform(.2, .8, (21, 3))
        world = rng.normal(0, .05, (21, 3))
        mirrored_image = image.copy()
        mirrored_image[:, 0] = 1 - mirrored_image[:, 0]
        mirrored_world = world.copy()
        mirrored_world[:, 0] *= -1
        def landmarks(points):
            return [SimpleNamespace(x=x, y=y, z=z) for x, y, z in points]
        right = SimpleModeController()
        left = SimpleModeController(hand='Left', network=right.classifier.network)
        _, rp = right.classifier.classify(landmarks(image), landmarks(world), 16/9)
        _, lp = left.classifier.classify(landmarks(mirrored_image), landmarks(mirrored_world), 16/9)
        np.testing.assert_allclose(list(rp['probs'].values()), list(lp['probs'].values()), atol=1e-6)

    def test_default_is_simple_mode(self):
        self.assertTrue(AppConfig().simple_mode)

    def test_packaged_model_and_controller_cancel_on_disabled(self):
        controller = SimpleModeController()
        self.assertEqual(controller.classifier.network.labels, ['none', 'pinch'])
        controller.classifier.classify = Mock(return_value=(None, {'label':'none'}))
        controller.update(hand_with_gap(), None, 1, 0)
        controller.update(hand_with_gap(), None, 1, .05)
        controller.classifier.classify.return_value = (None, {'label':'pinch'})
        controller.update(hand_with_gap(), None, 1, .1)
        controller.update(hand_with_gap(), None, 1, .15)
        controller.classifier.classify.return_value = (None, {'label':'none'})
        controller.update(hand_with_gap(), None, 1, .2)
        controller.update(hand_with_gap(), None, 1, .26)
        self.assertIsNone(controller.update(hand_with_gap(), None, 1, .7, enabled=False))
        self.assertFalse(controller.sequence.armed)

    def test_simple_runtime_emits_only_slide_actions_with_both_hands_visible(self):
        from contextlib import ExitStack
        from types import SimpleNamespace
        from unittest.mock import patch
        import queue
        import numpy as np
        import hand_tracker as tracker

        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        camera = Mock()
        camera.isOpened.return_value = True
        camera.read.side_effect = [(True, frame)] * 3 + [(False, None)]
        result = SimpleNamespace(
            hand_landmarks=[[SimpleNamespace(x=.5, y=.5, z=0)] * 21] * 2,
            hand_world_landmarks=[None, None],
            handedness=[[SimpleNamespace(category_name='Left')],
                        [SimpleNamespace(category_name='Right')]])
        detector = Mock()
        detector.detect_for_video.return_value = result
        context = Mock()
        context.__enter__ = Mock(return_value=detector)
        context.__exit__ = Mock(return_value=False)
        controller = Mock()
        controller.sequence.closed = False
        controller.sequence.armed = True
        controller.status = 'Right: ready'
        controller.update.side_effect = ['next', None, 'next']
        left_controller = Mock()
        left_controller.status = 'Left: ready'
        left_controller.sequence.closed = False
        left_controller.sequence.armed = True
        left_controller.update.side_effect = [None, 'previous', 'previous']
        with ExitStack() as stack:
            action_mock = stack.enter_context(patch.object(tracker, 'actions'))
            stack.enter_context(patch('simple_mode.SimpleModeController', side_effect=[controller, left_controller]))
            stack.enter_context(patch.object(tracker.gesture_model, 'load_classifiers',
                                            side_effect=AssertionError('full model loaded')))
            stack.enter_context(patch.object(tracker, 'get_display_rect', return_value=(0, 0, 100, 100)))
            stack.enter_context(patch.object(tracker.cv2, 'VideoCapture', return_value=camera))
            stack.enter_context(patch.object(tracker.cv2, 'imencode', return_value=(False, None)))
            stack.enter_context(patch.object(tracker.vision.HandLandmarker, 'create_from_options', return_value=context))
            for name in ('draw_hand', 'draw_hud', 'draw_speech_overlay'):
                stack.enter_context(patch.object(tracker, name))
            # A saved voice preference must not load speech in simple mode.
            stack.enter_context(patch.dict('sys.modules', {'speech': None}))
            tracker.run(AppConfig(simple_mode=True, voice_enabled=True), ui_queue=queue.Queue())
            self.assertEqual([call[0] for call in action_mock.mock_calls],
                             ['next_slide', 'previous_slide'])
        camera.release.assert_called_once()

    def test_status_distinguishes_missing_hand_and_pinch_detection(self):
        controller = SimpleModeController()
        controller.update(None, None, 1, 0)
        self.assertIn('Right: show your hand', controller.status)
        controller.classifier.classify = Mock(return_value=(None, {
            'label': 'none', 'probs': {'pinch': .03}}))
        controller.update(hand_with_gap(), None, 1, .1)
        controller.update(hand_with_gap(), None, 1, .16)
        self.assertIn('Ready', controller.status)
        controller.classifier.classify.return_value = (None, {
            'label': 'pinch', 'probs': {'pinch': .95}})
        controller.update(hand_with_gap(), None, 1, .2)
        controller.update(hand_with_gap(), None, 1, .26)
        self.assertIn('Pinch detected', controller.status)
        self.assertIn('95%', controller.status)

    def test_focused_recorder_protocol(self):
        protocol = json.loads(Path('research/protocol_simple.json').read_text())
        plan = build_plan(protocol, 42)
        self.assertEqual(len(plan), 16)
        self.assertEqual({t.gesture for t in plan}, {'pinch'})
        self.assertEqual({t.hand for t in plan}, {'Right'})


if __name__ == '__main__':
    unittest.main()
