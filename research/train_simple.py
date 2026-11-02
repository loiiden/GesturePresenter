"""Train a separate pinch/not-pinch model from original recordings."""
import argparse
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from gesture_features import FeatureConfig
from gesture_model import GestureNetwork
from research.dataset import read_rows, matrix, TRIAL_KEY
from research.train import _split, _report, export_npz


def select_rows(rows, replacement_pinch=None):
    """Keep old negatives, optionally replace all old positives without editing data."""
    if replacement_pinch is not None:
        fresh = [r for r in replacement_pinch if r['hand'] == 'Right']
        if not fresh or any(r['gesture'] != 'pinch' for r in fresh):
            raise ValueError('Replacement dataset must contain right-hand pinch samples only')
        old_sessions = {r['session_id'] for r in rows}
        if old_sessions & {r['session_id'] for r in fresh}:
            raise ValueError('Use distinct session IDs for fresh pinch recordings')
        rows = [r for r in rows if r['gesture'] != 'pinch'] + fresh
    return [dict(r, gesture='pinch' if r['gesture'] == 'pinch' else 'none')
            for r in rows if r['hand'] == 'Right']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('datasets', nargs='+', type=Path)
    parser.add_argument('--replacement-pinch-dataset', type=Path,
                        help='Use only this fresh pinch dataset for positives; retain old negatives')
    parser.add_argument('--holdout-session', action='append', default=[])
    parser.add_argument('--holdout-trials-from-session', action='append', default=[],
                        help='Pilot: hold out one whole trial per condition in this session')
    parser.add_argument('--output', type=Path, default=Path('models/simple_pinch.npz'))
    args = parser.parse_args(argv)
    if not args.holdout_session and not args.holdout_trials_from_session:
        parser.error('Specify a session or whole-trial holdout for evaluation')
    source_rows = read_rows(args.datasets)
    replacement = (read_rows([args.replacement_pinch_dataset])
                   if args.replacement_pinch_dataset is not None else None)
    try:
        rows = select_rows(source_rows, replacement)
    except ValueError as exc:
        parser.error(str(exc))
    excluded_old_pinches = sum(r['gesture'] == 'pinch' for r in source_rows) if replacement is not None else 0
    all_source_rows = source_rows + (replacement or [])
    print(f'Using {len(rows)} right-hand frames; excluded {excluded_old_pinches} old pinch frames. Source files unchanged.')
    train, test = _split(rows, set(args.holdout_session),
                         set(args.holdout_trials_from_session), seed=42)
    if args.holdout_trials_from_session:
        print('PILOT: fresh poses evaluated on held-out whole trials within a session, not a new sitting.')
    if set(args.holdout_session) - {r['session_id'] for r in test}:
        parser.error('A requested held-out session is missing')
    for name, subset in [('training', train), ('evaluation', test)]:
        if {r['gesture'] for r in subset} != {'none', 'pinch'}:
            parser.error(f'{name} requires both pinch and negative examples')
    config = FeatureConfig()
    x, y, _ = matrix(train, config)
    xt, yt, _ = matrix(test, config)
    pipeline = make_pipeline(StandardScaler(), MLPClassifier(
        hidden_layer_sizes=(64, 32), max_iter=300, early_stopping=True,
        n_iter_no_change=15, random_state=42, batch_size=256))
    pipeline.fit(x, y)
    results = _report('Simple pinch (held-out data)', test, pipeline.predict(xt))
    metadata = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'simple_mode', 'hand': 'Right',
        'datasets': [str(p) for p in args.datasets],
        'replacement_pinch_dataset': str(args.replacement_pinch_dataset) if replacement is not None else None,
        'excluded_old_pinch_frames': excluded_old_pinches,
        'positive_source': 'replacement dataset only' if replacement is not None else 'base datasets',
        'original_labels': sorted({r['gesture'] for r in source_rows if r['hand'] == 'Right'}),
        'original_label_counts': dict(Counter(r['gesture'] for r in source_rows if r['hand'] == 'Right')),
        'label_policy': ('Fresh pinch replaces old pinch; every other original label becomes none'
                         if replacement is not None else
                         'Original pinch stays pinch; every other original label becomes none'),
        'excluded_frames': len(all_source_rows) - len(rows),
        'training_frames': len(train), 'test_frames': len(test),
        'training_label_counts': dict(Counter(r['gesture'] for r in train)),
        'test_label_counts': dict(Counter(r['gesture'] for r in test)),
        'training_sessions': sorted({r['session_id'] for r in train}),
        'holdout_sessions': sorted(set(args.holdout_session)),
        'trial_holdout_sessions': sorted(set(args.holdout_trials_from_session)),
        'training_trial_keys': sorted({tuple(r[k] for k in TRIAL_KEY) for r in train}),
        'holdout_trial_keys': sorted({tuple(r[k] for k in TRIAL_KEY) for r in test}),
        'results': results,
        'limitations': ('Recorded held poses, not live pinch sequences; one participant. No left-hand validation.'
                       + (' Pilot trial holdouts within a session do not measure new-session pinch performance.'
                          if args.holdout_trials_from_session else '')),
    }
    export_npz(args.output, pipeline, list(pipeline.classes_), config, metadata)
    runtime = GestureNetwork(args.output)
    actual = np.array([runtime.probabilities(f) for f in xt])
    np.testing.assert_allclose(actual, pipeline.predict_proba(xt), atol=2e-5)
    print(f'Exported {args.output}; NumPy probabilities match sklearn on {len(test)} held-out frames.')


if __name__ == '__main__':
    main()
