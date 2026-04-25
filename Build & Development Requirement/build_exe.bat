@echo off
REM ============================================================
REM  Hardware Health Dashboard v2.2 - Build EXE
REM  Put this file next to hardware_dashboard.py and run it.
REM  Output will be at:  dist\HardwareDashboard.exe
REM ============================================================

echo.
echo  Step 1 - Installing dependencies...
echo.
pip install psutil plyer pystray Pillow pyinstaller
if errorlevel 1 (
    echo.
    echo  ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo  Step 2 - Building EXE (please wait 1-3 minutes)...
echo.

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "HardwareDashboard" ^
  --hidden-import=psutil ^
  --hidden-import=psutil._pswindows ^
  --hidden-import=plyer ^
  --hidden-import=plyer.platforms ^
  --hidden-import=plyer.platforms.win ^
  --hidden-import=plyer.platforms.win.notification ^
  --hidden-import=pystray ^
  --hidden-import=pystray._win32 ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=PIL.ImageDraw ^
  hardware_dashboard.py

if errorlevel 1 (
    echo.
    echo  ERROR: PyInstaller build failed. See output above.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   BUILD SUCCESSFUL!
echo   Your EXE is at:  dist\HardwareDashboard.exe
echo  ============================================================
echo.
pause
