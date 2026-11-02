# Gesture model: recording, training, shipping

Everything in this directory is a **development tool**. None of it is installed
with the application — `pyproject.toml` omits it from `py-modules` and from the
packaged data files. The recorder is here so gestures can be captured easily,
not as a user-facing feature.

What ships is three files at the repository root:

| File | Role |
| --- | --- |
| `gesture_features.py` | Landmarks → feature vector. Imported by the trainer *and* the runtime, so they cannot drift apart. |
| `gesture_model.py` | NumPy-only inference: loads the exported `.npz`, adds smoothing, a confidence floor and hysteresis. |
| `models/gesture_mlp.npz` | The trained network (~60 KB). |

The application never imports scikit-learn. scikit-learn does not guarantee that
pickled estimators load across versions, so shipping one would make the built
binary fail in a way that only shows up on someone else's machine.

## Replace only pointer and click

Record two clean poses: `point` with the index straight and thumb tucked, and
`index_thumb` with the index straight and thumb straight out to the side
(an L shape). Keep middle/ring/pinky curled for both. The click fires once on
release and works with either hand. Right click is removed.

All old `point`, `pinch`, and `pinch_right` recordings are excluded. Every
other class keeps its existing data, action mapping and timing. The CSV schema
and feature vector are unchanged; no full recording session is needed.

1. Prepare the retained dataset (already done in this checkout):

   ```bash
   uv run --extra research python -m research.migrate_gestures research/data/gestures.csv
   ```

   This creates `research/data/gestures_v3.csv` and a
   `gestures_v3.migration.json` report. The original `gestures.csv` stays
   intact for recovery. Existing outputs are never overwritten; use
   `--dry-run` to inspect the counts without writing.

   Local result: **19,688 frames / 436 trials retained** from all eight
   unchanged classes. **6,565 frames / 143 trials excluded**, covering all old
   pointing and both pinch classes. There is no geometric filtering or
   automatic relabelling of old pointing poses.

2. Record the two replacement poses in three short sittings, changing lighting
   or seating between them. Use new session IDs:

   ```bash
   uv run --extra research python -m research.recorder --participant P001 --session G01 --gestures point index_thumb --output research/data/pointer_click.csv
   uv run --extra research python -m research.recorder --participant P001 --session G02 --gestures point index_thumb --output research/data/pointer_click.csv
   uv run --extra research python -m research.recorder --participant P001 --session G03 --gestures point index_thumb --output research/data/pointer_click.csv
   ```

   Each sitting has **38 trials**: 16 right-hand pointing, 16 right-hand click,
   and 6 left-hand click trials. Allow about three minutes plus positioning.
   Countdown, rest, near/far/tilted/off-centre blocks, calibration, and quality
   gates work as before. Hold the requested pose throughout recording and
   release during rest. Each launch gets unique trial IDs.

3. Check each new sitting:

   ```bash
   uv run --extra research python -m research.inspect research/data/pointer_click.csv --gestures point index_thumb --session G01
   uv run --extra research python -m research.inspect research/data/pointer_click.csv --gestures point index_thumb --session G02
   uv run --extra research python -m research.inspect research/data/pointer_click.csv --gestures point index_thumb --session G03
   ```

4. Train on the retained data plus the fresh pointer/click file:

   ```bash
   uv run --extra research python -m research.train research/data/gestures_v3.csv \
     --replacement-dataset research/data/pointer_click.csv \
     --holdout-session S03 --holdout-session G03 --baselines
   ```

   `--replacement-dataset` identifies the fresh recordings. The trainer
   excludes any old point rows in the base datasets and removes both pinch
   classes from all inputs. This also handles supplying the original base CSV
   accidentally without mixing its old points into the new recordings.

   S03 tests unchanged gestures; G03 tests fresh pointing and clicking on an
   unseen sitting. Export is blocked if any current class is missing from
   training or the requested holdout. `--allow-incomplete` is only for
   synthetic development tests.

The bundled model has now been trained on the retained data and G01, enabling
the fresh pointer/click pair. There is no legacy pointer compatibility rule.
With only G01 available, the initial evaluation reserves whole trials within
that sitting; it does not yet establish performance across sittings:

```bash
uv run --extra research python -m research.train research/data/gestures_v3.csv \
  --replacement-dataset research/data/pointer_click.csv \
  --holdout-session S03 --holdout-trials-from-session G01
```

