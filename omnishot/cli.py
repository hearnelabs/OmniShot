"""
OmniShot Command Line Interface
Provides full command-line arguments compatible with Spectacle conventions,
plus dedicated scrolling capture flags.
"""

import sys
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from .core.config import OmniShotConfig
from .app import OmniShotApp

__version__ = "1.0.0"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnishot",
        description="OmniShot - Advanced KDE Plasma 6 Screenshot & Scrolling Capture Utility"
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    
    # Capture modes
    parser.add_argument("-S", "--scroll", action="store_true", help="Launch directly into Auto-Scrolling Capture mode")
    parser.add_argument("-M", "--manual-scroll", action="store_true", help="Launch directly into Manual Scrolling Capture mode")
    parser.add_argument("-r", "--region", action="store_true", help="Capture a rectangular region of the screen")
    parser.add_argument("-f", "--fullscreen", action="store_true", help="Capture the entire desktop workspace")
    parser.add_argument("-a", "--activewindow", action="store_true", help="Capture the currently active window")
    parser.add_argument("-l", "--launchonly", action="store_true", help="Launch GUI without taking a screenshot")
    
    # Post-processing flags
    parser.add_argument("-c", "--copy-image", action="store_true", help="Copy screenshot directly to clipboard")
    parser.add_argument("-o", "--output", metavar="FILE", type=str, help="Save screenshot to specified file path")
    parser.add_argument("-d", "--delay", metavar="MSEC", type=int, default=0, help="Delay before capture in milliseconds")
    parser.add_argument("-E", "--edit-existing", metavar="FILE", type=str, help="Open and edit an existing screenshot file")

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("OmniShot")
    app.setApplicationDisplayName("OmniShot")
    app.setOrganizationName("HearneLabs")
    app.setOrganizationDomain("hearnelabs.com")

    config = OmniShotConfig.load()
    controller = OmniShotApp(app, config)

    # Determine initial action
    def start_action():
        if args.edit_existing:
            from PySide6.QtGui import QImage
            path = Path(args.edit_existing).expanduser().resolve()
            if path.exists():
                img = QImage(str(path))
                if not img.isNull():
                    controller.main_window.set_captured_image(img)
                    return
            print(f"[OmniShot] Could not load image: {args.edit_existing}")
            controller.show_main_window()
        elif args.scroll:
            controller.trigger_capture("scroll_auto")
        elif args.manual_scroll:
            controller.trigger_capture("scroll_manual")
        elif args.region:
            controller.trigger_capture("region")
        elif args.fullscreen:
            controller.trigger_capture("fullscreen")
        elif args.activewindow:
            controller.trigger_capture("window")
        elif args.launchonly:
            controller.show_main_window()
        else:
            # Default action: show main window with quick action options
            controller.show_main_window()

    delay = max(0, args.delay)
    QTimer.singleShot(delay, start_action)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
