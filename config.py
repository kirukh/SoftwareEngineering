"""
config.py — Zentrale Konfiguration für das Visual-Modul.

Auflösungsreihenfolge (späteres überschreibt früheres):
    1) Defaults aus dem Code (sicher, immer da)
    2) config.yaml im Repo-Root, falls vorhanden und PyYAML installiert
    3) Umgebungsvariablen (VISUAL_*, VISION_*)

Aufruf:
    from config import CONFIG
    print(CONFIG.port, CONFIG.detector_mode)

Aktive Werte ausgeben (zum Debuggen):
    python config.py
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, fields, asdict
from pathlib import Path
from typing import Any

log = logging.getLogger("visual.config")


# ------------------------------------------------------------------ Defaults

@dataclass
class VisualConfig:
    """Alle Tuning-Parameter des Visual-Moduls an einer Stelle.

    Range-Hinweis: Port-Range Visual ist 7991–8000 (Festlegung Prof. Jehle).
    """

    # --- Server ---
    host: str = "127.0.0.1"      # 0.0.0.0 für Netzwerk-Zugriff
    port: int = 7995             # in Range 7991–8000

    # --- Detector-Wahl ---
    detector_mode: str = ""      # "" (auto), "hailo", "yolo"

    # --- Detection-Parameter ---
    confidence_min: float = 0.5  # pro Frame
    window_size: int = 8         # Sliding-Window-Größe in Frames
    min_hits_in_window: int = 5  # Mindesttreffer für found=True

    # --- YOLO-spezifisch ---
    camera_index: int = 0        # Webcam-Index
    model_path: str = "yolov8n.pt"

    # --- Timing ---
    stop_timeout_seconds: float = 5.0  # Wait beim Tracking-Stop

    # --- MJPEG-Stream (/stream-Endpoint) ---
    stream_jpeg_quality: int = 80  # JPEG-Qualität 1–100 (höher = größer)
    stream_fps: int = 15           # max. Frames/s, die /stream ausliefert

    def validate(self) -> None:
        """Plausibilitäts-Checks. Wirft ValueError bei Quatsch."""
        if not (7991 <= self.port <= 8000):
            raise ValueError(
                f"port={self.port} außerhalb der Visual-Range 7991–8000. "
                f"Wenn das Absicht ist, passe die Range im config.py an."
            )
        if self.detector_mode not in ("", "hailo", "yolo"):
            raise ValueError(
                f"detector_mode={self.detector_mode!r} ungültig. "
                f"Erlaubt: '' (auto), 'hailo', 'yolo'."
            )
        if not (0.0 <= self.confidence_min <= 1.0):
            raise ValueError(f"confidence_min={self.confidence_min} muss in [0.0, 1.0] liegen")
        if self.window_size < 1:
            raise ValueError(f"window_size={self.window_size} muss >= 1 sein")
        if not (1 <= self.min_hits_in_window <= self.window_size):
            raise ValueError(
                f"min_hits_in_window={self.min_hits_in_window} muss in "
                f"[1, window_size={self.window_size}] liegen"
            )
        if self.camera_index < 0:
            raise ValueError(f"camera_index={self.camera_index} muss >= 0 sein")
        if self.stop_timeout_seconds <= 0:
            raise ValueError(f"stop_timeout_seconds={self.stop_timeout_seconds} muss > 0 sein")
        if not (1 <= self.stream_jpeg_quality <= 100):
            raise ValueError(
                f"stream_jpeg_quality={self.stream_jpeg_quality} muss in [1, 100] liegen"
            )
        if self.stream_fps < 1:
            raise ValueError(f"stream_fps={self.stream_fps} muss >= 1 sein")


# ------------------------------------------------------------------ Quellen-Mapping

# Feldname → Env-Variable (Backwards-Kompatibilität mit bestehenden Env-Vars).
_ENV_MAP: dict[str, str] = {
    "host": "VISUAL_HOST",
    "port": "VISUAL_PORT",
    "detector_mode": "VISUAL_DETECTOR",
    "confidence_min": "VISION_CONFIDENCE_MIN",
    "window_size": "VISION_WINDOW_SIZE",
    "min_hits_in_window": "VISION_MIN_HITS_IN_WINDOW",
    "camera_index": "VISION_CAMERA_INDEX",
    "model_path": "VISION_MODEL_PATH",
    "stop_timeout_seconds": "VISION_STOP_TIMEOUT_SECONDS",
    "stream_jpeg_quality": "VISION_STREAM_JPEG_QUALITY",
    "stream_fps": "VISION_STREAM_FPS",
}


def _coerce(value: Any, target_type: type) -> Any:
    """String → richtigen Typ. Wird für Env-Variablen gebraucht."""
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
    """config.yaml lesen, wenn vorhanden und PyYAML da ist. Sonst {}."""
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        log.warning("%s gefunden, aber PyYAML nicht installiert — wird ignoriert.", path.name)
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        log.warning("%s konnte nicht gelesen werden: %s — wird ignoriert.", path.name, e)
        return {}
    if not isinstance(data, dict):
        log.warning(
            "%s: Top-Level muss ein Mapping sein, ist %s — ignoriert.",
            path.name, type(data).__name__,
        )
        return {}
    # Optional: unter 'visual:' verschachtelt, falls die Datei später team-übergreifend wird.
    if "visual" in data and isinstance(data["visual"], dict):
        return data["visual"]
    return data


# ------------------------------------------------------------------ Build

def load_config(yaml_path: Path | None = None) -> VisualConfig:
    """Config zusammenbauen: Defaults < YAML < Env."""
    cfg = VisualConfig()
    field_types = {f.name: f.type for f in fields(cfg)}

    # 1) YAML-Layer
    yaml_file = yaml_path or (Path(__file__).parent / "config.yaml")
    yaml_data = _load_yaml(yaml_file)
    for name, value in yaml_data.items():
        if name not in field_types:
            log.warning("Unbekanntes Feld in %s: %r — ignoriert.", yaml_file.name, name)
            continue
        # type-string in echten Typ auflösen ist tricky; nutzen Default-Wert als Hinweis
        default_val = getattr(cfg, name)
        try:
            setattr(cfg, name, _coerce(value, type(default_val)))
        except (ValueError, TypeError) as e:
            log.warning("YAML-Wert für %s=%r ungültig: %s — Default beibehalten.", name, value, e)

    # 2) Env-Layer
    for name, env_var in _ENV_MAP.items():
        raw = os.environ.get(env_var)
        if raw is None:
            continue
        default_val = getattr(cfg, name)
        try:
            setattr(cfg, name, _coerce(raw, type(default_val)))
        except (ValueError, TypeError) as e:
            log.warning("Env %s=%r ungültig: %s — vorigen Wert beibehalten.", env_var, raw, e)

    # detector_mode normalisieren (lower, leerstring statt None)
    cfg.detector_mode = (cfg.detector_mode or "").strip().lower()

    cfg.validate()
    return cfg


# Modulweite Instanz — wird beim ersten Import gebaut.
CONFIG: VisualConfig = load_config()


# ------------------------------------------------------------------ Debug-Helper

def _print_config() -> None:
    # Bewusst print() statt logging: das ist die CLI-Ausgabe von
    # `python config.py` und soll immer auf stdout landen, unabhängig vom
    # Log-Level.
    print("Aktive Visual-Konfiguration:")
    for k, v in asdict(CONFIG).items():
        env = _ENV_MAP.get(k, "—")
        print(f"  {k:25s} = {v!r:25s}  (Env: {env})")


if __name__ == "__main__":
    _print_config()