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

## Quick start

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
→ record → rest cycle. Roughly **194 trials, ~14 minutes** per session.

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

### Contact gates

`pinch` and `pinch_right` are defined by fingertips *touching*, but a classifier
learns whatever separates its training data, which is not the same thing. In
S01+S02 every recorded pinch had a normalized thumb-index distance below 0.69
and every point above 1.02, leaving the 0.69–1.02 band completely unlabelled —
and that band is exactly what a hand crosses while a thumb approaches a finger.
The learned boundary there was arbitrary extrapolation, so a click could fire
before contact.

The runtime therefore measures the distance and vetoes a predicted contact
gesture when the fingers are apart, falling through to the best non-contact
class (usually `point`) so pointer movement is not interrupted. Limits are
calibrated per operator at training time from their own recorded pinches —
p99 x 1.20 to enter, x 1.55 to release — because hand proportions differ. The
percentile rather than the maximum keeps one mistracked frame from widening the
gate permanently.

Measured effect on an interpolated approach, thumb closing toward index:

| thumb-index distance | model alone | with the gate |
| --- | --- | --- |
| 1.015 | point | point |
| 0.848 | **pinch** | point |
| 0.697 | pinch | pinch |

The gate rejects none of the genuine recorded pinches. The protocol also now
asks for close-but-not-touching thumb poses during `point` and `none` trials, so
future sessions supervise the zone directly instead of relying on the veto alone.

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

## Results

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
