"""
detector.py — MediaPipe EAR calculation + blink state machine.

Runs the camera capture loop in a dedicated thread. Computes the Eye Aspect
Ratio (EAR) from Face Mesh landmarks and feeds valid blinks into SharedState.

Features:
  • Per-eye EAR tracking for dashboard
  • JPEG frame encoding for live preview
  • 3-level gentle escalation alerts
  • DND schedule awareness
  • Hourly blink data collection
  • Calibrated EAR threshold support
"""

import time
import datetime
import logging

import cv2
import mediapipe as mp

from blink_guard.state import SharedState, DetectorState, Phase
from blink_guard.alerts import play_alert, set_base_volume, load_custom_sound
from blink_guard.dnd import is_dnd_active

logger = logging.getLogger("BlinkGuard")

# ---------------------------------------------------------------------------
# Landmark indices (MediaPipe Face Mesh 468+ landmarks)
# ---------------------------------------------------------------------------

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# ---------------------------------------------------------------------------
# EAR helpers
# ---------------------------------------------------------------------------

def _distance(p1, p2) -> float:
    """Euclidean distance between two landmark points."""
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5


def _ear(landmarks, indices) -> float:
    """Compute Eye Aspect Ratio for one eye.

    EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
    """
    p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in indices]
    vertical_1 = _distance(p2, p6)
    vertical_2 = _distance(p3, p5)
    horizontal = _distance(p1, p4)
    if horizontal < 1e-6:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def compute_ear(landmarks) -> float:
    """Average EAR across both eyes."""
    left = _ear(landmarks, LEFT_EYE)
    right = _ear(landmarks, RIGHT_EYE)
    return (left + right) / 2.0


def compute_ear_both(landmarks) -> tuple[float, float]:
    """Return (left_ear, right_ear)."""
    return _ear(landmarks, LEFT_EYE), _ear(landmarks, RIGHT_EYE)


# ---------------------------------------------------------------------------
# Detection loop (runs in Thread-1)
# ---------------------------------------------------------------------------

DEFAULT_EAR_THRESHOLD = 0.2
BLINK_CONSEC_FRAMES = 2     # frames below threshold to count as blink
BLINK_GRACE_PERIOD = 0.3    # seconds of grace after a valid blink
MIN_DETECTION_CONFIDENCE = 0.5
FRAME_ENCODE_INTERVAL = 3   # encode a JPEG every N frames (~10 fps at 30 fps)

# Escalation timings (seconds after initial alert)
ESCALATION_DELAY = 2.0       # seconds between escalation levels


def _draw_overlays(frame, landmarks, face_lms, blink_flash: bool) -> None:
    """Draw face rectangle and eye landmarks on the frame for the dashboard."""
    h, w = frame.shape[:2]

    # Face bounding rectangle
    xs = [lm.x * w for lm in face_lms]
    ys = [lm.y * h for lm in face_lms]
    x1, y1 = int(min(xs)), int(min(ys))
    x2, y2 = int(max(xs)), int(max(ys))
    pad = 20
    color = (78, 201, 78) if blink_flash else (0, 122, 204)  # BGR
    cv2.rectangle(frame, (x1 - pad, y1 - pad), (x2 + pad, y2 + pad), color, 2)

    # Eye landmark dots
    for idx_list in [LEFT_EYE, RIGHT_EYE]:
        for idx in idx_list:
            lm = face_lms[idx]
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 2, (0, 122, 204), -1)


