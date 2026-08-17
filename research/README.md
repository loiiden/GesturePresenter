# Gesture model: recording, training, shipping

Everything in this directory is a **development tool**. None of it is packaged
into the application — `pyproject.toml` omits it from `py-modules`, and
`GesturePresenter.spec` bundles only `models/`. The recorder is here so gestures
can be captured easily, not as a user-facing feature.

What ships is three files at the repository root:

| File | Role |
| --- | --- |
| `gesture_features.py` | Landmarks → feature vector. Imported by the trainer *and* the runtime, so they cannot drift apart. |
| `gesture_model.py` | NumPy-only inference: loads the exported `.npz`, adds smoothing, a confidence floor and hysteresis. |
| `models/gesture_mlp.npz` | The trained network (~60 KB). |

The application never imports scikit-learn. scikit-learn does not guarantee that
pickled estimators load across versions, so shipping one would make the built
binary fail in a way that only shows up on someone else's machine.

## Quick start

```bash
uv sync --extra research

# 1. Verify the whole pipeline without a camera (~20 s)
uv run --extra research python -m research.selftest

# 2. Record three sessions, changing position and lighting between them
uv run --extra research python -m research.recorder --participant P001 --session S01
uv run --extra research python -m research.recorder --participant P001 --session S02
uv run --extra research python -m research.recorder --participant P001 --session S03

# 3. Train, holding out the last session entirely
uv run --extra research python -m research.train research/data/gestures.csv \
    --holdout-session S03 --baselines

# 4. The app now picks the model up automatically
uv run gesture-presenter
```

## The recorder

A pywebview window with a live skeleton preview, guided prompts, and a countdown
→ record → rest cycle. Roughly **194 trials, ~14 minutes** per session.

Keyboard: `Space` pause/resume, `R` retake, `S` skip.

**Condition blocking.** Trials are grouped into blocks — normal, near, far,
tilted, off-centre, then the left-hand block — and shuffled only *within* a
block. Fully randomising would ask you to move nearer and further every three
seconds, which is not physically practical and silently mislabels the distance
conditions.

**Quality gating.** Every frame is checked for detection confidence, clipping at
the frame edge, and apparent hand size. A trial that yields fewer than 12 good
frames is rejected with the reason shown and re-queued rather than being written.
Thin or mistracked trials are exactly what poisons a small dataset. You can also
delete any recent trial from the side panel; deletion is always by whole trial,
never by frame, so a partially removed trial cannot leave a biased remainder.

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

Eleven classes. Nine drive actions; two exist purely to protect a neighbour:

| Gesture | Action |
| --- | --- |
| `point` | move the pointer |
| `pinch` | left click |
| `pinch_right` | right click |
| `open_palm` | swipe horizontally to change slide |
| `v_sign` | Mission Control |
| `two_finger_scroll` | scroll |
| `fist` | black screen |
| `fist_thumb_up` | play / pause |
| `fist_thumb_left`, `fist_thumb_right` | **nothing** |
| `none` | nothing |

`fist_thumb_left` / `fist_thumb_right` are recorded but bound to no action. Left
out of the label set entirely, a fist with the thumb sticking sideways has
nowhere to land and the model assigns it to its nearest neighbour — `fist` —
which blacks the screen mid-presentation. Giving them their own class turns a
disruptive misfire into a harmless no-op.

Motion-dependent behaviour is unchanged and still lives outside the model:
`PinchTracker` distinguishes click from drag, `PalmSwipeTracker` turns a held
palm into a directional swipe, `ScrollTracker` integrates vertical movement.
The model only answers "what shape is this hand, right now".

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

## Scope

This is a personalized pilot: one participant unless more are recorded. Held-out
*session* accuracy says the model survives a new sitting, not that it generalizes
to new people. Report it that way.
