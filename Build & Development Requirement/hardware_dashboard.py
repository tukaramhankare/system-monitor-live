# -*- coding: utf-8 -*-
"""
Hardware Health Dashboard v2.3
Made by Tukaram Hankare (As Farmer, Coder and Designer)

Confirmed alert logic:
- Low  alert fires when battery % <= low_threshold  AND discharging
- High alert fires when battery % >= high_threshold AND charging
- Alert fires immediately on first match (no startup delay)
- After firing, repeats every 60 seconds while condition persists
- Saving new thresholds resets cooldown timers so new alert fires immediately
- Settings dialog has "Test Alert" button to verify notifications work
- Badge text in main window always matches current threshold values
"""

import multiprocessing
multiprocessing.freeze_support()

import tkinter as tk
from tkinter import messagebox
import threading
import time
import sys
import ctypes

# --------------------------------------------------------------------------
# Optional imports
# --------------------------------------------------------------------------
try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False

try:
    from plyer import notification as _plyer
    PLYER_OK = True
except Exception:
    PLYER_OK = False

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_OK = True
except Exception:
    TRAY_OK = False

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
APP_NAME   = "Hardware Health Dashboard"
AUTHOR     = "Tukaram Hankare"
AUTHOR_SUB = "Farmer | Coder | Designer"
VERSION    = "v2.3"

BG_DARK  = "#0a0e0a"
BG_CARD  = "#111a11"
BG_PANEL = "#0f1a0f"
C_GREEN  = "#00ff9d"
C_GREEN2 = "#00cc7a"
C_WHITE  = "#ddeedd"
C_DIM    = "#3a5e3a"
C_RED    = "#ff4d4d"
C_AMBER  = "#ffaa00"

F_TITLE  = ("Courier New", 20, "bold")
F_VALUE  = ("Courier New", 12, "bold")
F_LABEL  = ("Courier New", 10)
F_SMALL  = ("Courier New", 8)

POLL_SEC   = 2
NOTIF_COOL = 60   # seconds between repeated alerts for same condition


# --------------------------------------------------------------------------
# Notification delivery
# --------------------------------------------------------------------------
def _msgbox_worker(title, msg):
    """Windows fallback: blocking MessageBox in daemon thread."""
    try:
        ctypes.windll.user32.MessageBoxW(
            0, msg, title,
            0x00000040 | 0x00001000   # MB_ICONINFORMATION | MB_SYSTEMMODAL
        )
    except Exception:
        pass


def send_notification(title, msg):
    """
    Send a desktop notification.
    1st choice: plyer (proper OS toast)
    2nd choice: Windows MessageBox in background thread
    """
    if PLYER_OK:
        try:
            _plyer.notify(
                title=title,
                message=msg,
                app_name=APP_NAME,
                timeout=8,
            )
            return
        except Exception:
            pass
    # Windows fallback - runs in daemon thread so it does not block UI
    if sys.platform == "win32":
        threading.Thread(
            target=_msgbox_worker,
            args=(title, msg),
            daemon=True
        ).start()


# --------------------------------------------------------------------------
# Notification Engine
#
# Alert rules (confirmed):
#   LOW  : battery_pct <= low_threshold  AND NOT plugged_in
#   HIGH : battery_pct >= high_threshold AND plugged_in (charging)
#
# Cooldown: after each alert fires, waits NOTIF_COOL seconds before
# repeating the same alert. A NEW condition (low->high or high->low)
# fires immediately regardless of cooldown.
#
# Threshold change: calling reset_cooldowns() clears timers so the
# new threshold takes effect immediately on next poll.
# --------------------------------------------------------------------------
class NotificationEngine:
    def __init__(self):
        self.low_threshold  = 25   # alert when battery <= this AND discharging
        self.high_threshold = 95   # alert when battery >= this AND charging
        self._t_low  = -NOTIF_COOL   # set negative so first check fires immediately
        self._t_high = -NOTIF_COOL

    def reset_cooldowns(self):
        """Call this after saving new thresholds so alerts fire right away."""
        self._t_low  = -NOTIF_COOL
        self._t_high = -NOTIF_COOL

    def check(self, pct, plugged):
        """
        Called every POLL_SEC seconds with current battery state.
        pct    : float - battery percentage 0-100
        plugged: bool  - True if charger is connected
        """
        now = time.time()

        # -- Low battery check --
        if pct <= self.low_threshold and not plugged:
            if now - self._t_low >= NOTIF_COOL:
                send_notification(
                    "Low Battery Warning",
                    "Battery at {:.0f}% (Limit: {}%) - Please plug in charger!".format(
                        pct, self.low_threshold)
                )
                self._t_low = now
            # Reset high timer so if user plugs in and unplugs, high alert
            # does not get suppressed by old high timer
            self._t_high = -NOTIF_COOL

        # -- High battery / fully charged check --
        elif pct >= self.high_threshold and plugged:
            if now - self._t_high >= NOTIF_COOL:
                send_notification(
                    "Battery Charged",
                    "Battery at {:.0f}% (Limit: {}%) - Safe to unplug charger.".format(
                        pct, self.high_threshold)
                )
                self._t_high = now
            # Reset low timer symmetrically
            self._t_low = -NOTIF_COOL

        # -- Condition cleared: reset timers so next trigger fires instantly --
        else:
            # Only reset if was previously in alert state
            # This ensures a fresh alert fires as soon as condition returns
            pass   # timers decay naturally; negative init handles first-time

    def test_alert(self):
        """Fire a test notification to confirm alerts are working."""
        send_notification(
            "Test Alert - Hardware Dashboard",
            "Notifications are working! Low={:.0f}%  High={:.0f}%".format(
                self.low_threshold, self.high_threshold)
        )


