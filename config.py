"""Zentrale Konfiguration des Visual-Moduls.

Auflösungsreihenfolge (späteres überschreibt früheres):
    1) Defaults im Code
    2) config.yaml im Repo-Root (optional, benötigt PyYAML)
    3) Umgebungsvariablen (VISUAL_*, VISION_*)

Aktive Werte anzeigen: ``python config.py``
"""
from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

log = logging.getLogger("visual.config")


@dataclass
class VisualConfig:
    # Server
    host: str = "0.0.0.0"        # 0.0.0.0 = von anderen Geräten erreichbar
    port: int = 7995             # Visual-Range 7991–8000

    # Detector-Wahl: "" (auto: Hailo, sonst YOLO), "hailo", "yolo"
    detector_mode: str = ""

    # Detection
    confidence_min: float = 0.5
    window_size: int = 8
    min_hits_in_window: int = 5

    # YOLO (lokales Testen ohne Pi)
    camera_index: int = 0
    model_path: str = "yolov8n.pt"

    # Hailo (Pi 5 + Hailo-8)
    hailo_input: str = "rpi"     # "rpi" (CSI), "usb" oder /dev/videoX
    hailo_hef_path: str = ""     # leer = Default-HEF der Pipeline

    # Timing
    stop_timeout_seconds: float = 5.0
    stale_after_seconds: float = 1.5   # ohne neuen Frame gilt das Window als veraltet

    # MJPEG-Stream
    stream_jpeg_quality: int = 80
    stream_fps: int = 15
    stream_max_width: int = 640        # 0 = nicht verkleinern

    def validate(self) -> None:
        if not (7991 <= self.port <= 8000):
            raise ValueError(f"port={self.port} außerhalb der Range 7991–8000")
        if self.detector_mode not in ("", "hailo", "yolo"):
            raise ValueError(f"detector_mode={self.detector_mode!r} ungültig")
        if not (0.0 <= self.confidence_min <= 1.0):
            raise ValueError(f"confidence_min={self.confidence_min} muss in [0.0, 1.0] liegen")
        if self.window_size < 1:
            raise ValueError(f"window_size={self.window_size} muss >= 1 sein")
        if not (1 <= self.min_hits_in_window <= self.window_size):
            raise ValueError(f"min_hits_in_window={self.min_hits_in_window} muss in [1, window_size] liegen")
        if self.camera_index < 0:
            raise ValueError(f"camera_index={self.camera_index} muss >= 0 sein")
        if self.stop_timeout_seconds <= 0:
            raise ValueError(f"stop_timeout_seconds={self.stop_timeout_seconds} muss > 0 sein")
        if self.stale_after_seconds <= 0:
            raise ValueError(f"stale_after_seconds={self.stale_after_seconds} muss > 0 sein")
        if not (1 <= self.stream_jpeg_quality <= 100):
            raise ValueError(f"stream_jpeg_quality={self.stream_jpeg_quality} muss in [1, 100] liegen")
        if self.stream_fps < 1:
            raise ValueError(f"stream_fps={self.stream_fps} muss >= 1 sein")
        if self.stream_max_width < 0:
            raise ValueError(f"stream_max_width={self.stream_max_width} muss >= 0 sein")


_ENV_MAP: dict[str, str] = {
    "host": "VISUAL_HOST",
    "port": "VISUAL_PORT",
    "detector_mode": "VISUAL_DETECTOR",
    "confidence_min": "VISION_CONFIDENCE_MIN",
    "window_size": "VISION_WINDOW_SIZE",
    "min_hits_in_window": "VISION_MIN_HITS_IN_WINDOW",
    "camera_index": "VISION_CAMERA_INDEX",
    "model_path": "VISION_MODEL_PATH",
    "hailo_input": "VISION_HAILO_INPUT",
    "hailo_hef_path": "VISION_HAILO_HEF_PATH",
    "stop_timeout_seconds": "VISION_STOP_TIMEOUT_SECONDS",
    "stale_after_seconds": "VISION_STALE_AFTER_SECONDS",
    "stream_jpeg_quality": "VISION_STREAM_JPEG_QUALITY",
    "stream_fps": "VISION_STREAM_FPS",
    "stream_max_width": "VISION_STREAM_MAX_WIDTH",
}


def _coerce(value: Any, target_type: type) -> Any:
    if value is None:
        return None
    if target_type is bool:
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    return str(value)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        log.warning("%s gefunden, aber PyYAML fehlt — ignoriert.", path.name)
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        log.warning("%s nicht lesbar: %s — ignoriert.", path.name, e)
        return {}
    if not isinstance(data, dict):
        log.warning("%s: Top-Level muss ein Mapping sein — ignoriert.", path.name)
        return {}
    if "visual" in data and isinstance(data["visual"], dict):
        return data["visual"]
    return data


def load_config(yaml_path: Path | None = None) -> VisualConfig:
    cfg = VisualConfig()
    field_types = {f.name for f in fields(cfg)}

    yaml_file = yaml_path or (Path(__file__).parent / "config.yaml")
    for name, value in _load_yaml(yaml_file).items():
        if name not in field_types:
            log.warning("Unbekanntes Feld in %s: %r — ignoriert.", yaml_file.name, name)
            continue
        try:
            setattr(cfg, name, _coerce(value, type(getattr(cfg, name))))
        except (ValueError, TypeError) as e:
            log.warning("YAML-Wert %s=%r ungültig: %s", name, value, e)

    for name, env_var in _ENV_MAP.items():
        raw = os.environ.get(env_var)
        if raw is None:
            continue
        try:
            setattr(cfg, name, _coerce(raw, type(getattr(cfg, name))))
        except (ValueError, TypeError) as e:
            log.warning("Env %s=%r ungültig: %s", env_var, raw, e)

    cfg.detector_mode = (cfg.detector_mode or "").strip().lower()
    cfg.validate()
    return cfg


CONFIG: VisualConfig = load_config()


def _print_config() -> None:
    print("Aktive Visual-Konfiguration:")
    for k, v in asdict(CONFIG).items():
        print(f"  {k:25s} = {v!r:25s}  (Env: {_ENV_MAP.get(k, '—')})")


if __name__ == "__main__":
    _print_config()
