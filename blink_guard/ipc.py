"""
ipc.py — Inter-Process Communication between BlinkGuard background and dashboard.

Protocol:
  - TCP socket on localhost:57821
  - Newline-delimited JSON messages
  - Background process runs the server; dashboard connects as client.

Message types (client → server):
  GET_LIVE_STATE           → returns current live stats
  GET_CAMERA_FRAME         → returns JPEG-encoded camera frame (base64)
  SET_SETTING {key, value} → updates a setting in the background process
  PAUSE                    → pause detection
  RESUME                   → resume detection
  LAUNCH_CONFIRMED         → no-op, just checks if background is alive

Message types (server → client):
  JSON response with requested data or {"ok": true}
"""

import json
import os
import socket
import threading
import logging
import time
import base64
from typing import Any, Callable

logger = logging.getLogger("BlinkGuard")

IPC_HOST = "127.0.0.1"
IPC_PORT = 57821
IPC_PORTS = [57821, 57822, 57823, 57824, 57825]
BUFFER_SIZE = 1024 * 1024  # 1 MB for camera frames


def _port_file_path() -> str:
    """Return path to the blinkguard.port lock file."""
    from blink_guard.defaults import settings_path
    return os.path.join(os.path.dirname(settings_path()), "blinkguard.port")


def _write_port_file(port: int) -> None:
    """Write the active IPC port to a lock file."""
    try:
        with open(_port_file_path(), "w") as f:
            f.write(str(port))
    except OSError:
        logger.warning("Failed to write port file.")


def _read_port_file() -> int | None:
    """Read the IPC port from the lock file. Returns None if not found."""
    try:
        with open(_port_file_path(), "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def _remove_port_file() -> None:
    """Remove the port lock file."""
    try:
        os.remove(_port_file_path())
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("Failed to remove port file.")


# ---------------------------------------------------------------------------
# Server (runs in the background process)
# ---------------------------------------------------------------------------

class IPCServer:
    """TCP server that listens for dashboard connections."""

    def __init__(self, get_state_callback: Callable[[], dict],
                 get_frame_callback: Callable[[], bytes | None],
                 command_callback: Callable[[str, dict], dict]):
        """
        Args:
            get_state_callback: returns dict of current live state
            get_frame_callback: returns JPEG bytes of current camera frame or None
            command_callback: handles commands (PAUSE, RESUME, SET_SETTING, etc.)
        """
        self._get_state = get_state_callback
        self._get_frame = get_frame_callback
        self._on_command = command_callback
        self._server_socket: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the IPC server in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._serve, name="IPCServer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the IPC server."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        _remove_port_file()

    def _serve(self) -> None:
        """Main server loop: try ports in order, accept connections."""
        bound_port = None
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.settimeout(1.0)

            # Try each port until one works
            for port in IPC_PORTS:
                try:
                    self._server_socket.bind((IPC_HOST, port))
                    bound_port = port
                    break
                except OSError:
                    logger.info("Port %d unavailable, trying next...", port)
                    # Need a fresh socket for the next attempt
                    self._server_socket.close()
                    self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self._server_socket.settimeout(1.0)

            if bound_port is None:
                logger.error("IPC server: all ports %s are occupied!", IPC_PORTS)
                return

            self._server_socket.listen(2)
            _write_port_file(bound_port)
            logger.info("IPC server listening on %s:%d", IPC_HOST, bound_port)

            while self._running:
                try:
                    conn, addr = self._server_socket.accept()
                    handler = threading.Thread(
                        target=self._handle_client, args=(conn,),
                        name="IPCClient", daemon=True
                    )
                    handler.start()
                except socket.timeout:
                    continue
                except OSError:
                    if self._running:
                        logger.exception("IPC server accept error")
                    break
        except OSError:
            logger.exception("IPC server failed to bind")
        finally:
            if self._server_socket:
                try:
                    self._server_socket.close()
                except OSError:
                    pass

    def _handle_client(self, conn: socket.socket) -> None:
        """Handle a single client connection — read messages line by line."""
        conn.settimeout(5.0)
        buf = b""
        try:
            while self._running:
                try:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        response = self._process_message(line.decode("utf-8", errors="replace"))
                        resp_bytes = (json.dumps(response) + "\n").encode("utf-8")
                        conn.sendall(resp_bytes)
                except socket.timeout:
                    continue
                except (ConnectionResetError, BrokenPipeError):
                    break
        except Exception:
            logger.exception("IPC client handler error")
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _process_message(self, raw: str) -> dict:
        """Parse and dispatch a client message."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return {"error": "invalid JSON"}

        cmd = msg.get("command", "").upper()

        if cmd == "GET_LIVE_STATE":
            return self._get_state()

        elif cmd == "GET_CAMERA_FRAME":
            frame = self._get_frame()
            if frame is not None:
                return {"frame": base64.b64encode(frame).decode("ascii")}
            return {"frame": None}

        elif cmd in ("PAUSE", "RESUME", "SET_SETTING", "LAUNCH_CONFIRMED"):
            return self._on_command(cmd, msg)

        else:
            return {"error": f"unknown command: {cmd}"}


# ---------------------------------------------------------------------------
# Client (runs in the dashboard process)
# ---------------------------------------------------------------------------

class IPCClient:
    """TCP client that connects to the BlinkGuard background IPC server."""

    def __init__(self):
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """Attempt to connect to the background process.

        Reads the port file first, then falls back to scanning all known ports.
        """
        with self._lock:
            if self._connected:
                return True

            # Try the port file first
            ports_to_try = []
            file_port = _read_port_file()
            if file_port is not None:
                ports_to_try.append(file_port)
            # Then try all known ports (excluding the one we already tried)
            for p in IPC_PORTS:
                if p not in ports_to_try:
                    ports_to_try.append(p)

            for port in ports_to_try:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.3)
                    sock.connect((IPC_HOST, port))
                    self._socket = sock
                    self._connected = True
                    return True
                except (ConnectionRefusedError, socket.timeout, OSError):
                    try:
                        sock.close()
                    except OSError:
                        pass
                    continue

            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close connection."""
        with self._lock:
            self._connected = False
            if self._socket:
                try:
                    self._socket.close()
                except OSError:
                    pass
                self._socket = None

    def send(self, message: dict) -> dict | None:
        """Send a JSON message and wait for a JSON response."""
        with self._lock:
            if not self._connected or not self._socket:
                return None
            try:
                raw = (json.dumps(message) + "\n").encode("utf-8")
                self._socket.sendall(raw)

                # Read response (may come in chunks)
                buf = b""
                self._socket.settimeout(3.0)
                while b"\n" not in buf:
                    chunk = self._socket.recv(BUFFER_SIZE)
                    if not chunk:
                        self._connected = False
                        return None
                    buf += chunk
                line = buf.split(b"\n", 1)[0]
                return json.loads(line.decode("utf-8", errors="replace"))
            except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError):
                self._connected = False
                self._socket = None
                return None
            except json.JSONDecodeError:
                return None

    def get_live_state(self) -> dict | None:
        """Convenience: fetch live state from background."""
        return self.send({"command": "GET_LIVE_STATE"})

    def get_camera_frame(self) -> bytes | None:
        """Convenience: fetch a camera frame (JPEG) from background."""
        resp = self.send({"command": "GET_CAMERA_FRAME"})
        if resp and resp.get("frame"):
            return base64.b64decode(resp["frame"])
        return None

    def pause(self) -> dict | None:
        return self.send({"command": "PAUSE"})

    def resume(self) -> dict | None:
        return self.send({"command": "RESUME"})

    def set_setting(self, key: str, value: Any) -> dict | None:
        return self.send({"command": "SET_SETTING", "key": key, "value": value})


