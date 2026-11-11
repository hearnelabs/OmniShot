"""
OmniShot Native Screen Recording Backend (KDE Plasma 6 / Wayland)
High-performance screen, region, and window video recording with:
- Zero-copy hardware accelerated frame acquisition via KWin ScreenShot2
- Crystal-clear audio capture (Desktop Audio via PipeWire/Pulse sink monitor + Microphone)
- FFmpeg H.264 / AAC MP4 or VP9 / Opus WebM encoding
- Global start/stop toggle IPC via Unix domain socket
- Live desktop notifications with Open Folder & Play Video actions
"""

import os
import sys
import time
import signal
import socket
import threading
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal, QTimer, QRect, QPoint, Qt
from PySide6.QtGui import QImage, QPainter, QCursor, QColor, QPen, QGuiApplication

from .config import OmniShotConfig
from .capture import get_capture_backend, KWinCaptureBackend
from .clipboard import copy_text_to_clipboard


def get_recorder_socket_path() -> Path:
    """Returns the user runtime socket path for recording IPC."""
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime and Path(xdg_runtime).is_dir():
        return Path(xdg_runtime) / "omnishot_recorder.sock"
    cache_dir = Path.home() / ".cache" / "omnishot"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "recorder.sock"


def is_recording_in_progress() -> bool:
    """Checks if another OmniShot recording process is currently active."""
    sock_path = get_recorder_socket_path()
    if not sock_path.exists():
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(str(sock_path))
        s.sendall(b"PING\n")
        resp = s.recv(1024)
        s.close()
        return resp.startswith(b"PONG")
    except Exception:
        # Stale socket file
        try:
            sock_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def request_stop_active_recording() -> bool:
    """Sends a STOP command to any currently running recording session."""
    sock_path = get_recorder_socket_path()
    if not sock_path.exists():
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect(str(sock_path))
        s.sendall(b"STOP\n")
        resp = s.recv(1024)
        s.close()
        return b"OK" in resp
    except Exception as e:
        print(f"[OmniShot] Could not signal active recording: {e}")
        return False


