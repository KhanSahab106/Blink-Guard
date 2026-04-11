"""
state.py — Shared state between threads.

Defines enums for application phase and detector state, and a thread-safe
SharedState container that all threads read from / write to.
"""

import enum
import threading
import time
import logging

from blink_guard.defaults import (
    load_settings_from_disk,
    save_settings_to_disk,
)

logger = logging.getLogger("BlinkGuard")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Phase(enum.Enum):
    """High-level training phase."""
    OBSERVING = "observing"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    WEAN_OFF = "wean_off"


class DetectorState(enum.Enum):
    """Real-time detector status."""
    WATCHING = "watching"
    BLINK_DETECTED = "blink_detected"
    FACE_NOT_VISIBLE = "face_not_visible"
    PAUSED = "paused"


# ---------------------------------------------------------------------------
# Shared State
# ---------------------------------------------------------------------------

class SharedState:
    """Thread-safe container for all shared runtime data.

    Every public attribute is guarded by ``lock``.  Callers should use the
    helper methods (``record_blink``, ``set_detector_state``, etc.) instead
    of touching fields directly whenever possible.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()

        # --- Detector state ---
        self.detector_state: DetectorState = DetectorState.FACE_NOT_VISIBLE

        # --- Phase ---
        self.phase: Phase = Phase.OBSERVING

        # --- Blink data ---
        self.blink_timestamps: list[float] = []
        self.last_blink_time: float = time.time()

        # --- Adaptive thresholds ---
        self.current_threshold: float | None = None
        self.baseline_interval: float | None = None

        # --- Session stats (current session) ---
        self.session_start_time: float = time.time()
        self.session_blink_count: int = 0
        self.session_alerts_fired: int = 0

        # --- Wean-off tracking ---
        self.consecutive_misses: int = 0

        # --- User preferences ---
        self.sound_enabled: bool = True
        self.launch_on_startup: bool = True

        # --- Full settings dict (for persistence) ---
        self.settings: dict = {}

        # --- IPC / detector data (previously set dynamically in main.py) ---
        self.ear_left: float = 0.0
        self.ear_right: float = 0.0
        self.ear_history: list = []
        self.last_jpeg_frame: bytes | None = None
        self.escalation_level: int = 0
        self.escalation_counts: dict = {}
        self.dnd_active: bool = False
        self.dnd_end_time: str | None = None

    # ---- helpers ---------------------------------------------------------

    def record_blink(self) -> None:
        """Register a valid blink.  Caller must NOT hold the lock."""
        with self.lock:
            now = time.time()
            self.blink_timestamps.append(now)
            self.last_blink_time = now
            self.session_blink_count += 1
            self.detector_state = DetectorState.BLINK_DETECTED
            self.consecutive_misses = 0

    def set_detector_state(self, state: DetectorState) -> None:
        with self.lock:
            self.detector_state = state

    def get_detector_state(self) -> DetectorState:
        with self.lock:
            return self.detector_state

    def increment_alerts(self) -> None:
        with self.lock:
            self.session_alerts_fired += 1
            self.consecutive_misses += 1

    def get_session_duration_minutes(self) -> float:
        return (time.time() - self.session_start_time) / 60.0

    def get_avg_blink_interval(self) -> float | None:
        """Average inter-blink interval for the current session."""
        with self.lock:
            ts = self.blink_timestamps.copy()
        if len(ts) < 2:
            return None
        intervals = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
        # discard outliers > 30s (likely face-away periods)
        intervals = [iv for iv in intervals if iv <= 30.0]
        return sum(intervals) / len(intervals) if intervals else None

    # ---- persistence -----------------------------------------------------

    def load_settings(self) -> None:
        """Load settings.json from disk into this state object.

        Uses defaults.py for path resolution, default values, validation,
        and session history pruning.
        """
        data = load_settings_from_disk()

        with self.lock:
            self.settings = data
            self.phase = Phase(data.get("phase", "observing"))
            self.baseline_interval = data.get("baseline_interval")
            self.current_threshold = data.get("current_threshold")
            self.sound_enabled = data.get("sound_enabled", True)
            self.launch_on_startup = data.get("launch_on_startup", True)

    def save_settings(self) -> None:
        """Persist current state back to settings.json."""
        with self.lock:
            self.settings["phase"] = self.phase.value
            self.settings["baseline_interval"] = self.baseline_interval
            self.settings["current_threshold"] = self.current_threshold
            self.settings["sound_enabled"] = self.sound_enabled
            self.settings["launch_on_startup"] = self.launch_on_startup

            data = self.settings.copy()

        save_settings_to_disk(data)
