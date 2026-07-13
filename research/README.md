# Personalized gesture-classification study

These tools collect MediaPipe hand landmarks without saving camera frames, train
a local classical model, and compare it with the production rule classifier on
the exact same held-out session.

## Install

Use the project's supported Python (3.10–3.12):

```bash
uv sync --extra research
```

If a manually created environment such as `venv` is currently activated, `uv`
may warn that it does not match the project's `.venv`. This warning is not a
failure: `uv run` uses `.venv` by default. Either run `deactivate` first, or use
`uv run --active` only when the active environment uses a supported Python and
has been synchronized with the research dependencies.

The research extra pins scikit-learn 1.6.1 because the saved joblib models were
trained with that version. Scikit-learn does not guarantee that pickled models
remain compatible across versions. Run `uv sync --extra research` after pulling
dependency changes so old `.venv` installations are corrected.

The generated `research/data`, `research/models`, and `research/reports`
directories are intentionally ignored by Git.

## One-evening protocol

Record three genuinely separate sessions. Change position or lighting slightly
and take a break between them. Use your right hand, because that is the product's
presentation-control hand.

```bash
uv run --extra research python -m research.collect --participant P001 --session S01
uv run --extra research python -m research.collect --participant P001 --session S02
uv run --extra research python -m research.collect --participant P001 --session S03
```

The default protocol contains 135 randomized trials (15 repetitions of nine
classes) and takes about 10–15 minutes per session. Press `r` during a trial to
retry it or `q` to stop safely; completed trials are appended immediately.
Use a different session ID when restarting a logically new session. Do not reuse
an ID after changing the protocol.

No images are written. Each CSV row contains the 21 `(x, y, z)` landmarks,
handedness, timestamp, gesture, trial, session, and participant identifiers.

## Train without the final session

Reserve `S03` before inspecting its performance:

```bash
uv run --extra research python -m research.train \
  research/data/landmarks.csv --model tree --exclude-session S03 \
  --output research/models/tree.joblib
```

Other supported models are `forest` and `logistic`. The artifact records its
training sessions and feature schema.

## One-to-one held-out comparison

```bash
uv run --extra research python -m research.compare \
  --model research/models/tree.joblib \
  --session S03 research/data/landmarks.csv
```

Both classifiers receive the same raw landmarks in the same order. The report
includes frame and trial-majority accuracy, a classification report, and a
confusion matrix. Evaluation refuses to run if the model trained on the chosen
session. The hard-coded classifier's hysteresis is reset at every trial.

Trial-level performance is the primary result because neighboring video frames
are not independent samples. This is a single-user personalized pilot and must
not be presented as evidence of cross-user generalization.

## Interactive XAI sandbox

The sandbox compares the production rules and all available trained models on
the same landmarks. It is research-only: it does not import the action layer and
cannot move the pointer, click, type, or change slides.

For a reliable presentation, replay the held-out S03 landmarks:

```bash
uv run --extra research python -m research.explain \
  --mode replay --session S03
```

The initial filter shows every trial. Press `f` once to show only cases where
the rules were wrong and the selected learned model was right. This is the most
useful view for demonstrating the `none`-class result. No footage is replayed;
the hand is reconstructed as a skeleton from stored landmarks.

For an interactive camera demonstration:

```bash
uv run --extra research python -m research.explain --mode live
```

The live view classifies one hand without recording it. There are no expected
labels in this mode, so correctness cannot be measured; it is intended to show
prediction agreement and explanations, not to create a new evaluation result.

### Controls

| Key | Action |
| --- | --- |
| `1`, `2`, `3` or `m` | Select the explained model |
| `f` | Cycle replay filters |
| `a` / `d` | Previous / next trial |
| `j` / `k` | Previous / next frame |
| `Space` | Pause or resume replay |
| `+` / `-` | Change replay speed |
| `r` | Restart the current trial |
| `g` | Toggle the global model overview |
| `q` or `Esc` | Close the sandbox |

Explanations depend on the selected model:

- **Decision tree:** the exact local path of feature thresholds used for the
  current prediction, plus the nearest boundary on that path.
- **Random forest:** prediction confidence and global feature importance. The
  UI explicitly avoids presenting global importance as a local cause.
- **Logistic regression:** signed feature contributions to the predicted
  class's linear score after standardization.
- **Rules:** normalized pinch ratios, active hysteresis threshold, finger gap,
  and finger-extension states.

Press `g` to show trial accuracy, macro F1, global feature ranking, and the
scope warnings needed to interpret the pilot honestly. Model confidence is
shown as model output, not as calibrated certainty.

To load a subset or a differently named artifact, repeat `--model`:

```bash
uv run --extra research python -m research.explain \
  --model research/models/tree.joblib \
  --model research/models/forest.joblib
```

Validate the data, artifacts, metrics, and explanation pipeline without opening
a window or camera:

```bash
uv run --extra research python -m research.explain \
  --headless-check --session S03
```

Like `research.compare`, replay mode refuses to use a model trained on the
selected evaluation session unless `--allow-training-overlap` is explicitly
passed. That override is for debugging, not for reporting results.
