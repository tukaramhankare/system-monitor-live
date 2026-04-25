# Hardware Health Dashboard v2.2
Made by Tukaram Hankare | Farmer | Coder | Designer

---

## Fixed in v2.2
- **_tkinter.TclError: invalid command name "500"**
  This was the crash you saw. Caused by BarWidget (Canvas) being
  initialised before Tkinter was fully ready. Fixed by:
  1. Not passing width/height to Canvas constructor
  2. Using .configure() after construction
  3. Guarding every canvas draw with winfo_exists() check
  4. First data update delayed to after(500ms) so window is ready

---

## How to Run (Python script)

1. Install dependencies:
   ```
   pip install psutil plyer pystray Pillow
   ```

2. Run:
   ```
   python hardware_dashboard.py
   ```

---

## How to Build EXE

Just double-click **build_exe.bat**

Or manually:
```
pip install psutil plyer pystray Pillow pyinstaller

pyinstaller --onefile --windowed --name HardwareDashboard ^
  --hidden-import=psutil ^
  --hidden-import=psutil._pswindows ^
  --hidden-import=plyer.platforms.win.notification ^
  --hidden-import=pystray._win32 ^
  --hidden-import=PIL.Image ^
  --hidden-import=PIL.ImageDraw ^
  hardware_dashboard.py
```

EXE will be at: dist\HardwareDashboard.exe

---

## Battery Alert Settings

Default thresholds:
- Low battery alert  : <= 25% (while discharging)
- High battery alert : >= 95% (while charging)

Click Settings button (top-right) to change thresholds anytime.
Alerts fire even when window is minimised.
Alerts repeat every 60 seconds while condition persists.

---

## Dependencies

| Package    | Purpose                      | Required |
|------------|------------------------------|----------|
| psutil     | CPU / RAM / Battery / Disk   | YES      |
| plyer      | Desktop notifications        | Optional |
| pystray    | System tray on minimise      | Optional |
| Pillow     | Tray icon image              | Optional |

If plyer is missing: falls back to Windows MessageBox popup.
If pystray/Pillow missing: minimise goes to taskbar normally.
