from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path


APP_NAME = "Gesture Presenter"


def _config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("APPDATA", Path.home()))
    elif system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "gesture-presenter"


@dataclass
class AppConfig:
    mode: str = "presentation"
    voice_enabled: bool = False
    camera_index: int = 0
    display_index: int = 0

    @classmethod
    def load(cls) -> "AppConfig":
        path = _config_dir() / "config.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            allowed = cls.__dataclass_fields__.keys()
            return cls(**{key: value for key, value in data.items() if key in allowed})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        directory = _config_dir()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "config.json").write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )
