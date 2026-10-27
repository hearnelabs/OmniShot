"""
OmniShot Configuration Manager
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict

CONFIG_DIR = Path.home() / ".config" / "omnishot"
CONFIG_FILE = CONFIG_DIR / "config.json"

@dataclass
class OmniShotConfig:
    save_directory: str = str(Path.home() / "Pictures" / "Screenshots")
    filename_template: str = "OmniShot_%Y%m%d_%H%M%S.png"
    default_format: str = "png"
    copy_to_clipboard_on_save: bool = True
    copy_to_clipboard_on_capture: bool = False
    notify_on_save: bool = True
    
    # Scrolling Capture settings
    scroll_step_pixels: int = 120
    scroll_delay_ms: int = 150
    scroll_max_frames: int = 80
    scroll_max_height: int = 30000
    scrollbar_margin_right: int = 24
    header_margin_top: int = 0
    footer_margin_bottom: int = 0
    scroll_similarity_threshold: float = 28.0
    auto_detect_end_of_scroll: bool = True

    # Editor appearance
    theme_mode: str = "auto" # auto, dark, light
    default_annotation_color: str = "#e74c3c" # KDE vibrant red/crimson
    default_stroke_width: int = 4
    default_font_size: int = 18

    @classmethod
    def load(cls) -> "OmniShotConfig":
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
        except Exception as e:
            print(f"[OmniShot] Warning: Could not read config file ({e}), using defaults")
            return cls()

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            print(f"[OmniShot] Error saving config: {e}")