This reserves one trial per participant/session/gesture/hand/condition, requires
at least two trials in each group, and records the exact held-out trial keys in
the model metadata. Augmentation is applied only after the split. Prefer the
G03 whole-session holdout above once those additional recordings exist.

[Current results](../models/README.md): 157/158 recorded holdout trials correct
through runtime smoothing; all 13 pointer/click trials correct. Restart the app
after retraining to load the new model.

## Quick start (full dataset, for a new operator)

```bash
uv sync --extra research

# 1. Verify the whole pipeline without a camera (~20 s)
uv run --extra research python -m research.selftest

# 2. Record three sessions, changing lighting/position between them.
#    The recorder enforces each distance block itself — just follow the on-screen
#    arrow until it turns green; it starts recording on its own.
uv run --extra research python -m research.recorder --participant P001 --session S01
uv run --extra research python -m research.recorder --participant P001 --session S02
uv run --extra research python -m research.recorder --participant P001 --session S03

# 3. Confirm the recording actually varied (exits non-zero if it did not)
uv run --extra research python -m research.inspect research/data/gestures.csv

# 4. Train, holding out the last session entirely
uv run --extra research python -m research.train research/data/gestures.csv \
    --holdout-session S03 --baselines

# 5. The app now picks the model up automatically
uv run gesture-presenter
```

## The recorder

A pywebview window with a live skeleton preview, guided prompts, and a countdown
→ record → rest cycle. Roughly **184 trials, ~13 minutes** per full session; 38 trials with
`--gestures point index_thumb`.

Keyboard: `Space` pause/resume, `R` retake, `S` skip.

**Condition blocking.** Trials are grouped into blocks — normal, near, far,
tilted, off-centre, then the left-hand block — and shuffled only *within* a
block. Fully randomising would ask you to move nearer and further every three
seconds, which is not physically practical.

**The position gate enforces each block; it does not ask you to read anything.**
At a block boundary the recorder shows one glyph, one verb (`MOVE CLOSER`,
`MOVE BACK`, `MOVE TO A CORNER`) and a meter showing where you are relative to
where you need to be. It starts by itself once you hold the right position for
0.8 s. Frames outside the band are not counted as usable, so a `near` trial
cannot be recorded from your normal distance — after two failed trials the
full-screen cue returns. `Skip position check` overrides it if your camera
genuinely cannot reach a target.

Distance targets are **ratios of your own normal-distance span**, measured from
the first block, not absolute numbers: a fixed span is trivial on a wide-angle
webcam and unreachable on a narrow one. `near` means ≥1.4x your baseline, `far`
means ≤0.72x, which guarantees the two separate whatever camera you use.

This exists because session S01 was recorded without it and was unusable: every
per-frame quality measure passed (99% median detection confidence, full-length
trials, 193/194 saved) while near, far and offcentre came out statistically
identical to normal — a near/far span ratio of 0.98x where anything above 1.5x
was needed. A prompt that can be ignored will be.

**Quality gating.** Every frame is checked for detection confidence, clipping at
the frame edge, apparent hand size, and the active block's position target. A
trial yielding fewer than 12 good frames is rejected with the reason shown and
re-queued rather than written. You can also delete any recent trial from the
side panel; deletion is always by whole trial, never by frame, so a partially
removed trial cannot leave a biased remainder.

**Privacy.** No video is written. Only landmark coordinates leave the camera
loop. `research/data/` is gitignored.

### Recording well

- Use your **right hand** for the main blocks — it is the product's control hand.
- Vary the pose *within* a condition: same gesture, slightly different wrist
  angle and height each repetition.
- For `none`, be genuinely varied — resting, talking with your hands, reaching
  for the keyboard. This class is what stops the app acting while you present,
  so it needs to cover the space of "not a command" rather than one neutral pose.
- Record the three sessions **at different times of day**, or move the lamp
  between them. Lighting variation across sessions is what makes the held-out
  session a real test rather than a re-run of training.

## Invariances

The user-visible requirement was that a gesture works at different distances and
in different rooms. Three mechanisms handle that, in the order they apply:

