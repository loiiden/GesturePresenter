# Trained gesture model

`gesture_mlp.npz` is produced by `research/train.py` and loaded by
`gesture_model.py`. The committed archive contains network weights and feature
statistics, without raw recordings. Inference uses NumPy only.

The current archive contains the clean `point`/`index_thumb` pair and eight
unchanged classes. Both pinch classes are absent. Pointing and left click are
enabled through the learned model.

## Validation (2026-09-15)

Training reused all 19,688 retained frames and added 1,566 frames from G01
(34 trials). G01 passes the recording quality/position checks, with 2.19x
near/far separation. Four planned repetitions were skipped, but every required
gesture/hand/condition is represented at least twice.

S03 was held out entirely for unchanged gestures. With only G01 available,
one whole trial per gesture/hand/condition was reserved within G01: 13 test
trials and 21 training trials. No trial contributes frames to both partitions.
This is a pilot result; new-pose performance across sittings is unmeasured.

| Evaluation | Result |
| --- | --- |
| Exported MLP | 156/158 trials correct (98.73%) |
| Runtime with smoothing | 157/158 trials correct (99.37%) |
| Fresh pointing / clicking, runtime | 13/13 trials correct |
| Click events, recorded holdouts + simulated release | 8/8 single clicks; zero false-click trials |

The remaining runtime error is a left-hand `none` trial read as thumbs-up,
which has no left-hand action. These are recorded-pose tests, not a live camera
or continuous-transition evaluation. Eight regression tests and the synthetic
training/export/runtime check also pass.

Detailed local results: `research/reports/gesture_v3_runtime.json`.
Previous model backup: `research/reports/gesture_mlp_before_v3.npz`.

Reproduce the current pilot model:

```bash
uv run --extra research python -m research.train research/data/gestures_v3.csv \
  --replacement-dataset research/data/pointer_click.csv \
  --holdout-session S03 --holdout-trials-from-session G01
```

Follow the [incremental recording workflow](../research/README.md#replace-only-pointer-and-click)
to record only clean pointing and clicking, then train using the retained data:

```bash
uv run --extra research python -m research.train research/data/gestures_v3.csv \
  --replacement-dataset research/data/pointer_click.csv \
  --holdout-session S03 --holdout-session G03 --baselines
```

After recording G02/G03, use the session holdout command above to measure
performance on a new sitting. Restart the app after replacing the model.
