# Personalized gesture-classification study

These tools collect MediaPipe hand landmarks without saving camera frames, train
a local classical model, and compare it with the production rule classifier on
the exact same held-out session.

## Install

Use the project's supported Python (3.10–3.12):

```bash
uv sync --extra research
```

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
