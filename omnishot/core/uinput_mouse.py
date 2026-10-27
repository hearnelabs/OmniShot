"""
OmniShot Virtual Input Device Manager
Uses /dev/uinput to inject synthetic mouse scroll events and keyboard scroll keys
seamlessly into Wayland / KWin.
"""

import os
import time
import fcntl
import struct
from typing import Optional

# Linux input subsystem definitions
UI_SET_EVBIT    = 0x40045564
UI_SET_KEYBIT   = 0x40045565
UI_SET_RELBIT   = 0x40045566
UI_DEV_SETUP    = 0x405c5503
UI_DEV_CREATE   = 0x5501
UI_DEV_DESTROY  = 0x5502

EV_SYN          = 0x00
EV_KEY          = 0x01
EV_REL          = 0x02

SYN_REPORT      = 0x00
REL_X           = 0x00
REL_Y           = 0x01
REL_WHEEL       = 0x08
REL_WHEEL_HI_RES= 0x0b

BTN_LEFT        = 0x110
BTN_RIGHT       = 0x111
BTN_MIDDLE      = 0x112
KEY_DOWN        = 108
KEY_PAGEDOWN    = 109
BUS_USB         = 0x03

class UInputScroller:
    def __init__(self):
        self._fd: Optional[int] = None
        self._initialized = False

    def is_available(self) -> bool:
        """Checks if /dev/uinput can be opened."""
        try:
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)
            return True
        except Exception:
            return False

    def open(self) -> bool:
        """Initializes and registers the virtual scroll device."""
        if self._initialized and self._fd is not None:
            return True

        try:
            self._fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            
            # Configure relative pointer events (REL_X, REL_Y are mandatory for KWin pointer recognition)
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_REL)
            fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_X)
            fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_Y)
            fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_WHEEL)
            fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_WHEEL_HI_RES)
            
            # Configure keys and buttons
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, BTN_LEFT)
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, BTN_RIGHT)
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, BTN_MIDDLE)
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, KEY_DOWN)
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, KEY_PAGEDOWN)

            # Setup device info: struct uinput_setup
            name = b"OmniShot Virtual Pointer & Keyboard".ljust(80, b"\x00")
            setup_data = struct.pack("HHHH80sI", BUS_USB, 0x1234, 0x5678, 1, name, 0)
            
            fcntl.ioctl(self._fd, UI_DEV_SETUP, setup_data)
            fcntl.ioctl(self._fd, UI_DEV_CREATE)
            
            # Allow kernel and KWin/libinput to bind the new device
            time.sleep(0.25)
            self._initialized = True
            return True
        except Exception as e:
            print(f"[OmniShot] Could not initialize uinput scroll device: {e}")
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except Exception:
                    pass
                self._fd = None
            return False

    def scroll_down(self, steps: int = 1, high_res_delta: int = -120) -> bool:
        """Emits mouse wheel scroll down event."""
        # Negative wheel values indicate downward rotation towards the user in EV_REL
        return self._emit_wheel(-abs(steps), -abs(high_res_delta))

    def scroll_page_down(self) -> bool:
        """Emits PageDown key event to scroll the focused window."""
        return self._emit_key(KEY_PAGEDOWN)

    def scroll_key_down(self) -> bool:
        """Emits Down Arrow key event to scroll the focused window."""
        return self._emit_key(KEY_DOWN)

    def _emit_wheel(self, wheel_value: int, high_res_value: int) -> bool:
        if not self._initialized or self._fd is None:
            if not self.open():
                return False

        try:
            now = time.time()
            sec = int(now)
            usec = int((now - sec) * 1_000_000)
            ev_fmt = "qqHHi"
            
            # High-res wheel event
            ev_hi = struct.pack(ev_fmt, sec, usec, EV_REL, REL_WHEEL_HI_RES, high_res_value)
            # Standard discrete wheel event
            ev_wheel = struct.pack(ev_fmt, sec, usec, EV_REL, REL_WHEEL, wheel_value)
            # Syn report
            ev_syn = struct.pack(ev_fmt, sec, usec, EV_SYN, SYN_REPORT, 0)

            os.write(self._fd, ev_hi + ev_wheel + ev_syn)
            return True
        except Exception as e:
            print(f"[OmniShot] Failed emitting scroll event: {e}")
            return False

    def _emit_key(self, key_code: int) -> bool:
        if not self._initialized or self._fd is None:
            if not self.open():
                return False

        try:
            now = time.time()
            sec = int(now)
            usec = int((now - sec) * 1_000_000)
            ev_fmt = "qqHHi"

            # Key press
            ev_down = struct.pack(ev_fmt, sec, usec, EV_KEY, key_code, 1)
            ev_syn1 = struct.pack(ev_fmt, sec, usec, EV_SYN, SYN_REPORT, 0)
            # Key release
            ev_up = struct.pack(ev_fmt, sec, usec + 20000, EV_KEY, key_code, 0)
            ev_syn2 = struct.pack(ev_fmt, sec, usec + 20000, EV_SYN, SYN_REPORT, 0)

            os.write(self._fd, ev_down + ev_syn1 + ev_up + ev_syn2)
            return True
        except Exception as e:
            print(f"[OmniShot] Failed emitting key event: {e}")
            return False

    def close(self):
        """Destroys virtual device and closes descriptor."""
        if self._fd is not None:
            try:
                fcntl.ioctl(self._fd, UI_DEV_DESTROY)
            except Exception:
                pass
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        self._initialized = False

    def __del__(self):
        self.close()