class CaptureWorkerThread(QThread):
    """Pumps captured screen frames into FFmpeg rawvideo stdin at steady target FPS."""
    frameCaptured = Signal()
    workerError = Signal(str)

    def __init__(
        self,
        rect: QRect,
        fps: int,
        stdin_pipe,
        include_cursor: bool = True,
        target_w: Optional[int] = None,
        target_h: Optional[int] = None,
        first_frame: Optional[QImage] = None,
        parent=None
    ):
        super().__init__(parent)
        self.rect = rect
        self.fps = fps
        self.stdin_pipe = stdin_pipe
        self.include_cursor = include_cursor
        self._running = True
        self._paused = False
        self.backend = get_capture_backend()
        self.target_w = target_w or ((rect.width() // 2) * 2)
        self.target_h = target_h or ((rect.height() // 2) * 2)
        self.first_frame = first_frame

    def set_paused(self, paused: bool):
        self._paused = paused

    def stop(self):
        self._running = False
        self.wait(1500)

    def run(self):
        w, h = self.rect.width(), self.rect.height()
        rx, ry = self.rect.x(), self.rect.y()
        frame_interval = 1.0 / max(1, self.fps)
        expected_len = self.target_w * self.target_h * 4

        def write_frame(img: QImage):
            if img.width() != self.target_w or img.height() != self.target_h:
                img = img.copy(0, 0, self.target_w, self.target_h)

            if self.include_cursor:
                cur_pos = QCursor.pos()
                if self.rect.contains(cur_pos):
                    # Scale cursor coordinates from logical to physical
                    scale_x = self.target_w / max(1, w)
                    scale_y = self.target_h / max(1, h)
                    cx = int((cur_pos.x() - rx) * scale_x)
                    cy = int((cur_pos.y() - ry) * scale_y)

                    p = QPainter(img)
                    p.setPen(QPen(QColor(0, 0, 0), 2))
                    p.setBrush(QColor(255, 255, 255))
                    points = [
                        QPoint(cx, cy),
                        QPoint(cx, cy + 16),
                        QPoint(cx + 4, cy + 12),
                        QPoint(cx + 9, cy + 19),
                        QPoint(cx + 12, cy + 18),
                        QPoint(cx + 7, cy + 11),
                        QPoint(cx + 13, cy + 11),
                    ]
                    p.drawPolygon(points)
                    p.end()

            if img.format() != QImage.Format.Format_RGBA8888:
                img = img.convertToFormat(QImage.Format.Format_RGBA8888)

            if img.bytesPerLine() == self.target_w * 4:
                raw_bytes = bytes(img.constBits())[:expected_len]
            else:
                raw_bytes = b"".join(bytes(img.scanLine(y))[:self.target_w * 4] for y in range(self.target_h))

            if self._running and self.stdin_pipe and not self.stdin_pipe.closed:
                self.stdin_pipe.write(raw_bytes)
                self.stdin_pipe.flush()
                self.frameCaptured.emit()

        # Emit probe frame as frame #1 if available
        if self.first_frame and not self.first_frame.isNull():
            try:
                write_frame(self.first_frame)
            except Exception:
                pass
            self.first_frame = None

        t_next = time.time()

        while self._running:
            now = time.time()
            if now < t_next:
                sleep_sec = t_next - now
                if sleep_sec > 0.001:
                    time.sleep(sleep_sec)

            t_next += frame_interval
            # Prevent falling behind if capture took longer
            if t_next < time.time() - frame_interval:
                t_next = time.time()

            if self._paused:
                time.sleep(0.05)
                continue

            try:
                img = self.backend.capture_area(rx, ry, w, h)
                if not img or img.isNull():
                    continue

                write_frame(img)
            except BrokenPipeError:
                break
            except Exception as e:
                if self._running:
                    self.workerError.emit(str(e))
                break


class ScreenRecordingSession(QObject):
    """
    Manages complete screen recording lifecycle:
    - FFmpeg process management with Pulse/PipeWire audio mixing
    - Multi-threaded video frame streaming
    - Elapsed timer and pause/resume states
    - Notification and clipboard persistence
    """
    timeUpdated = Signal(int) # elapsed seconds
    stateChanged = Signal(str) # 'recording', 'paused', 'stopped'
    recordingFinished = Signal(str) # output file path
    recordingFailed = Signal(str)

    def __init__(
        self,
        rect: QRect,
        mode: str = "region",
        include_desktop_audio: bool = True,
        include_mic: bool = False,
        include_cursor: bool = True,
        config: Optional[OmniShotConfig] = None,
        parent=None
    ):
        super().__init__(parent)
        self.rect = rect
        # Ensure dimensions are even numbers for x264/yuv420p
        w = (rect.width() // 2) * 2
        h = (rect.height() // 2) * 2
        if w != rect.width() or h != rect.height():
            self.rect = QRect(rect.x(), rect.y(), max(2, w), max(2, h))

        self.mode = mode
        self.include_desktop_audio = include_desktop_audio
        self.include_mic = include_mic
        self.include_cursor = include_cursor
        self.config = config or OmniShotConfig.load()

        self.fps = self.config.record_fps or 30
        self.format = (self.config.record_format or "mp4").lower()
        self.output_dir = Path(self.config.record_directory or str(Path.home() / "Videos" / "Recordings"))
        self.output_path: Optional[Path] = None
        self.backend = get_capture_backend()
        self.target_w = (self.rect.width() // 2) * 2
        self.target_h = (self.rect.height() // 2) * 2

        self.ffmpeg_proc: Optional[subprocess.Popen] = None
        self.worker: Optional[CaptureWorkerThread] = None

        self._is_recording = False
        self._is_paused = False
        self._elapsed_seconds = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_timer_tick)

        self._server_sock: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Initializes output path, launches FFmpeg and starts capture thread."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[OmniShot] Could not create recordings directory {self.output_dir}: {e}")
            self.output_dir = Path.home() / "Videos"
            self.output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        ext = "webm" if self.format == "webm" else "mp4"
        self.output_path = self.output_dir / f"OmniShot_{timestamp}.{ext}"

        # Probe physical frame dimensions from compositor (crucial for fractional DPI / Wayland scaling)
        probe = None
        try:
            probe = self.backend.capture_area(self.rect.x(), self.rect.y(), self.rect.width(), self.rect.height())
        except Exception:
            pass

        if probe and not probe.isNull():
            actual_w = (probe.width() // 2) * 2
            actual_h = (probe.height() // 2) * 2
        else:
            actual_w = (self.rect.width() // 2) * 2
            actual_h = (self.rect.height() // 2) * 2

        self.target_w = actual_w
        self.target_h = actual_h

        # Build FFmpeg command line with exact physical dimensions
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{actual_w}x{actual_h}",
            "-pix_fmt", "rgba",
            "-r", str(self.fps),
            "-i", "-"
        ]

        # Audio inputs via PipeWire/Pulse
        has_audio = False
        if self.include_desktop_audio and self.include_mic:
            has_audio = True
            cmd.extend([
                "-f", "pulse", "-i", "@DEFAULT_SINK@.monitor",
                "-f", "pulse", "-i", "@DEFAULT_SOURCE@",
                "-filter_complex", "amix=inputs=2:duration=longest"
            ])
        elif self.include_desktop_audio:
            has_audio = True
            cmd.extend(["-f", "pulse", "-i", "@DEFAULT_SINK@.monitor"])
        elif self.include_mic:
            has_audio = True
            cmd.extend(["-f", "pulse", "-i", "@DEFAULT_SOURCE@"])

        # Encoders & Container options
        if ext == "webm":
            cmd.extend([
                "-c:v", "libvpx-vp9",
                "-b:v", "0",
                "-crf", "28",
                "-deadline", "realtime",
                "-cpu-used", "8",
                "-pix_fmt", "yuv420p"
            ])
            if has_audio:
                cmd.extend(["-c:a", "libopus", "-b:a", "128k"])
        else: # mp4
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"
            ])
            if has_audio:
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd.append(str(self.output_path))

        try:
            self.ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            err_msg = f"Failed to launch FFmpeg: {e}"
            print(f"[OmniShot] {err_msg}")
            self.recordingFailed.emit(err_msg)
            return False

        # Launch frame worker thread
        self.worker = CaptureWorkerThread(
            rect=self.rect,
            fps=self.fps,
            stdin_pipe=self.ffmpeg_proc.stdin,
            include_cursor=self.include_cursor,
            target_w=actual_w,
            target_h=actual_h,
            first_frame=probe,
            parent=self
        )
        self.worker.workerError.connect(self._on_worker_error)
        self.worker.start()

        # Start IPC socket server for global hotkey toggling
        self._start_ipc_server()

        self._is_recording = True
        self._is_paused = False
        self._elapsed_seconds = 0
        self._timer.start()
        self.stateChanged.emit("recording")
        print(f"[OmniShot] Screen recording started -> {self.output_path}")
        return True

    def _start_ipc_server(self):
        sock_path = get_recorder_socket_path()
        sock_path.unlink(missing_ok=True)
        try:
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(str(sock_path))
            self._server_sock.listen(2)

            def listen_loop():
                while self._is_recording and self._server_sock:
                    try:
                        conn, _ = self._server_sock.accept()
                        data = conn.recv(1024)
                        if b"PING" in data:
                            conn.sendall(b"PONG\n")
                        elif b"STOP" in data:
                            conn.sendall(b"OK\n")
                            conn.close()
                            # Safely schedule stop on Qt thread
                            QTimer.singleShot(0, self.stop)
                            break
                        conn.close()
                    except Exception:
                        break

            self._server_thread = threading.Thread(target=listen_loop, daemon=True)
            self._server_thread.start()
        except Exception as e:
            print(f"[OmniShot] Notice: Could not bind recorder IPC socket: {e}")

    def _close_ipc_server(self):
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        sock_path = get_recorder_socket_path()
        try:
            sock_path.unlink(missing_ok=True)
        except Exception:
            pass

    def _on_timer_tick(self):
        if self._is_recording and not self._is_paused:
            self._elapsed_seconds += 1
            self.timeUpdated.emit(self._elapsed_seconds)

    def pause(self):
        if not self._is_recording or self._is_paused:
            return
        self._is_paused = True
        if self.worker:
            self.worker.set_paused(True)
        self.stateChanged.emit("paused")
        print("[OmniShot] Screen recording paused")

    def resume(self):
        if not self._is_recording or not self._is_paused:
            return
        self._is_paused = False
        if self.worker:
            self.worker.set_paused(False)
        self.stateChanged.emit("recording")
        print("[OmniShot] Screen recording resumed")

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_active(self) -> bool:
        return self._is_recording

    def toggle_pause(self):
        if self._is_paused:
            self.resume()
        else:
            self.pause()

    def stop(self):
        """Finalizes the video file, cleans up worker, and posts notification."""
        if not self._is_recording:
            return
        self._is_recording = False
        self._timer.stop()
        self._close_ipc_server()

        # Stop worker thread
        if self.worker:
            self.worker.stop()
            self.worker = None

        # Finalize FFmpeg
        if self.ffmpeg_proc:
            try:
                if self.ffmpeg_proc.stdin and not self.ffmpeg_proc.stdin.closed:
                    try:
                        self.ffmpeg_proc.stdin.close()
                    except Exception:
                        pass
                # Send SIGINT so FFmpeg gracefully stops audio/video capture and writes moov atom
                self.ffmpeg_proc.send_signal(signal.SIGINT)
                self.ffmpeg_proc.wait(timeout=4)
            except Exception as e:
                print(f"[OmniShot] Warning waiting for FFmpeg: {e}")
                try:
                    self.ffmpeg_proc.terminate()
                except Exception:
                    pass
            self.ffmpeg_proc = None

        self.stateChanged.emit("stopped")

        if self.output_path and self.output_path.exists() and self.output_path.stat().st_size > 500:
            print(f"[OmniShot] Recording successfully saved to {self.output_path}")
            # 1. Copy file path to clipboard
            copy_text_to_clipboard(str(self.output_path))

            # 2. Show desktop notification
            self._send_notification(self.output_path)

            self.recordingFinished.emit(str(self.output_path))
        else:
            err = "Recording failed: Video file was empty or missing."
            print(f"[OmniShot] {err}")
            self.recordingFailed.emit(err)

    def cancel(self):
        """Discards active recording and removes partial file."""
        if not self._is_recording:
            return
        self._is_recording = False
        self._timer.stop()
        self._close_ipc_server()

        if self.worker:
            self.worker.stop()
            self.worker = None

        if self.ffmpeg_proc:
            try:
                self.ffmpeg_proc.kill()
            except Exception:
                pass
            self.ffmpeg_proc = None

        if self.output_path and self.output_path.exists():
            try:
                self.output_path.unlink()
            except Exception:
                pass

        self.stateChanged.emit("stopped")
        print("[OmniShot] Screen recording cancelled and discarded")

    def _on_worker_error(self, err: str):
        print(f"[OmniShot] Recording worker error: {err}")
        self.stop()

    def _send_notification(self, file_path: Path):
        """Dispatches an interactive KDE Plasma notification with action buttons."""
        try:
            # Run non-blocking notify-send with Open Folder and Play actions
            title = "Screen Recording Saved"
            body = f"Saved to {file_path.name}"
            
            def notify_worker():
                cmd = [
                    "notify-send",
                    "-a", "OmniShot",
                    "-i", "video-x-generic",
                    title,
                    body,
                    "-A", "open=Open Folder",
                    "-A", "play=Play Video"
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                stdout, _ = proc.communicate()
                action = stdout.strip()
                if action in ("open", "0"):
                    subprocess.run(["xdg-open", str(file_path.parent)], check=False)
                elif action in ("play", "1"):
                    subprocess.run(["xdg-open", str(file_path)], check=False)

            threading.Thread(target=notify_worker, daemon=True).start()
        except Exception as e:
            print(f"[OmniShot] Could not send desktop notification: {e}")