1. **Aspect correction.** MediaPipe normalizes `x` by frame width and `y` by
   frame height *separately*. On a 16:9 camera every hand therefore arrives
   stretched ~1.78x horizontally; on 4:3 it is ~1.33x. Multiplying `x` and `z`
   by the aspect ratio restores isotropy, so a model trained on one camera
   transfers to another. The recorder stores `frame_width`/`frame_height` so the
   correction is exact rather than assumed.
2. **Rigid-palm normalization.** Coordinates are centred on the centroid of
   landmarks {0, 5, 9, 13, 17} and scaled by their RMS radius. Those five points
   keep their mutual distances whatever the fingers do, which makes the scale
   independent of both pose and distance from the camera.
3. **World landmarks.** MediaPipe's metric 3-D output is included as its own
   feature block. It is already in meters with the origin at the hand's centre,
   so it is distance-invariant by construction and carries real depth that the
   projected 2-D landmarks only approximate.

Distance and translation invariance are verifiable directly:

```bash
uv run --extra research python -c "
import numpy as np; from gesture_features import extract_features
rng=np.random.default_rng(0); p=rng.normal(size=(21,3))*0.1+0.5; w=rng.normal(size=(21,3))*0.05
a=extract_features(p,w,aspect=16/9); b=extract_features(p*2+0.3,w,aspect=16/9)
print('max difference after doubling size and shifting:', abs(a[:134]-b[:134]).max())"
```

Because scale and translation are removed exactly, augmenting them would only
duplicate rows — which is why `research/augment.py` does not.

## Augmentation

`research/augment.py` produces N copies per training frame (default 6):

| Transform | Stands in for |
| --- | --- |
| In-plane rotation | Tilted head, tilted camera, rotated wrist |
| Out-of-plane rotation (pitch/yaw) | Viewing the hand from a different angle |
| Landmark jitter (0.5–4.5% of palm radius) | Sensor noise, motion blur, dim light |
| Mild anisotropic stretch | Lens and perspective variation |

In-plane rotation is **capped at ±10° for `fist_thumb_up`, `fist_thumb_left` and
`fist_thumb_right`** and ±25° otherwise. Those three classes are *defined* by
their orientation, so rotating one far enough turns it into a different gesture
while keeping the old label — augmentation that manufactures wrong labels.

## Gesture set

Ten classes:

| Gesture | Action |
| --- | --- |
| `point` | move the pointer |
| `index_thumb` | left click on release (either hand) |
| `open_palm` | swipe horizontally to change slide |
| `v_sign` | Mission Control |
| `two_finger_scroll` | scroll |
| `fist` | black screen |
| `fist_thumb_up` | play / pause |
| `fist_thumb_left`, `fist_thumb_right` | previous / next slide (existing static fallback) |
| `none` | nothing |

### Shape and motion

`point` now means an extended index with the thumb relaxed or tucked.
`index_thumb` adds a straight sideways thumb. Contact is not part of the
click definition, so the former fingertip-contact gates are no longer used.
The feature schema stays unchanged, preserving compatibility with saved data.

Motion-dependent behaviour remains outside the model: `ClickTracker` emits
one click on release, `PalmSwipeTracker` recognizes directional swipes, and
`ScrollTracker` integrates vertical movement. Click debounce, tracking-loss
cancellation, either-hand support, and the voice/controls guards are preserved.

## Training

```bash
uv run --extra research python -m research.train research/data/gestures.csv \
    --holdout-session S03 --baselines
```

Evaluation holds out **a whole session**, so reported numbers describe a
recording the model has never seen. Frame accuracy is reported but trial
accuracy is the honest headline: neighbouring video frames are near-duplicates,
so frame accuracy flatters the model.

`--baselines` also fits a decision tree, random forest and logistic regression,
and the hard-coded rules from `main` are always evaluated on the same held-out
rows — that comparison is the case for replacing them.

Useful flags: `--no-world` (ablate the world-landmark block), `--augment-copies 0`
(ablate augmentation), `--hidden 256,128`, `--min-score`.

## Runtime behaviour

`gesture_model.MLGestureClassifier` is a drop-in for `gestures.GestureClassifier`
and returns the same `(Gesture, payload)` pair, so nothing downstream changed.
It adds:

- **Probability smoothing** — an EMA over frames, so one bad frame cannot fire.
- **A confidence floor** — below it the result is `NONE` rather than the best of
  several bad options.
