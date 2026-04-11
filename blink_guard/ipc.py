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
import socket
import threading
import logging
import time
import base64
from typing import Any, Callable

logger = logging.getLogger("BlinkGuard")

IPC_HOST = "127.0.0.1"
IPC_PORT = 57821
BUFFER_SIZE = 1024 * 1024  # 1 MB for camera frames


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

    def _serve(self) -> None:
        """Main server loop: accept connections and handle them."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.settimeout(1.0)
            self._server_socket.bind((IPC_HOST, IPC_PORT))
            self._server_socket.listen(2)
            logger.info("IPC server listening on %s:%d", IPC_HOST, IPC_PORT)

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
        """Attempt to connect to the background process."""
        with self._lock:
            if self._connected:
                return True
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((IPC_HOST, IPC_PORT))
                self._socket = sock
                self._connected = True
                return True
            except (ConnectionRefusedError, socket.timeout, OSError):
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
