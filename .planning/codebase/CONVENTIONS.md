# Code Conventions

## Style
- **Python 3.10+** type hints used throughout (union types with `|`, `list[float]`, etc.)
- Module-level docstrings describe purpose, features, and design intent
- Functions have Google-style docstrings with Args/Returns sections
- Private functions prefixed with `_` (e.g. `_distance()`, `_draw_overlays()`)
- Constants are `UPPER_SNAKE_CASE` at module top
- Imports grouped: stdlib → third-party → local, separated by blank lines
- `noqa: E402` used for local imports deferred after logging setup in `main.py`

## Patterns
- **Thread-safe state** — All shared data accessed through `SharedState.lock` mutex
- **Helper methods over direct field access** — `shared.record_blink()` instead of `shared.blink_count += 1`
- **Graceful degradation** — `try/except ImportError` around optional deps (pywin32, customtkinter)
- **hasattr guards** — Dynamic attributes on SharedState checked with `hasattr()` before access
- **Callback-based IPC** — Server receives callback functions rather than direct SharedState reference
- **Settings dict** — Single `settings: dict` on SharedState holds all persistent config. No ORM, no schema.

## Naming
- Files: `snake_case.py`
- Classes: `PascalCase` (`SharedState`, `IPCServer`, `CalibrationWizard`)
- UI tabs: `Tab<Name>` convention (`LiveTab`, `HistoryTab`, `ProgressTab`, `SettingsTab`)
- Enums: `PascalCase` with `UPPER_SNAKE_CASE` values

## Logging
- Single logger: `logging.getLogger("BlinkGuard")`
- RotatingFileHandler (2 MB, 2 backups) + stderr in dev mode
- Levels: DEBUG for blink events, INFO for lifecycle, WARNING for graceful failures, EXCEPTION for crashes

## Error Handling
- `try/except Exception` with `logger.exception()` at thread boundaries
- Never crash the main process — threads fail silently, main thread continues
- Detector thread wraps the entire camera loop in try/finally to ensure `cap.release()`
