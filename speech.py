"""
Audio recording + Whisper transcription.
Thread-safe: start_recording() / stop_recording() called from camera loop,
result delivered via on_result callback from a background thread.
"""
import threading
import warnings
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE  = 16000   # Whisper expects 16 kHz
MODEL_SIZE   = "small" # "tiny" fastest · "small" good balance · "base" in-between


class SpeechRecognizer:
    def __init__(self, on_result, on_transcribing):
        """
        on_result(text: str)  — called from background thread when done.
        on_transcribing()     — called just before Whisper starts.
        """
        self._on_result       = on_result
        self._on_transcribing = on_transcribing
        self._frames          = []
        self._lock            = threading.Lock()
        self._stream          = None
        self._model           = None
        # Load model in background so startup is instant
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        print(f"[speech] loading Whisper '{MODEL_SIZE}' model…")
        self._model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        print("[speech] model ready")

    def start_recording(self):
        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._cb,
        )
        self._stream.start()

    def stop_recording(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        frames = None
        with self._lock:
            frames = list(self._frames)
        threading.Thread(target=self._transcribe, args=(frames,), daemon=True).start()

    def _cb(self, indata, _frames, _time, _status):
        with self._lock:
            self._frames.append(indata.copy())

    def _transcribe(self, frames):
        self._on_transcribing()
        if not frames or self._model is None:
            self._on_result("")
            return
        audio = np.concatenate(frames, axis=0).flatten()

        # Whisper's mel-spectrogram computation overflows on silence/very short clips.
        # Pad to at least 0.5 s and skip if essentially silent.
        min_samples = SAMPLE_RATE // 2
        if len(audio) < min_samples:
            audio = np.pad(audio, (0, min_samples - len(audio)))
        if np.abs(audio).max() < 0.01:
            self._on_result("")
            return

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            segments, _ = self._model.transcribe(audio, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        self._on_result(text)
