# 📸 OmniShot
> **The Next-Generation Screenshot & Scrolling Capture Suite for CachyOS & KDE Plasma 6 (Wayland)**

OmniShot brings the one killer feature that **KDE Spectacle** has always been missing: **Pixel-Perfect Seamless Scrolling Capture**, built natively for **CachyOS**, **KDE Plasma 6.8+**, and **KWin Wayland**.

---

## 🌟 Why OmniShot?

KDE Spectacle is loved for its clean Plasma integration, annotation tools, and snappy workflow—but it cannot capture content beyond the screen viewport. 

OmniShot was engineered from the ground up to solve this:
1. **Flawless Scrolling Capture**: Automatically or manually scroll web pages, documents, long chat histories, terminals, and spreadsheets, stitching them with sub-millisecond C/AVX2 multi-strip correlation.
2. **Native KWin Wayland Backend**: Direct pipe-based screencopy through `org.kde.KWin.ScreenShot2` (bypassing slow portal prompts and flicker).
3. **Hardware-Level Virtual Scrolling**: Injects synthetic scroll wheel events via `/dev/uinput` directly into the Linux kernel input subsystem without requiring root/sudo passwords.
4. **Spectacle-Grade Annotator**:
   - ✏️ Pen & Translucent Highlighter
   - ➡️ Smart Directional Arrows
   - 🔲 Rectangles & ⭕ Ellipses
   - 🔢 **Numbered Step Badges (1, 2, 3...)** with auto-increment
   - 💧 **Privacy Blur & Pixelation** (hide passwords, emails, API keys)
   - 🔤 Rich draggable Text annotations
   - ✂️ Canvas Crop tool
   - ↩️ Full Undo/Redo history stack
5. **Integrated Tesseract OCR**: One-click text extraction from any capture or long scrolling document.
6. **KDE Plasma 6 Breeze Theme**: Fully styled with native Breeze dark glass aesthetics and rounded geometry.

---

## 🚀 Quick Start

OmniShot is already installed in your `~/.local/bin` and system application menus.

### Run via Terminal or KRunner (`Alt+Space`)
```bash
# Launch the main OmniShot annotator window
omnishot

# Start an Auto-Scrolling Capture session immediately
omnishot -S

# Start a Manual Scrolling Capture session
omnishot -M

# Snip a rectangular region (like Spectacle Shift+Print)
omnishot -r

# Capture full desktop workspace
omnishot -f

# Capture active window
omnishot -a

# Open an existing image in the annotator
omnishot -E ~/Pictures/Screenshots/example.png
```

---

## 📜 How Scrolling Capture Works

1. **Trigger Scrolling Capture**:
   - Click **`📜 Scrolling Capture`** in the OmniShot toolbar, or run `omnishot -S`, or select a region on screen and press **`A`** or click **`Auto-Scroll`**.
2. **Select Region**:
   - Drag a rectangle over the scrollable area (web browser, code editor, chat app, document).
3. **Watch It Stitch in Real Time**:
   - A sleek floating HUD appears alongside your capture with a live pulsing indicator, height counter, and real-time expanding miniature thumbnail.
   - **Auto Mode**: OmniShot smoothly scrolls down and captures at high frequency.
   - **Manual Mode**: You scroll with your trackpad or mouse wheel at your own pace.
4. **Finish & Edit**:
   - Press **`Enter`** (or click **`⏹ Done`**) when finished.
   - OmniShot also auto-detects when the content hits the bottom of the page!
   - The full long screenshot opens instantly in the OmniShot annotator ready to crop, blur, annotate, copy, or save!

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + C` | Copy screenshot to clipboard |
| `Ctrl + S` | Quick save to `~/Pictures/Screenshots/` |
| `Ctrl + Shift + S` | Save As... (choose location & format) |
| `Ctrl + Z` | Undo last annotation |
| `Ctrl + Y` | Redo annotation |
| `Ctrl + +` / `Ctrl + -` | Zoom in / Zoom out |
| `Ctrl + 0` | Reset zoom to 100% |
| `Enter` / `Space` | Confirm selection / Finish scrolling |
| `Esc` | Cancel capture / Dismiss overlay |

---

## ⚙️ Configuration

Configuration is stored in `~/.config/omnishot/config.json`:

```json
{
  "save_directory": "~/Pictures/Screenshots",
  "filename_template": "OmniShot_%Y%m%d_%H%M%S.png",
  "default_format": "png",
  "copy_to_clipboard_on_save": true,
  "scroll_step_pixels": 120,
  "scroll_delay_ms": 150,
  "scroll_max_frames": 80,
  "scrollbar_margin_right": 24,
  "scroll_similarity_threshold": 28.0,
  "auto_detect_end_of_scroll": true
}
```

---

## 🏗️ Architecture

```
OmniShot/
├── bin/
│   └── omnishot             # PATH executable launcher
├── native/
│   ├── stitcher.c           # Ultra-fast SIMD/AVX2 multi-strip correlation engine
│   └── Makefile             # Builds libomnishot_stitch.so
├── omnishot/
│   ├── core/
│   │   ├── capture.py       # org.kde.KWin.ScreenShot2 Wayland screencopy
│   │   ├── uinput_mouse.py  # /dev/uinput virtual wheel kernel injection
│   │   ├── stitcher.py      # Python controller bridging C stitcher to QImage
│   │   ├── ocr.py           # Tesseract OCR engine
│   │   └── config.py        # Config persistence
│   ├── ui/
│   │   ├── main_window.py   # Spectacle-style primary annotator & viewer
│   │   ├── canvas.py        # Interactive annotation canvas (pen, arrow, blur...)
│   │   ├── snip_overlay.py  # Wayland region selector with loupe magnifier
│   │   ├── scroll_hud.py    # Floating live HUD with preview thumbnail
│   │   └── theme.py         # KDE Plasma 6 Breeze Dark QSS
│   ├── cli.py               # CLI parser matching Spectacle + scroll flags
│   └── app.py               # Application coordinator
├── tests/
│   └── test_omnishot.py     # Comprehensive automated test suite
├── omnishot.desktop         # KDE application entry with restricted interfaces
├── omnishot.svg             # High-DPI Breeze vector application icon
└── README.md
```

---

*Crafted with ❤️ for CachyOS and KDE Plasma 6.*