# ---------------------------------------------------------------------------
# IPC callback factory
# ---------------------------------------------------------------------------

def build_ipc_callbacks(shared):
    """Create IPC callback functions that read from SharedState.

    Returns (get_state, get_frame, handle_command) suitable for IPCServer.
    """
    from blink_guard.state import DetectorState, Phase

    def get_state() -> dict:
        avg_interval = shared.get_avg_blink_interval()
        with shared.lock:
            return {
                "blink_count": shared.session_blink_count,
                "avg_interval": avg_interval,
                "last_blink_ms_ago": int((time.time() - shared.last_blink_time) * 1000),
                "ear_left": shared.ear_left,
                "ear_right": shared.ear_right,
                "ear_history": list(shared.ear_history),
                "alerts_fired": shared.session_alerts_fired,
                "phase": shared.phase.value,
                "current_threshold": shared.current_threshold,
                "face_detected": shared.detector_state != DetectorState.FACE_NOT_VISIBLE,
                "escalation_level": shared.escalation_level,
                "dnd_active": shared.dnd_active,
                "dnd_end_time": shared.dnd_end_time,
                "escalation_counts": dict(shared.escalation_counts),
            }

    def get_frame() -> bytes | None:
        return shared.last_jpeg_frame

    def handle_command(cmd: str, msg: dict) -> dict:
        if cmd == "PAUSE":
            shared.set_detector_state(DetectorState.PAUSED)
            return {"ok": True}
        elif cmd == "RESUME":
            shared.set_detector_state(DetectorState.WATCHING)
            return {"ok": True}
        elif cmd == "SET_SETTING":
            key = msg.get("key")
            value = msg.get("value")
            allowed_keys = (
                "sound_enabled", "launch_on_startup",
                "alert_volume", "volume", "camera_index",
                "ear_threshold", "ear_blink_threshold", "ear_open_threshold",
                "show_landmarks",
                "total_sessions_planned", "target_threshold",
                "phase", "baseline_interval",
                "sessions_completed", "current_threshold",
                "maintenance_sessions",
                "alert_sound", "custom_sound_path",
                "dnd_enabled", "dnd_schedule",
                "calibrated", "calibration_date",
            )
            if key and key in allowed_keys:
                with shared.lock:
                    shared.settings[key] = value
                    if key == "sound_enabled":
                        shared.sound_enabled = bool(value)
                    elif key == "launch_on_startup":
                        shared.launch_on_startup = bool(value)
                    elif key == "phase":
                        shared.phase = Phase(value)
                    elif key == "baseline_interval":
                        shared.baseline_interval = value
                    elif key == "current_threshold":
                        shared.current_threshold = value
                shared.save_settings()
                return {"ok": True}
            return {"error": f"unknown setting: {key}"}
        elif cmd == "LAUNCH_CONFIRMED":
            return {"ok": True}
        return {"error": f"unhandled: {cmd}"}

    return get_state, get_frame, handle_command
