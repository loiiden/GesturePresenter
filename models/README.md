# Trained gesture models

`gesture_mlp.npz` is produced by `research/train.py` and read at runtime by
`gesture_model.py`. It is committed deliberately: the application needs it, it
is ~60 KB, and it contains only network weights — no landmarks and no recording.

It is not in the repository yet. Record and train first:

```bash
uv run --extra research python -m research.recorder --participant P001 --session S01
uv run --extra research python -m research.train research/data/gestures.csv \
    --holdout-session S03 --output models/gesture_mlp.npz
```

Until then `hand_tracker.py` falls back to the geometric rules in `gestures.py`
and prints that it has done so. Installing (`uv tool install` / `pip install .`)
will fail while the file is missing, which is intended — it prevents shipping an
install that silently runs on the fallback rules instead of the trained model.