- **Enter/stay hysteresis** — switching class needs more confidence (0.62) than
  holding one (0.38), which stops flicker at decision boundaries.

The payload also exposes per-class `probs`. `hand_tracker.py` uses this to give
swipe detection a permissive threshold (0.35): at swipe speed the palm blurs and
briefly loses the argmax, and a missed slide change is more annoying than a late
one — while black screen and Mission Control stay on the strict path. Different
actions genuinely want different precision/recall trade-offs, and probabilities
are how you get them from one model.

Both hands run through the model. The left hand is mirrored into the right
hand's frame, so a single model serves the control hand, the controls lock
(`open_palm`) and the voice trigger (`fist`). Each hand keeps its own smoothing
state.

If `models/gesture_mlp.npz` is missing, `hand_tracker.py` falls back to the
original geometric rules and says so on stdout.

## Files

| File | Purpose |
| --- | --- |
| `protocol.json` | Classes, instructions, conditions, timing, quality thresholds |
| `recorder.py` + `recorder_frontend/` | The guided recorder |
| `dataset.py` | CSV schema v2, loading, filtering, trial-level grouping |
| `augment.py` | Training-time augmentation |
| `train.py` | Training, evaluation, `.npz` export |
| `selftest.py` | Camera-free end-to-end pipeline check |
| `migrate_gestures.py` | Remove old point/pinch data while preserving all other classes |
| `test_gesture_change.py` | Gesture replacement regression checks |

## Results (previous gesture set, before replacement)

These scores describe the original model, including the retired pinch classes.
They are not measurements of the new click gesture.

Three sessions from one participant (P001), recorded on separate occasions with
the lighting and seating changed between them. S03 was held out entirely:
26,253 frames / 579 trials, of which 8,752 frames / 193 trials are the holdout.

Trial-level scores on the held-out session:

| Classifier | Trial accuracy | Macro-F1 |
| --- | --- | --- |
| Random forest | 0.995 | 0.995 |
| **MLP (shipped)** | **0.990** | **0.990** |
| Decision tree | 0.984 | 0.988 |
| Logistic regression | 0.984 | 0.984 |
| Hard-coded rules | 0.798 | 0.770 |

The forest is one trial ahead of the MLP out of 193 — inside the noise at this
sample size, and it does not survive the export path, since a 300-tree forest
cannot be flattened into a small dense-weight archive the way an MLP can. The
MLP is chosen for a 129 KB dependency-free artifact at statistically
indistinguishable accuracy.

The rules fail where the product actually hurts:

| Class | Rules F1 | MLP F1 | Consequence of the rules' error |
| --- | --- | --- | --- |
| `none` | 0.32 | 0.95 | acts on hands that were not commanding anything |
| `fist_thumb_right` | 0.12 | 1.00 | collapses onto `fist` → blacks the screen |
| `fist_thumb_up` | 0.64 | 0.97 | spurious play/pause |
| `v_sign` | 0.81 | 1.00 | missed Mission Control |

**Left hand:** 18/18 correct on the held-out session, classified by mirroring
right-hand training data into the left hand's frame. The controls lock and voice
trigger have no left-hand training examples of their own.

## Scope

A personalized pilot: one participant. Held-out *session* accuracy says the
model survives a new sitting with different lighting and seating — not that it
generalizes to other people. Report it that way.


## Simple-mode pinch

The installed `models/simple_pinch.npz` combines old `pinch` recordings from
`gestures.csv` with new `PINCH_V2_01` pinches from `pinch_v2.csv`. Every other
right-hand pose from `gestures.csv` and `pointer_click.csv` becomes `none`.
No old pinch samples are excluded by label. Source CSVs and the full-mode
model remain unchanged.

Reproduce the installed model:

```sh
uv run --extra research python -m research.train_simple research/data/gestures.csv research/data/pointer_click.csv research/data/pinch_v2.csv --holdout-session S03 --holdout-trials-from-session PINCH_V2_01 --output models/simple_pinch_combined.npz
```

Training uses 1,903 pinch frames (1,420 old + 483 fresh) and 15,824 negative
frames. S03 is held out entirely: 16 old pinch trials and 159 negative trials.
One whole fresh trial per condition is held out (5 trials, 230 frames), leaving
11 fresh trials for training. Training and evaluation trial keys are disjoint.
This remains a pilot for fresh pinches: performance in a new sitting is not
measured by a within-session trial holdout.

