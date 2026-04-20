@echo off
REM -----------------------------------------------------------------------
REM  build.bat — Package BlinkGuard into TWO executables with PyInstaller
REM    1. BlinkGuard.exe          — background tray process
REM    2. BlinkGuardDashboard.exe — dashboard UI
REM -----------------------------------------------------------------------

echo [BlinkGuard] Building executables...

REM Find the mediapipe data directory for bundling
for /f "delims=" %%i in ('python -c "import mediapipe, os; print(os.path.dirname(mediapipe.__file__))"') do set MP_DIR=%%i

REM Find the customtkinter data directory for bundling
for /f "delims=" %%i in ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_DIR=%%i

echo.
echo [1/2] Building BlinkGuard.exe (background process)...

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --noconsole ^
    --name BlinkGuard ^
    --add-data "%MP_DIR%\modules;mediapipe\modules" ^
    --add-data "%CTK_DIR%;customtkinter" ^
    --hidden-import=pystray._win32 ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=customtkinter ^
    --hidden-import=blink_guard.defaults ^
    --hidden-import=blink_guard.session ^
    --hidden-import=blink_guard.dnd ^
    --hidden-import=blink_guard.risk ^
    --hidden-import=blink_guard.weekly ^
    --hidden-import=blink_guard.ipc ^
    --hidden-import=blink_guard.ui.calibration ^
    --hidden-import=blink_guard.ui.cards._base ^
    --hidden-import=blink_guard.ui.cards.card_alert ^
    --hidden-import=blink_guard.ui.cards.card_startup ^
    --hidden-import=blink_guard.ui.cards.card_journey ^
    --hidden-import=blink_guard.ui.cards.card_dnd ^
    --hidden-import=blink_guard.ui.cards.card_camera ^
    --hidden-import=blink_guard.ui.cards.card_about ^
    --hidden-import=numpy ^
    --hidden-import=win10toast ^
    blink_guard\main.py

echo.
echo [2/2] Building BlinkGuardDashboard.exe (dashboard UI)...

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --noconsole ^
    --name BlinkGuardDashboard ^
    --add-data "%CTK_DIR%;customtkinter" ^
    --add-data "%MP_DIR%\modules;mediapipe\modules" ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=customtkinter ^
    --hidden-import=matplotlib ^
    --hidden-import=matplotlib.backends.backend_tkagg ^
    --hidden-import=blink_guard.defaults ^
    --hidden-import=blink_guard.dnd ^
    --hidden-import=blink_guard.risk ^
    --hidden-import=blink_guard.weekly ^
    --hidden-import=blink_guard.ipc ^
    --hidden-import=blink_guard.ui.calibration ^
    --hidden-import=blink_guard.ui.cards._base ^
    --hidden-import=blink_guard.ui.cards.card_alert ^
    --hidden-import=blink_guard.ui.cards.card_startup ^
    --hidden-import=blink_guard.ui.cards.card_journey ^
    --hidden-import=blink_guard.ui.cards.card_dnd ^
    --hidden-import=blink_guard.ui.cards.card_camera ^
    --hidden-import=blink_guard.ui.cards.card_about ^
    --hidden-import=numpy ^
    --hidden-import=win10toast ^
    blink_guard\dashboard.py

echo.
echo [BlinkGuard] Creating distribution folder...

REM Create clean dist folder
if not exist "dist\BlinkGuard" mkdir "dist\BlinkGuard"
copy /Y "dist\BlinkGuard.exe" "dist\BlinkGuard\BlinkGuard.exe" >nul 2>&1
copy /Y "dist\BlinkGuardDashboard.exe" "dist\BlinkGuard\BlinkGuardDashboard.exe" >nul 2>&1
copy /Y "settings.json" "dist\BlinkGuard\settings.json" >nul 2>&1

REM Create README.txt
(
echo BlinkGuard — Adaptive Blink Rate Monitor
echo ==========================================
echo.
echo Run BlinkGuard.exe once — it will start automatically on every boot.
echo On first launch, a calibration wizard will help tune blink detection.
echo Open BlinkGuardDashboard.exe anytime to view your progress.
echo.
echo Features:
echo   - Calibration Wizard for personal eye detection tuning
echo   - 3-level gentle alert escalation ^(soft, medium, urgent^)
echo   - Do Not Disturb schedule for meetings/focus time
echo   - Custom alert sounds ^(.wav / .mp3^)
echo   - Time-of-day blink heatmap
echo   - Eye strain risk scoring
echo   - Weekly summary report cards
echo.
echo Both files must remain in the same folder.
echo.
echo All processing is local. No data ever leaves your device.
) > "dist\BlinkGuard\README.txt"

echo.
echo [BlinkGuard] Build complete!
echo   dist\BlinkGuard\BlinkGuard.exe          — background tray process
echo   dist\BlinkGuard\BlinkGuardDashboard.exe — dashboard UI
echo   dist\BlinkGuard\settings.json           — configuration
echo   dist\BlinkGuard\README.txt
pause
