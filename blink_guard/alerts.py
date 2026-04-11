"""
alerts.py — Multi-level alert sound logic + custom sound support.

Features:
  • Three escalation levels (soft → medium → loud)
  • Custom sound file support (.wav / .mp3)
  • Volume scaling per level
  • DND-aware (callers pass dnd_active flag)
"""

import array
import math
import os
import logging

import pygame

logger = logging.getLogger("BlinkGuard")

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_sounds: dict[int, pygame.mixer.Sound] = {}   # level → Sound
_custom_sound: pygame.mixer.Sound | None = None
_initialized: bool = False
_base_volume: float = 0.75     # 0.0-1.0, updated from settings

# Escalation config:  (frequency_hz, duration_ms, repeats)
ESCALATION = {
    1: (440, 150, 1),
    2: (550, 200, 1),
    3: (660, 300, 2),
}

# Volume multipliers per level
LEVEL_VOLUME = {1: 0.5, 2: 0.75, 3: 1.0}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_sound() -> None:
    """Initialize pygame mixer and pre-generate escalation beeps."""
    global _initialized
    if _initialized:
        return
    try:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
        pygame.mixer.init()
        for level, (freq, dur, _repeats) in ESCALATION.items():
            _sounds[level] = _generate_beep(frequency=freq, duration_ms=dur, volume=0.5)
        _initialized = True
        logger.info("Sound system initialized (3-level escalation).")
    except Exception:
        logger.exception("Failed to initialize pygame mixer.")


def set_base_volume(volume_pct: int) -> None:
    """Set the base volume (0-100)."""
    global _base_volume
    _base_volume = max(0.0, min(volume_pct / 100.0, 1.0))


def load_custom_sound(path: str | None) -> bool:
    """Load a custom alert sound from file. Returns True on success."""
    global _custom_sound
    _custom_sound = None
    if not path or not os.path.isfile(path):
        return False
    try:
        # Check file size (max 5 MB)
        if os.path.getsize(path) > 5 * 1024 * 1024:
            logger.warning("Custom sound file too large: %s", path)
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".wav", ".mp3"):
            logger.warning("Unsupported sound format: %s", ext)
            return False
        _custom_sound = pygame.mixer.Sound(path)
        logger.info("Custom sound loaded: %s", path)
        return True
    except Exception:
        logger.exception("Failed to load custom sound: %s", path)
        return False


def play_alert(sound_enabled: bool, level: int = 1,
               use_custom: bool = False, dnd_active: bool = False) -> None:
    """Play an alert at the given escalation level.

    Args:
        sound_enabled: master sound toggle
        level: escalation level 1-3
        use_custom: use custom sound instead of beep
        dnd_active: if True, suppress all audio (still track stats)
    """
    if not sound_enabled or not _initialized or dnd_active:
        return

    level = max(1, min(3, level))
    vol_mult = LEVEL_VOLUME.get(level, 1.0)
    effective_vol = _base_volume * vol_mult

    _freq, _dur, repeats = ESCALATION.get(level, (440, 150, 1))

    try:
        if use_custom and _custom_sound is not None:
            _custom_sound.set_volume(effective_vol)
            for _ in range(repeats):
                _custom_sound.play()
        else:
            sound = _sounds.get(level)
            if sound:
                sound.set_volume(effective_vol)
                for _ in range(repeats):
                    sound.play()
    except Exception:
        logger.exception("Failed to play alert (level %d)", level)


# Keep backward compat
def play_beep(sound_enabled: bool) -> None:
    """Legacy single-beep interface."""
    play_alert(sound_enabled, level=1)


def shutdown_sound() -> None:
    """Tear down the mixer cleanly."""
    global _initialized
    if _initialized:
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        _initialized = False


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _generate_beep(
    frequency: int = 440,
    duration_ms: int = 150,
    volume: float = 0.5,
) -> pygame.mixer.Sound:
    """Synthesise a sine-wave tone and return a Sound object."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    max_amp = int(32767 * volume)

    buf = array.array("h")  # signed 16-bit
    for i in range(n_samples):
        t = i / sample_rate
        value = int(max_amp * math.sin(2.0 * math.pi * frequency * t))
        buf.append(value)

    # Apply a tiny fade-in / fade-out to avoid clicks
    fade_samples = min(200, n_samples // 4)
    for i in range(fade_samples):
        factor = i / fade_samples
        buf[i] = int(buf[i] * factor)
        buf[-(i + 1)] = int(buf[-(i + 1)] * factor)

    return pygame.mixer.Sound(buffer=buf)
