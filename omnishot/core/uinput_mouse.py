"""
OmniShot Virtual Input Device Manager
Uses /dev/uinput to inject synthetic mouse scroll events seamlessly into Wayland / KWin.
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
REL_WHEEL       = 0x08
REL_WHEEL_HI_RES= 0x0b

BTN_LEFT        = 0x110
BTN_RIGHT       = 0x111
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
            
            # Configure event types
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_REL)
            fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_WHEEL)
            fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_WHEEL_HI_RES)
            
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, BTN_LEFT)

            # Setup device info: struct uinput_setup { struct input_id id; char name[80]; __u32 ff_effects_max; };
            # format: 'HHHH80sI'
            name = b"OmniShot Virtual Scroll".ljust(80, b"\x00")
            setup_data = struct.pack("HHHH80sI", BUS_USB, 0x1234, 0x5678, 1, name, 0)
            
            fcntl.ioctl(self._fd, UI_DEV_SETUP, setup_data)
            fcntl.ioctl(self._fd, UI_DEV_CREATE)
            
            # Brief pause for kernel/udev/KWin to bind device
            time.sleep(0.05)
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
        """
        Emits mouse scroll down event.
        steps: number of discrete wheel clicks (negative is down in Linux EV_REL)
        """
        return self._emit_wheel(-abs(steps), -abs(high_res_delta))

    def scroll_up(self, steps: int = 1, high_res_delta: int = 120) -> bool:
        """Emits mouse scroll up event."""
        return self._emit_wheel(abs(steps), abs(high_res_delta))

    def _emit_wheel(self, wheel_value: int, high_res_value: int) -> bool:
        if not self._initialized or self._fd is None:
            if not self.open():
                return False

        try:
            now = time.time()
            sec = int(now)
            usec = int((now - sec) * 1_000_000)

            # struct input_event { struct timeval time; __u16 type; __u16 code; __s32 value; };
            # 64-bit: 'qqHHi' (16 + 2 + 2 + 4 = 24 bytes)
            ev_fmt = "qqHHi"
            
            # High-res wheel event
            ev_hi = struct.pack(ev_fmt, sec, usec, EV_REL, REL_WHEEL_HI_RES, high_res_value)
            # Discrete wheel event
            ev_wheel = struct.pack(ev_fmt, sec, usec, EV_REL, REL_WHEEL, wheel_value)
            # Syn report
            ev_syn = struct.pack(ev_fmt, sec, usec, EV_SYN, SYN_REPORT, 0)

            os.write(self._fd, ev_hi + ev_wheel + ev_syn)
            return True
        except Exception as e:
            print(f"[OmniShot] Failed emitting scroll event: {e}")
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