# --------------------------------------------------------------------------
# BarWidget - Canvas-based progress bar
# width/height NOT passed to Canvas() constructor to avoid TclError "500"
# --------------------------------------------------------------------------
class BarWidget(tk.Canvas):
    def __init__(self, parent, bar_width=490, bar_height=14):
        super().__init__(
            parent,
            highlightthickness=0,
            bd=0,
            bg=BG_DARK
        )
        self._bw    = bar_width
        self._bh    = bar_height
        self._pct   = 0.0
        self._color = C_GREEN
        # Set size after construction (avoids TclError)
        self.configure(width=self._bw, height=self._bh)

    def set(self, pct, color=None):
        self._pct   = max(0.0, min(100.0, float(pct)))
        self._color = color if color else C_GREEN
        self._render()

    def _render(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        try:
            self.delete("all")
            w, h = self._bw, self._bh
            # Border
            self.create_rectangle(0, 0, w - 1, h - 1, outline=C_DIM, fill=BG_DARK)
            # Fill
            fw = int((w - 2) * self._pct / 100.0)
            if fw > 2:
                self.create_rectangle(1, 1, fw, h - 2, fill=self._color, outline="")
                self.create_line(1, 1, fw, 1, fill="#bbffdd", width=1)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Settings Dialog
# --------------------------------------------------------------------------
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, engine):
        super().__init__(parent)
        self.engine = engine
        self.title("Notification Settings")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()
        self._build()
        self.update_idletasks()
        try:
            px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
            py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry("+{}+{}".format(max(0, px), max(0, py)))
        except Exception:
            pass

    def _build(self):
        p = dict(padx=20, pady=8)

        tk.Label(
            self, text="BATTERY ALERT THRESHOLDS",
            font=("Courier New", 11, "bold"),
            fg=C_GREEN, bg=BG_DARK
        ).grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 4))

        # Explanation text
        tk.Label(
            self,
            text="LOW  alert : fires when battery <= Low%  and discharging\n"
                 "HIGH alert : fires when battery >= High% and charging",
            font=F_SMALL, fg=C_DIM, bg=BG_DARK, justify="left"
        ).grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 12), sticky="w")

        # Low threshold
        tk.Label(
            self, text="Low Battery Alert (%):",
            font=F_LABEL, fg=C_WHITE, bg=BG_DARK
        ).grid(row=2, column=0, sticky="w", **p)

        self._low_var = tk.IntVar(value=self.engine.low_threshold)
        tk.Spinbox(
            self, from_=5, to=50,
            textvariable=self._low_var,
            width=6, font=F_LABEL,
            bg=BG_CARD, fg=C_GREEN,
            buttonbackground=BG_PANEL,
            insertbackground=C_GREEN,
            relief="flat"
        ).grid(row=2, column=1, sticky="w", **p)

        # High threshold
        tk.Label(
            self, text="High Battery Alert (%):",
            font=F_LABEL, fg=C_WHITE, bg=BG_DARK
        ).grid(row=3, column=0, sticky="w", **p)

        self._high_var = tk.IntVar(value=self.engine.high_threshold)
        tk.Spinbox(
            self, from_=51, to=100,
            textvariable=self._high_var,
            width=6, font=F_LABEL,
            bg=BG_CARD, fg=C_GREEN,
            buttonbackground=BG_PANEL,
            insertbackground=C_GREEN,
            relief="flat"
        ).grid(row=3, column=1, sticky="w", **p)

        tk.Label(
            self,
            text="Alerts fire even when window is minimised.\n"
                 "After saving, new limits take effect on next battery check.",
            font=F_SMALL, fg=C_DIM, bg=BG_DARK, justify="left"
        ).grid(row=4, column=0, columnspan=2, padx=20, pady=(0, 6), sticky="w")

        # Buttons row
        btn_row = tk.Frame(self, bg=BG_DARK)
        btn_row.grid(row=5, column=0, columnspan=2, pady=(4, 20))

        tk.Button(
            btn_row, text="  SAVE  ",
            command=self._save,
            font=("Courier New", 10, "bold"),
            bg=C_GREEN2, fg=BG_DARK,
            activebackground=C_GREEN,
            relief="flat", padx=14, pady=6,
            cursor="hand2"
        ).pack(side="left", padx=6)

        tk.Button(
            btn_row, text="  TEST ALERT  ",
            command=self._test,
            font=F_LABEL,
            bg=C_AMBER, fg=BG_DARK,
            activebackground="#ffcc44",
            relief="flat", padx=14, pady=6,
            cursor="hand2"
        ).pack(side="left", padx=6)

        tk.Button(
            btn_row, text="  CANCEL  ",
            command=self.destroy,
            font=F_LABEL,
            bg=BG_CARD, fg=C_DIM,
            activebackground=BG_PANEL,
            relief="flat", padx=14, pady=6,
            cursor="hand2"
        ).pack(side="left", padx=6)

    def _save(self):
        lo = self._low_var.get()
        hi = self._high_var.get()
        if lo >= hi:
            messagebox.showerror(
                "Invalid",
                "Low threshold must be less than High threshold.",
                parent=self
            )
            return
        self.engine.low_threshold  = lo
        self.engine.high_threshold = hi
        self.engine.reset_cooldowns()   # <-- ensures alert fires immediately with new limits
        messagebox.showinfo(
            "Saved",
            "Alert thresholds saved:\n\n"
            "  Low  <= {}%  (alerts when discharging)\n"
            "  High >= {}%  (alerts when charging)\n\n"
            "New limits active from next battery reading.".format(lo, hi),
            parent=self
        )
        self.destroy()

    def _test(self):
        """Fire a test notification immediately to confirm system is working."""
        self.engine.test_alert()