Raw model results: 97.73% frame accuracy and 176/180 correct trials. Exported
NumPy probabilities match sklearn on all 8,190 held-out frames. Runtime replay
at 30 fps with a recorded neutral lead-in and simulated release detects 5/5
fresh and 16/16 old pinch trials. With the geometric release guard, it produces
no false actions on 159 negative trials (previously four without the guard).
The runtime confidence threshold and model weights are unchanged.

`MAX_PINCH_DISTANCE_RATIO = 0.30` in `simple_mode.py` limits thumb–index
separation to 30% of wrist-to-middle-knuckle length, using aspect-corrected 2-D
coordinates. Old/fresh training pinch frames had maximum ratios of 0.216/0.173;
the guard leaves room for tracking noise. Beyond the limit, the classifier's
hysteresis resets and the temporal tracker receives a non-pinch observation.
Release keeps the 45 ms debounce, with no double-pinch window. Right-hand
release emits next slide; left-hand release emits previous slide. Separate
classifier/tracker state per hand shares one model; left image and world
landmarks are mirrored before feature extraction. Opposite commands released
on the same frame cancel each other. Tests cover sticky model confidence,
distance/scale changes, independent hand tracking, immediate releases, and
identical probabilities for mirrored inputs.

Recorded replay passes all 180 trials on the right and all 180 mirrored trials
on the left: 21/21 pinches and 159/159 negative trials per hand. Reports are
`research/reports/simple_pinch_combined_runtime.json` and
`research/reports/simple_pinch_mirrored_left_runtime.json`. Mirrored right-hand
recordings validate symmetry, not accuracy on newly captured left-hand poses.
These tests use simulated transitions and do not establish live-camera accuracy.

The installed archive and `simple_pinch_combined.npz` contain the same weights.
`simple_pinch_v2.npz` retains the previous fresh-only candidate. A backup of the
preceding installed model is saved locally under `research/reports/` with a
`simple_pinch_before_combined_` timestamp. Early stopping uses an internal
training split, separate from the reported held-out evaluation.

The optional replacement workflow below remains available, but is **not used**
by the currently installed combined model.

### Replace old pinches with fresh recordings

Keep the old CSVs intact. Use a separate `research/data/pinch_v2.csv` and session
IDs `PINCH_V2_01`, `PINCH_V2_02`, `PINCH_V2_03`. The gesture label remains `pinch`:
the source dataset and session identify its generation, rather than inventing
a different physical gesture. The existing interactive recorder provides live
preview, position gates, countdown, retakes, and quality checks.

```sh
uv run --extra research python -m research.recorder --protocol research/protocol_simple.json --participant P001 --session PINCH_V2_01 --output research/data/pinch_v2.csv
```

Each session has 16 right-hand trials across normal, near, far, tilted and
off-centre conditions. Touch thumb and index tips and hold contact during each
recording; release during rest. Vary the remaining fingers and wrist naturally.
Record one held pinch per trial; the same model serves the left hand through
mirroring at inference. No separate left-hand training label is needed.
Repeat with `PINCH_V2_02` and `PINCH_V2_03` at different sittings.

After recording, train a candidate model:

```sh
uv run --extra research python -m research.train_simple research/data/gestures.csv research/data/pointer_click.csv --replacement-pinch-dataset research/data/pinch_v2.csv --holdout-session S03 --holdout-session PINCH_V2_03 --output models/simple_pinch_v2.npz
```

`--replacement-pinch-dataset` excludes all old `pinch` rows from both training
and evaluation; it does not delete or relabel any source file. Other original
poses remain negative examples. Only the fresh dataset supplies positive
examples. Empty, non-pinch, or overlapping-session replacement inputs fail
before the model is written. Metadata records the source and exclusion counts.
S03 evaluates old negatives; PINCH_V2_03 evaluates fresh positives, both held out
entirely. A pinch-only holdout cannot measure false activations by itself.

The app continues using `models/simple_pinch.npz` until the candidate is
validated and deliberately installed there. Test live releases with both
hands too; held-pose accuracy alone does not establish live reliability.
For stronger validation, collect fresh `none` samples with the normal protocol
in a separate dataset and include it among the positional negative datasets.

Camera-free checks:

```sh
uv run --extra research python -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend.test.cjs
```
