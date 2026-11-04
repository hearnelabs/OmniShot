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
    copy_to_clipboard_on_capture: bool = True
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

    # Global shortcuts (KDE Plasma 6 Wayland)
    shortcut_launch: str = "Meta+Shift+S"
    shortcut_scrolling: str = "Meta+Shift+C"
    shortcut_region: str = "Meta+Shift+R"
    shortcut_fullscreen: str = "Print"
    shortcut_window: str = "Meta+Print"
    shortcut_editor: str = "Meta+Shift+E"

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

    def apply_kde_shortcuts(self):
        """Syncs configured global shortcuts to KDE Plasma 6 via kglobalshortcutsrc and desktop entry."""
        import subprocess
        import shutil

        # 1. Update kglobalshortcutsrc via kwriteconfig6
        if shutil.which("kwriteconfig6"):
            try:
                # Write to both [services][omnishot.desktop] and fallback [omnishot.desktop]
                for grp in [["services", "omnishot.desktop"], ["omnishot.desktop"]]:
                    base_cmd = ["kwriteconfig6", "--file", "kglobalshortcutsrc"]
                    for g in grp:
                        base_cmd.extend(["--group", g])

                    subprocess.run(base_cmd + ["--key", "_launch", f"{self.shortcut_launch},none,OmniShot"], check=False)
                    subprocess.run(base_cmd + ["--key", "OpenImageEditor", f"{self.shortcut_editor},none,Open Image Editor"], check=False)
                    subprocess.run(base_cmd + ["--key", "ScrollingCapture", f"{self.shortcut_scrolling},none,Scrolling Capture (Auto)"], check=False)
                    subprocess.run(base_cmd + ["--key", "RectangularRegionScreenShot", f"{self.shortcut_region},none,Capture Rectangular Region"], check=False)
                    subprocess.run(base_cmd + ["--key", "FullScreenScreenShot", f"{self.shortcut_fullscreen},none,Capture Entire Desktop"], check=False)
                    subprocess.run(base_cmd + ["--key", "ActiveWindowScreenShot", f"{self.shortcut_window},none,Capture Active Window"], check=False)
            except Exception as e:
                print(f"[OmniShot] Warning: Could not update kglobalshortcutsrc: {e}")

        # 2. Update .desktop file with X-KDE-Shortcuts across all actions
        desktop_file = Path.home() / ".local/share/applications/omnishot.desktop"
        if desktop_file.exists():
            try:
                action_shortcuts = {
                    "[Desktop Entry]": self.shortcut_launch,
                    "[Desktop Action OpenImageEditor]": self.shortcut_editor,
                    "[Desktop Action ScrollingCapture]": self.shortcut_scrolling,
                    "[Desktop Action RectangularRegionScreenShot]": self.shortcut_region,
                    "[Desktop Action FullScreenScreenShot]": self.shortcut_fullscreen,
                    "[Desktop Action ActiveWindowScreenShot]": self.shortcut_window,
                }
                lines = desktop_file.read_text(encoding="utf-8").splitlines()
                new_lines = []
                current_section = ""
                has_shortcut_in_section = False

                for line in lines:
                    if line.startswith("[") and line.endswith("]"):
                        if current_section in action_shortcuts and not has_shortcut_in_section:
                            new_lines.append(f"X-KDE-Shortcuts={action_shortcuts[current_section]}")
                        current_section = line
                        has_shortcut_in_section = False
                        new_lines.append(line)
                    elif line.startswith("X-KDE-Shortcuts="):
                        if current_section in action_shortcuts:
                            new_lines.append(f"X-KDE-Shortcuts={action_shortcuts[current_section]}")
                            has_shortcut_in_section = True
                    else:
                        new_lines.append(line)

                if current_section in action_shortcuts and not has_shortcut_in_section:
                    new_lines.append(f"X-KDE-Shortcuts={action_shortcuts[current_section]}")

                desktop_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            except Exception as e:
                print(f"[OmniShot] Warning: Could not update desktop entry: {e}")

        # 3. Direct D-Bus registration with org.kde.kglobalaccel for instant live activation
        try:
            import dbus
            bus = dbus.SessionBus()
            kg = bus.get_object("org.kde.kglobalaccel", "/kglobalaccel")
            iface = dbus.Interface(kg, "org.kde.KGlobalAccel")

            from PySide6.QtGui import QKeySequence

            shortcuts_map = [
                ("_launch", "OmniShot", self.shortcut_launch),
                ("OpenImageEditor", "Open Image Editor", self.shortcut_editor),
                ("ScrollingCapture", "Scrolling Capture (Auto)", self.shortcut_scrolling),
                ("RectangularRegionScreenShot", "Capture Rectangular Region", self.shortcut_region),
                ("FullScreenScreenShot", "Capture Entire Desktop", self.shortcut_fullscreen),
                ("ActiveWindowScreenShot", "Capture Active Window", self.shortcut_window),
            ]
            for action_name, label, seq_str in shortcuts_map:
                action_id = ["omnishot.desktop", action_name, "OmniShot", label]
                iface.doRegister(action_id)
                if seq_str and seq_str.lower() != "none":
                    ks = QKeySequence(seq_str)
                    if ks.count() > 0:
                        key_int = int(ks[0].toCombined())
                        iface.setForeignShortcut(action_id, dbus.Array([dbus.Int32(key_int)], signature="i"))
        except Exception:
            pass

        # 4. Reload KDE system configuration cache
        if shutil.which("kbuildsycoca6"):
            try:
                subprocess.run(["kbuildsycoca6", "--noincremental"], check=False)
            except Exception:
                pass

