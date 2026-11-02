"""Camera-free regression checks for the incremental gesture replacement."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from gesture_features import FeatureConfig
from gesture_model import GestureNetwork, MLGestureClassifier
from gestures import ClickTracker, Gesture, GestureClassifier, is_index_thumb
from research.dataset import append_rows, read_rows
from research.migrate_gestures import main as migrate, partition_rows
from research.recorder import PROTOCOL_PATH, RecorderApi, build_plan, select_gestures


def pose(click=True):
    points = np.zeros((21, 3))
    points[1:5, :2] = [(-.3, .4), (-.65, .6), (-.95, .65), (-1.25, .7)]
    points[5:9, :2] = [(-.4, 1), (-.4, 1.5), (-.4, 1.8), (-.4, 2)]
    for start, x, y in [(9, 0, 1), (13, .3, .9), (17, .6, .8)]:
        points[start:start+4, :2] = [(x, y), (x, y+.4), (x, y-.1), (x, y-.3)]
    if not click:
        points[2:5, :2] = [(-.4, .4), (-.2, .6), (-.35, .9)]
    return points


def landmarks(points):
    return [SimpleNamespace(x=x, y=y, z=z) for x, y, z in points]


def row(label, trial, click=False, session="S01", participant="P001"):
    from research.selftest import _rows
    sample = _rows(session, np.random.default_rng(0))[0]
    sample.update(gesture=label, trial_id=trial, participant_id=participant,
                  frame_width=100, frame_height=100)
    for i, (x, y, z) in enumerate(pose(click)):
        sample.update({f"x{i}": x, f"y{i}": y, f"z{i}": z})
    return sample


class GestureChangeTests(unittest.TestCase):
    def test_geometry_and_invariance(self):
        classifier = GestureClassifier()
        self.assertEqual(classifier.classify(landmarks(pose(False)))[0], Gesture.POINT)
        for angle in (0, .5, 1.5, 3):
            rotation = np.array([[np.cos(angle), -np.sin(angle)],
                                 [np.sin(angle), np.cos(angle)]])
            for mirror in (1, -1):
                points = pose()
                points[:, 0] *= mirror
                points[:, :2] = points[:, :2] @ rotation * .13 + .5
                self.assertTrue(is_index_thumb(landmarks(points)))
                self.assertEqual(classifier.classify(landmarks(points))[0], Gesture.INDEX_THUMB)
        for tip in (8, 12):
            points = pose(False)
            points[4] = points[tip]
            self.assertFalse(is_index_thumb(landmarks(points)))

    def test_click_debounce_release_and_cancel(self):
        tracker = ClickTracker()
        self.assertEqual(tracker.update(True), [])
        self.assertEqual(tracker.update(False), [])  # one-frame noise
        for _ in range(30):
            self.assertEqual(tracker.update(True), [])  # held pose never repeats
        self.assertEqual(tracker.update(False), [])
        self.assertEqual(tracker.update(False), [("click",)])
        self.assertEqual(tracker.update(False), [])
        tracker.update(True)
        tracker.update(True)
        tracker.reset()  # loss of either clicking hand cancels
        self.assertEqual(tracker.update(False) + tracker.update(False), [])

    def test_runtime_legacy_and_trained_models(self):
        labels = [g.value for g in Gesture if g != Gesture.INDEX_THUMB] + ["pinch", "pinch_right"]
        def classifier(prediction, modern=False):
            names = labels + (["index_thumb"] if modern else [])
            probs = np.array([float(g == prediction) for g in names])
            network = SimpleNamespace(
                labels=names, gestures=[GestureNetwork._to_gesture(g) for g in names],
                none_index=names.index("none"), needs_pointer_retraining=not modern,
                feature_config=FeatureConfig(world=False), probabilities=lambda _: probs,
            )
            return MLGestureClassifier(network)
        for retired in ("pinch", "pinch_right"):
            self.assertEqual(classifier(retired).classify(landmarks(pose(False)))[0], Gesture.NONE)
        self.assertEqual(classifier("point").classify(landmarks(pose()))[0], Gesture.NONE)
        self.assertEqual(classifier("point").classify(landmarks(pose(False)))[0], Gesture.NONE)
        for gesture in Gesture:
            if gesture not in (Gesture.POINT, Gesture.INDEX_THUMB, Gesture.NONE):
                self.assertEqual(classifier(gesture.value).classify(landmarks(pose()))[0], gesture)
        result, payload = classifier("index_thumb", True).classify(landmarks(pose()))
        self.assertEqual(result, Gesture.INDEX_THUMB)
        self.assertEqual(payload["label"], "index_thumb")
        self.assertEqual(classifier("point", True).classify(landmarks(pose(False)))[0], Gesture.POINT)
        # Runtime corrects a widescreen camera and mirrors anatomical left hands.
        points = pose()
        points[:, 0] = 1 - points[:, 0] / (16/9)
        left = classifier("index_thumb", True)
        left.hand = "Left"
        self.assertEqual(left.classify(landmarks(points), aspect=16/9)[0], Gesture.INDEX_THUMB)

    def test_single_gesture_plan_and_unique_recording_ids(self):
        original = json.loads(PROTOCOL_PATH.read_text())
        selected = select_gestures(original, ["point", "index_thumb"])
        plan = build_plan(selected, 42)
        self.assertEqual(len(plan), 38)  # 32 right + 6 left
        self.assertEqual({t.gesture for t in plan}, {"point", "index_thumb"})
        self.assertEqual({t.gesture for t in plan if t.hand == "Left"}, {"index_thumb"})
        self.assertEqual(plan[0].block, "right:normal")
        self.assertEqual({t.condition for t in plan}, {c["id"] for c in original["conditions"]})
        self.assertEqual(selected["quality"], original["quality"])
        self.assertEqual(len(original["gestures"]), 10)
        with self.assertRaises(ValueError):
            select_gestures(original, ["pinch"])
        args = SimpleNamespace(output=Path("unused.csv"), seed=42)
        self.assertNotEqual(RecorderApi(args, selected).run_id, RecorderApi(args, selected).run_id)

    def test_migration_whole_trials_and_preserved_sources(self):
        samples = [row("pinch", "old1"), row("pinch_right", "old2"),
                   row("point", "overlap", True), row("point", "overlap", False),
                   row("point", "overlap", False, participant="P002"),
                   row("point", "overlap", False, session="S02"), row("fist", "keep")]
        kept, removed = partition_rows(samples)
        self.assertEqual(len(removed), 6)  # all legacy point and both pinch classes
        self.assertEqual(kept, samples[6:])  # every other row is unchanged
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"old.csv", Path(directory)/"new.csv"
            append_rows(source, samples)
            before = source.read_bytes()
            migrate([str(source), "--output", str(output)])
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(len(read_rows([output])), 1)
            migrated_bytes = output.read_bytes()
            with self.assertRaises(SystemExit):
                migrate([str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), migrated_bytes)
            self.assertEqual(partition_rows(kept)[0], kept)

    def test_training_keeps_only_fresh_point_examples(self):
        from research.train import prepare_training_rows
        with tempfile.TemporaryDirectory() as directory:
            old, fresh = Path(directory)/"old.csv", Path(directory)/"fresh.csv"
            append_rows(old, [row("point", "old-point"), row("pinch", "old-pinch"),
                             row("pinch_right", "old-right"), row("fist", "keep")])
            append_rows(fresh, [row("point", "new-point", session="G01"),
                               row("index_thumb", "new-click", True, session="G01")])
            prepared, removed = prepare_training_rows([old], [fresh])
            self.assertEqual(len(removed), 3)
            self.assertEqual({r["trial_id"] for r in prepared}, {"keep", "new-point", "new-click"})
            with self.assertRaisesRegex(SystemExit, "must be different"):
                prepare_training_rows([old], [old])

    def test_training_requires_new_recordings_before_export(self):
        from research.train import main as train
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"old.csv", Path(directory)/"model.npz"
            append_rows(source, [row("point", "keep")])
            with self.assertRaisesRegex(SystemExit, "Missing training gestures"):
                train([str(source), "--output", str(output)])
            self.assertFalse(output.exists())

    def test_pilot_split_keeps_whole_trials_and_training_coverage(self):
        from research.train import _split
        samples = [row(g, f"{g}-{trial}", session="G01")
                   for g in ("point", "index_thumb") for trial in range(3)
                   for _ in range(2)] + [row("fist", "old-test", session="S03")]
        train, test = _split(samples, {"S03"}, {"G01"})
        key = lambda r: (r["participant_id"], r["session_id"], r["trial_id"])
        self.assertFalse({key(r) for r in train} & {key(r) for r in test})
        self.assertEqual(len(train), 8)
        self.assertEqual(len(test), 5)
        self.assertEqual(_split(samples, {"S03"}, {"G01"}), (train, test))
        with self.assertRaisesRegex(SystemExit, "at least two"):
            _split([row("point", "only", session="G01")], set(), {"G01"})


if __name__ == "__main__":
    unittest.main()