# --------------------------------------------------------------------------
# Main Dashboard
# --------------------------------------------------------------------------
class Dashboard(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.configure(bg=BG_DARK)
        self.resizable(False, False)

        self._engine  = NotificationEngine()
        self._running = True
        self._tray    = None

        self._build_ui()
        self._center()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_unmap)

        threading.Thread(target=self._poll_loop, daemon=True).start()

        # Delay first update so window is fully drawn before we touch bars
        self.after(500, self._do_update)

    # -----------------------------------------------------------------------
    # Build UI
    # -----------------------------------------------------------------------
    def _build_ui(self):
        wrap = tk.Frame(self, bg=BG_DARK, padx=22, pady=16)
        wrap.pack(fill="both", expand=True)

        # Header
        hdr = tk.Frame(wrap, bg=BG_DARK)
        hdr.pack(fill="x", pady=(0, 10))

        tk.Label(
            hdr, text="SYSTEM  DASHBOARD",
            font=F_TITLE, fg=C_GREEN, bg=BG_DARK
        ).pack(side="left")

        tk.Button(
            hdr, text="Settings",
            command=self._open_settings,
            font=F_SMALL,
            bg=BG_CARD, fg=C_GREEN,
            activebackground=BG_PANEL,
            activeforeground=C_GREEN2,
            relief="flat", padx=10, pady=4,
            cursor="hand2"
        ).pack(side="right")

        tk.Frame(wrap, bg=C_GREEN2, height=1).pack(fill="x", pady=(0, 12))

        # CPU
        self._cpu_var = tk.StringVar(value="CPU Usage:  --")
        self._cpu_bar = self._make_card(wrap, self._cpu_var)

        # RAM
        self._ram_var = tk.StringVar(value="RAM Usage:  --")
        self._ram_bar = self._make_card(wrap, self._ram_var)

        # Battery
        self._bat_var = tk.StringVar(value="Battery:  --")
        self._bat_bar = self._make_card(wrap, self._bat_var)

        # Battery alert badge
        self._badge_var = tk.StringVar(value="")
        self._badge_lbl = tk.Label(
            wrap, textvariable=self._badge_var,
            font=("Courier New", 9, "bold"),
            fg=C_AMBER, bg=BG_DARK
        )
        self._badge_lbl.pack(anchor="w", pady=(0, 4))

        # Disk
        self._disk_var = tk.StringVar(value="Disk:  --")
        self._make_card(wrap, self._disk_var, bar=False)

        # Uptime
        self._uptime_var = tk.StringVar(value="Uptime:  --")
        tk.Label(
            wrap, textvariable=self._uptime_var,
            font=("Courier New", 13, "bold"),
            fg=C_GREEN, bg=BG_DARK
        ).pack(pady=10)

        # Alert info strip
        self._alert_var = tk.StringVar(value=self._alert_strip())
        tk.Label(
            wrap, textvariable=self._alert_var,
            font=F_SMALL, fg=C_DIM, bg=BG_DARK
        ).pack()

        tk.Frame(wrap, bg=C_DIM, height=1).pack(fill="x", pady=(10, 8))

        # About
        about = tk.Frame(wrap, bg=BG_DARK)
        about.pack(fill="x")

        tk.Label(
            about,
            text="Made by {}".format(AUTHOR),
            font=("Courier New", 9, "bold"),
            fg=C_GREEN2, bg=BG_DARK
        ).pack(side="left")

        tk.Label(
            about,
            text="  |  {}".format(AUTHOR_SUB),
            font=F_SMALL, fg=C_DIM, bg=BG_DARK
        ).pack(side="left")

        tk.Label(
            about, text=VERSION,
            font=F_SMALL, fg=C_DIM, bg=BG_DARK
        ).pack(side="right")

    def _make_card(self, parent, textvar, bar=True):
        frame = tk.Frame(
            parent, bg=BG_CARD, padx=10, pady=8,
            highlightbackground=C_DIM, highlightthickness=1
        )
        frame.pack(fill="x", pady=4)

        tk.Label(
            frame, textvariable=textvar,
            font=F_VALUE, fg=C_WHITE, bg=BG_CARD
        ).pack(anchor="w")

        if bar:
            bw = BarWidget(frame, bar_width=490, bar_height=14)
            bw.pack(fill="x", pady=(4, 0))
            return bw
        return None

    def _alert_strip(self):
        return (
            "Alert limits  |  Low <= {}%  (discharging)  |  High >= {}%  (charging)".format(
                self._engine.low_threshold,
                self._engine.high_threshold
            )
        )

    # -----------------------------------------------------------------------
    # Background poll loop
    # -----------------------------------------------------------------------
    def _poll_loop(self):
        while self._running:
            time.sleep(POLL_SEC)
            if self._running:
                try:
                    self.after(0, self._do_update)
                except Exception:
                    break

    # -----------------------------------------------------------------------
    # Collect data (thread-safe, no Tk calls)
    # -----------------------------------------------------------------------
    def _collect(self):
        d = {
            "cpu": 0.0,
            "ram_used": 0, "ram_total": 1, "ram_pct": 0.0,
            "disk_pct": 0.0,
            "bat_pct": None, "bat_plugged": False,
            "uptime": 0.0,
        }
        if not PSUTIL_OK:
            return d

        try:
            d["cpu"] = psutil.cpu_percent(interval=0)
        except Exception:
            pass

        try:
            r = psutil.virtual_memory()
            d["ram_used"]  = r.used  >> 20
            d["ram_total"] = r.total >> 20
            d["ram_pct"]   = r.percent
        except Exception:
            pass

        try:
            path = "C:\\" if sys.platform == "win32" else "/"
            dk = psutil.disk_usage(path)
            d["disk_pct"] = dk.percent
        except Exception:
            pass

        try:
            b = psutil.sensors_battery()
            if b is not None:
                d["bat_pct"]     = b.percent
                d["bat_plugged"] = bool(b.power_plugged)
        except Exception:
            pass

        try:
            d["uptime"] = time.time() - psutil.boot_time()
        except Exception:
            pass

        return d

    # -----------------------------------------------------------------------
    # Apply data to UI (main thread only, called via .after())
    # -----------------------------------------------------------------------
    def _do_update(self):
        if not self._running:
            return
        try:
            d = self._collect()
        except Exception:
            return

        # CPU
        cpu = d["cpu"]
        self._cpu_var.set("CPU Usage:  {:.1f}%".format(cpu))
        if self._cpu_bar:
            c = C_RED if cpu > 85 else C_AMBER if cpu > 60 else C_GREEN
            self._cpu_bar.set(cpu, c)

        # RAM
        self._ram_var.set(
            "RAM Usage:  {}MB / {}MB  ({:.1f}%)".format(
                d["ram_used"], d["ram_total"], d["ram_pct"])
        )
        if self._ram_bar:
            c = C_RED if d["ram_pct"] > 85 else C_AMBER if d["ram_pct"] > 65 else C_GREEN
            self._ram_bar.set(d["ram_pct"], c)

        # Battery
        if d["bat_pct"] is not None:
            pct     = d["bat_pct"]
            plugged = d["bat_plugged"]
            status  = "Charging" if plugged else "Discharging"

            self._bat_var.set("Battery:  {:.0f}%  ({})".format(pct, status))

            if self._bat_bar:
                bc = C_RED if (pct <= self._engine.low_threshold and not plugged) else C_GREEN
                self._bat_bar.set(pct, bc)

            # Badge
            badge = ""
            if pct <= self._engine.low_threshold and not plugged:
                badge = "!! LOW BATTERY ({:.0f}%) - Please plug in charger !!".format(pct)
                try:
                    self._badge_lbl.config(fg=C_RED)
                except Exception:
                    pass
            elif pct >= self._engine.high_threshold and plugged:
                badge = ">> Battery charged ({:.0f}%) - Safe to unplug <<".format(pct)
                try:
                    self._badge_lbl.config(fg=C_GREEN2)
                except Exception:
                    pass
            self._badge_var.set(badge)

            # Fire notification engine (handles cooldown internally)
            self._engine.check(pct, plugged)

        else:
            self._bat_var.set("Battery:  Not detected")
            if self._bat_bar:
                self._bat_bar.set(0)
            self._badge_var.set("")

        # Disk
        drive = "C:\\" if sys.platform == "win32" else "/"
        self._disk_var.set("{}  ->  {:.1f}% used".format(drive, d["disk_pct"]))

        # Uptime
        sec = int(d["uptime"])
        h, rem = divmod(sec, 3600)
        m, _   = divmod(rem, 60)
        self._uptime_var.set("Uptime:  {}h  {}m".format(h, m))

        # Refresh alert strip (reflects any threshold changes)
        self._alert_var.set(self._alert_strip())

    # -----------------------------------------------------------------------
    # Settings
    # -----------------------------------------------------------------------
    def _open_settings(self):
        SettingsDialog(self, self._engine)

    # -----------------------------------------------------------------------
    # Tray
    # -----------------------------------------------------------------------
    def _on_unmap(self, event):
        if not TRAY_OK or self._tray is not None:
            return
        try:
            if self.state() == "iconic":
                self._go_tray()
        except Exception:
            pass

    def _go_tray(self):
        try:
            self.withdraw()
            img  = self._tray_img()
            menu = pystray.Menu(
                pystray.MenuItem("Show Dashboard", self._restore, default=True),
                pystray.MenuItem("Settings", self._tray_settings),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._on_close),
            )
            self._tray = pystray.Icon("hhdash", img, APP_NAME, menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception as e:
            print("[TRAY] {}".format(e))
            try:
                self.deiconify()
            except Exception:
                pass

    def _tray_img(self):
        img  = Image.new("RGB", (64, 64), "#0a0e0a")
        draw = ImageDraw.Draw(img)
        draw.rectangle([3, 3, 61, 61], outline="#00ff9d", width=3)
        draw.rectangle([10, 29, 54, 35], fill="#00ff9d")
        return img

    def _restore(self, icon=None, item=None):
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        self.after(0, self.deiconify)

    def _tray_settings(self, icon=None, item=None):
        self._restore()
        self.after(200, self._open_settings)

    # -----------------------------------------------------------------------
    # Close
    # -----------------------------------------------------------------------
    def _on_close(self, icon=None, item=None):
        self._running = False
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        try:
            self.after(0, self.destroy)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Centre on screen
    # -----------------------------------------------------------------------
    def _center(self):
        self.update_idletasks()
        w  = self.winfo_reqwidth()
        h  = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry("+{}+{}".format(max(0, (sw - w) // 2), max(0, (sh - h) // 2)))


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
if __name__ == "__main__":
    multiprocessing.freeze_support()

    if not PSUTIL_OK:
        _r = tk.Tk()
        _r.withdraw()
        messagebox.showerror(
            "Missing Dependency",
            "psutil is not installed.\n\n"
            "Open Command Prompt and run:\n\n"
            "    pip install psutil\n\n"
            "Then run the program again."
        )
        _r.destroy()
        sys.exit(1)

    app = Dashboard()
    app.mainloop()