def run_detector(shared: SharedState) -> None:
    """Main camera + detection loop.  Blocks until shutdown_event is set."""
    logger.info("Detector thread starting.")

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=MIN_DETECTION_CONFIDENCE,
    )

    # Read settings
    cam_index = 0
    ear_threshold = DEFAULT_EAR_THRESHOLD
    with shared.lock:
        cam_index = shared.settings.get("camera_index", 0)
        # Use calibrated threshold if available
        ear_threshold = shared.settings.get("ear_blink_threshold", DEFAULT_EAR_THRESHOLD)
        # Load volume
        volume = shared.settings.get("volume", 75)
        # Load custom sound
        alert_sound = shared.settings.get("alert_sound", "default")
        custom_path = shared.settings.get("custom_sound_path")

    set_base_volume(volume)
    use_custom = alert_sound == "custom"
    if use_custom and custom_path:
        load_custom_sound(custom_path)

    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        logger.error("Cannot open camera (index %d).", cam_index)
        return

    # Try to set a modest resolution to reduce CPU load
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    frames_below = 0           # consecutive frames with EAR < threshold
    last_blink_ts = time.time()
    grace_until = 0.0          # timestamp until we suppress new blinks
    frame_counter = 0          # for throttling JPEG encoding

    # Escalation state
    escalation_level = 0       # 0 = no alert, 1-3 = escalation levels
    first_alert_ts = 0.0       # when the first alert was fired
    last_escalation_ts = 0.0   # when we last escalated

    # Hourly data tracking
    last_hourly_update = 0.0

    try:
        while not shared.shutdown_event.is_set():
            # --- respect PAUSED state ---
            if shared.get_detector_state() == DetectorState.PAUSED:
                time.sleep(0.5)
                continue

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)

            now = time.time()

            if not results.multi_face_landmarks:
                # No face detected — pause timer
                shared.set_detector_state(DetectorState.FACE_NOT_VISIBLE)
                frames_below = 0

                # Still encode a frame for the dashboard (no overlays)
                frame_counter += 1
                if frame_counter % FRAME_ENCODE_INTERVAL == 0:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    shared.last_jpeg_frame = buf.tobytes()

                time.sleep(0.03)
                continue

            face_lms = results.multi_face_landmarks[0].landmark
            landmarks = face_lms
            ear_left, ear_right = compute_ear_both(landmarks)
            ear = (ear_left + ear_right) / 2.0

            # Store EAR data for IPC
            shared.ear_left = ear_left
            shared.ear_right = ear_right
            shared.ear_history.append({"left": round(float(ear_left), 4),
                                        "right": round(float(ear_right), 4)})
            if len(shared.ear_history) > 100:
                shared.ear_history = shared.ear_history[-100:]

            # --- blink state machine --- (using calibrated threshold)
            blink_flash = False
            if ear < ear_threshold:
                frames_below += 1
            else:
                if frames_below >= BLINK_CONSEC_FRAMES and now > grace_until:
                    # Valid full blink
                    shared.record_blink()
                    last_blink_ts = now
                    grace_until = now + BLINK_GRACE_PERIOD
                    blink_flash = True

                    # Reset escalation on blink
                    escalation_level = 0
                    first_alert_ts = 0.0

                    # Update hourly data
                    _update_hourly_data(shared, now)

                    logger.debug("Blink detected (EAR=%.3f, frames=%d)", ear, frames_below)
                frames_below = 0

            if now <= grace_until:
                blink_flash = True

            # --- encode frame with overlays for dashboard ---
            frame_counter += 1
            if frame_counter % FRAME_ENCODE_INTERVAL == 0:
                show_landmarks = True
                with shared.lock:
                    show_landmarks = shared.settings.get("show_landmarks", True)
                if show_landmarks:
                    _draw_overlays(frame, landmarks, face_lms, blink_flash)
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                shared.last_jpeg_frame = buf.tobytes()

            # --- update detector state ---
            if shared.get_detector_state() != DetectorState.PAUSED:
                if now <= grace_until:
                    shared.set_detector_state(DetectorState.BLINK_DETECTED)
                else:
                    shared.set_detector_state(DetectorState.WATCHING)

            # --- check alert threshold with gentle escalation ---
            with shared.lock:
                threshold = shared.current_threshold
                phase = shared.phase
                sound_on = shared.sound_enabled
                consecutive_misses = shared.consecutive_misses
                settings_copy = shared.settings.copy()

            if phase == Phase.OBSERVING or threshold is None:
                # No alerts during observation
                time.sleep(0.03)
                continue

            elapsed = now - last_blink_ts

            # Check DND schedule
            dnd_active, dnd_end = is_dnd_active(settings_copy)
            if dnd_active:
                # Store DND status for tray/IPC
                shared.dnd_active = True
                shared.dnd_end_time = dnd_end
            else:
                shared.dnd_active = False
                shared.dnd_end_time = None

            if elapsed > threshold:
                # In WEAN_OFF mode, only fire if 2+ consecutive misses
                should_fire = True
                if phase == Phase.WEAN_OFF and consecutive_misses < 1:
                    should_fire = False

                if should_fire:
                    # --- Gentle Escalation ---
                    if escalation_level == 0:
                        # First alert
                        escalation_level = 1
                        first_alert_ts = now
                        last_escalation_ts = now
                        shared.increment_alerts()
                        _record_escalation(shared, 1)
                        play_alert(sound_on, level=1, use_custom=use_custom,
                                   dnd_active=dnd_active)
                        # Store level for IPC
                        shared.escalation_level = 1
                        logger.debug("Alert L1 (elapsed=%.1fs, thr=%.1fs)", elapsed, threshold)
                    elif now - last_escalation_ts >= ESCALATION_DELAY:
                        # Escalate
                        if escalation_level < 3:
                            escalation_level += 1
                        last_escalation_ts = now
                        shared.increment_alerts()
                        _record_escalation(shared, escalation_level)
                        play_alert(sound_on, level=escalation_level,
                                   use_custom=use_custom, dnd_active=dnd_active)
                        shared.escalation_level = escalation_level
                        logger.debug("Alert L%d (elapsed=%.1fs)", escalation_level, elapsed)
                else:
                    shared.increment_alerts()
                    # Reset the blink timer so we don't fire every frame
                    last_blink_ts = now
            else:
                # Not exceeding threshold, reset escalation
                if escalation_level > 0:
                    escalation_level = 0
                    shared.escalation_level = 0

            # Small sleep to cap CPU (~30 fps is plenty)
            time.sleep(0.03)

    except Exception:
        logger.exception("Detector thread crashed.")
    finally:
        cap.release()
        face_mesh.close()
        logger.info("Detector thread stopped.")


def _record_escalation(shared: SharedState, level: int) -> None:
    """Record escalation event for session stats."""
    key = f"level_{level}"
    shared.escalation_counts[key] = shared.escalation_counts.get(key, 0) + 1


def _update_hourly_data(shared: SharedState, now: float) -> None:
    """Update hourly blink data for the time-of-day heatmap."""
    hour = datetime.datetime.now().strftime("%H")
    with shared.lock:
        hourly = shared.settings.setdefault("hourly_data", {})
        hour_data = hourly.setdefault(hour, {
            "total_intervals": [],
            "alert_count": 0,
            "session_count": 0,
        })

        # Add latest blink interval
        if len(shared.blink_timestamps) >= 2:
            interval = shared.blink_timestamps[-1] - shared.blink_timestamps[-2]
            if interval <= 30.0:  # filter outliers
                intervals = hour_data.get("total_intervals", [])
                intervals.append(round(interval, 2))
                # Cap stored intervals to prevent unbounded growth
                if len(intervals) > 500:
                    intervals = intervals[-500:]
                hour_data["total_intervals"] = intervals
