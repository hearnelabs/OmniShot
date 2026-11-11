"""
OmniShot Command Line Interface
Provides full command-line arguments compatible with Spectacle conventions,
plus dedicated scrolling capture flags.
"""

import sys
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer

from .core.config import OmniShotConfig
from .core.recorder import is_recording_in_progress, request_stop_active_recording
from .app import OmniShotApp

__version__ = "1.0.9"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnishot",
        description="OmniShot - Advanced KDE Plasma 6 Screenshot & Screen Recording Utility"
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    
    # Capture modes
    parser.add_argument("-e", "--editor", action="store_true", help="Launch directly into Image Editor mode")
    parser.add_argument("-S", "--scroll", action="store_true", help="Launch directly into Auto-Scrolling Capture mode")
    parser.add_argument("-M", "--manual-scroll", action="store_true", help="Launch directly into Manual Scrolling Capture mode")
    parser.add_argument("-r", "--region", action="store_true", help="Capture a rectangular region of the screen")
    parser.add_argument("-f", "--fullscreen", action="store_true", help="Capture the entire desktop workspace")
    parser.add_argument("-a", "--activewindow", action="store_true", help="Capture the currently active window")
    parser.add_argument("-l", "--launchonly", action="store_true", help="Launch GUI without taking a screenshot")
    
    # Screen Recording flags (Spectacle 6 compatible)
    parser.add_argument(
        "-R", "--record",
        nargs="?",
        const="region",
        default=None,
        choices=["region", "screen", "window", "fullscreen", "r", "s", "w"],
        help="Record screen video (modes: region, screen, window; default: region). If already recording, stops it."
    )
    parser.add_argument("--record-region", action="store_true", help="Record a rectangular region of the screen")
    parser.add_argument("--record-screen", action="store_true", help="Record the entire screen workspace")
    parser.add_argument("--record-window", action="store_true", help="Record the active window")
    parser.add_argument("--stop-record", action="store_true", help="Stop any active screen recording in progress")
    parser.add_argument("--no-audio", action="store_true", help="Disable all audio capture during recording")
    parser.add_argument("--record-audio", action="store_true", help="Include desktop/system audio in recording")
    parser.add_argument("--record-mic", action="store_true", help="Include microphone audio in recording")
    parser.add_argument("--no-cursor", action="store_true", help="Exclude mouse cursor from recording")

    # Post-processing flags
    parser.add_argument("-c", "--copy-image", action="store_true", help="Copy screenshot directly to clipboard")
    parser.add_argument("-o", "--output", metavar="FILE", type=str, help="Save screenshot to specified file path")
    parser.add_argument("-d", "--delay", metavar="MSEC", type=int, default=0, help="Delay before capture in milliseconds")
    parser.add_argument("-E", "--edit-existing", metavar="FILE", type=str, help="Open and edit an existing screenshot file")

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Fast IPC check: if user triggered a record command or --stop-record while a recording
    # is actively running, toggle/stop it immediately without launching a new GUI process.
    is_record_command = (
        args.record is not None
        or args.record_region
        or args.record_screen
        or args.record_window
        or args.stop_record
    )

    if is_record_command and is_recording_in_progress():
        print("[OmniShot] Active screen recording found. Sending stop signal...")
        if request_stop_active_recording():
            print("[OmniShot] Active screen recording stopped successfully.")
        else:
            print("[OmniShot] Failed to signal active recording.")
        sys.exit(0)
    elif args.stop_record:
        print("[OmniShot] No active screen recording in progress.")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("omnishot")
    app.setApplicationDisplayName("OmniShot")
    app.setOrganizationName("HearneLabs")
    app.setOrganizationDomain("hearnelabs.com")
    app.setDesktopFileName("omnishot")

    # Set application icon for KDE Plasma taskbar, titlebar, and launcher
    icon_path = Path(__file__).parent.parent / "omnishot.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon.fromTheme("omnishot", QIcon(str(icon_path))))

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
                    controller._show_editor_with_image(img)
                    return
            print(f"[OmniShot] Could not load image: {args.edit_existing}")
            controller.launch_interactive()
        elif is_record_command:
            # Determine record mode
            if args.record_screen:
                rec_mode = "screen"
            elif args.record_window:
                rec_mode = "window"
            elif args.record_region:
                rec_mode = "region"
            elif args.record in ("screen", "fullscreen", "s"):
                rec_mode = "screen"
            elif args.record in ("window", "w"):
                rec_mode = "window"
            else:
                rec_mode = "region"

            desktop_audio = config.record_include_desktop_audio
            if args.no_audio:
                desktop_audio = False
            elif args.record_audio:
                desktop_audio = True

            mic = config.record_include_mic
            if args.no_audio:
                mic = False
            elif args.record_mic:
                mic = True

            cursor = config.record_include_cursor
            if args.no_cursor:
                cursor = False

            controller.trigger_record(
                mode=rec_mode,
                include_desktop_audio=desktop_audio,
                include_mic=mic,
                include_cursor=cursor
            )
        elif args.editor:
            controller.show_main_window_empty()
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
            controller.launch_interactive()
        else:
            # Default action: launch Spectacle 6 in-situ floating overlay
            controller.launch_interactive()

    delay = max(0, args.delay)
    QTimer.singleShot(delay, start_action)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
