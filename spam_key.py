"""Key spammer / auto-clicker with GUI or CLI.

Run without arguments to open the GUI (double-click friendly). Example CLI usage:
    python spam_key.py --mode key --key space --interval 0.1 --duration 10 --start-delay 3 --hold 0
    python spam_key.py --mode click --button left --interval 0.05 --duration 5 --hold 0

- GUI lets you pick key/click mode, interval, duration (0 = until Stop), start delay, hold time, backend, and hotkey.
- Sends to the active window. Keep the target window focused before the timer ends.
- Press Stop (GUI) or the configured global hotkey to toggle start/stop; Ctrl+C also works in CLI.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import pyautogui
except ImportError as exc:  # pragma: no cover - dependency guard
    sys.exit("pyautogui is required. Install with: python -m pip install pyautogui")

# Optional: pydirectinput can bypass some games that block pyautogui.
try:  # pragma: no cover - optional dependency
    import pydirectinput  # type: ignore
    HAS_PYDIRECT = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PYDIRECT = False

# Optional: keyboard allows global hotkeys for start/stop.
try:  # pragma: no cover - optional dependency
    import keyboard  # type: ignore
    HAS_KEYBOARD = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_KEYBOARD = False

# Optional: pygetwindow lets us activate a specific window by title (Windows/macOS/X11).
try:  # pragma: no cover - optional dependency
    import pygetwindow as gw  # type: ignore
    HAS_GW = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_GW = False


def _wait_with_cancel(seconds: float, stop_event: threading.Event | None) -> None:
    """Sleep for `seconds` but respond quickly to stop requests."""
    if seconds <= 0:
        return
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if stop_event and stop_event.is_set():
            return
        time.sleep(0.05)


def spam_key(
    key: str,
    interval: float,
    duration: float,
    start_delay: float,
    hold: float,
    target_window: str | None,
    force_focus: bool,
    stop_event: threading.Event | None = None,
    backend: str = "pyautogui",
) -> int:
    """Send key presses at a fixed interval for the given duration.

    Returns the number of presses performed.
    """
    if interval <= 0:
        raise ValueError("interval must be > 0")
    if duration < 0:
        raise ValueError("duration must be >= 0")
    if start_delay < 0:
        raise ValueError("start_delay must be >= 0")
    if hold < 0:
        raise ValueError("hold must be >= 0")
    if target_window and not HAS_GW:
        raise RuntimeError("pygetwindow is required for target window. Install with: python -m pip install pygetwindow")

    # Choose which sender to use.
    if backend == "pydirectinput":
        if not HAS_PYDIRECT:
            raise RuntimeError("pydirectinput is not installed. Install with: python -m pip install pydirectinput")
        sender_down = lambda k: pydirectinput.keyDown(k)  # type: ignore[arg-type]
        sender_up = lambda k: pydirectinput.keyUp(k)  # type: ignore[arg-type]
        sender_press = lambda k: pydirectinput.press(k)  # type: ignore[arg-type]
    else:
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0  # run as fast as the interval allows
        sender_down = lambda k: pyautogui.keyDown(k)
        sender_up = lambda k: pyautogui.keyUp(k)
        sender_press = lambda k: pyautogui.press(k)

    target = None
    if target_window and HAS_GW:
        matches = gw.getWindowsWithTitle(target_window)
        if not matches:
            raise RuntimeError(f"No window found with title containing '{target_window}'.")
        target = matches[0]

    if start_delay:
        _wait_with_cancel(start_delay, stop_event)
        if stop_event and stop_event.is_set():
            return 0

    end_at = None if duration == 0 else time.monotonic() + duration
    presses = 0

    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            if end_at is not None and time.monotonic() >= end_at:
                break
            if target and force_focus:
                try:
                    target.activate()
                except Exception:
                    pass
            if hold > 0:
                sender_down(key)
                _wait_with_cancel(hold, stop_event)
                sender_up(key)
            else:
                sender_press(key)
            presses += 1
            _wait_with_cancel(interval, stop_event)
    except KeyboardInterrupt:
        print("\nStopped early (Ctrl+C).", flush=True)

    return presses


def spam_click(
    button: str,
    interval: float,
    duration: float,
    start_delay: float,
    hold: float,
    target_window: str | None,
    force_focus: bool,
    stop_event: threading.Event | None = None,
    backend: str = "pyautogui",
) -> int:
    """Spam mouse clicks at a fixed interval."""
    if interval <= 0:
        raise ValueError("interval must be > 0")
    if duration < 0:
        raise ValueError("duration must be >= 0")
    if start_delay < 0:
        raise ValueError("start_delay must be >= 0")
    if hold < 0:
        raise ValueError("hold must be >= 0")
    if target_window and not HAS_GW:
        raise RuntimeError("pygetwindow is required for target window. Install with: python -m pip install pygetwindow")

    if backend == "pydirectinput":
        if not HAS_PYDIRECT:
            raise RuntimeError("pydirectinput is not installed. Install with: python -m pip install pydirectinput")
        click_down = lambda b: pydirectinput.mouseDown(button=b)  # type: ignore[arg-type]
        click_up = lambda b: pydirectinput.mouseUp(button=b)  # type: ignore[arg-type]
        click_once = lambda b: pydirectinput.click(button=b)  # type: ignore[arg-type]
    else:
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        click_down = lambda b: pyautogui.mouseDown(button=b)
        click_up = lambda b: pyautogui.mouseUp(button=b)
        click_once = lambda b: pyautogui.click(button=b)

    target = None
    if target_window and HAS_GW:
        matches = gw.getWindowsWithTitle(target_window)
        if not matches:
            raise RuntimeError(f"No window found with title containing '{target_window}'.")
        target = matches[0]

    if start_delay:
        _wait_with_cancel(start_delay, stop_event)
        if stop_event and stop_event.is_set():
            return 0

    end_at = None if duration == 0 else time.monotonic() + duration
    clicks = 0

    while True:
        if stop_event and stop_event.is_set():
            break
        if end_at is not None and time.monotonic() >= end_at:
            break
        if hold > 0:
            click_down(button)
            _wait_with_cancel(hold, stop_event)
            click_up(button)
        else:
            click_once(button)
        if target and force_focus:
            try:
                target.activate()
            except Exception:
                pass
        clicks += 1
        _wait_with_cancel(interval, stop_event)

    return clicks


class SpammerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Key Spammer / Clicker")
        self.root.resizable(False, False)

        self.mode_var = tk.StringVar(value="key")  # key or click
        self.key_var = tk.StringVar(value="space")
        self.mouse_button_var = tk.StringVar(value="left")
        self.interval_var = tk.StringVar(value="0.2")
        self.duration_var = tk.StringVar(value="10")
        self.start_delay_var = tk.StringVar(value="3")
        self.hold_var = tk.StringVar(value="0")
        self.target_window_var = tk.StringVar(value="")
        self.force_focus_var = tk.BooleanVar(value=False)
        self.backend_var = tk.StringVar(value="pyautogui")
        self.hotkey_var = tk.StringVar(value="k")
        self.status_var = tk.StringVar(value="Idle")

        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._hotkey_registered = False
        self._hotkey_handle = None

        self._build_ui()
        self._register_hotkey()
        self.mode_var.trace_add("write", lambda *_: self._update_mode_fields())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        padding = {"padx": 8, "pady": 4}

        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Mode").grid(row=0, column=0, sticky="w", **padding)
        mode_box = ttk.Combobox(frm, textvariable=self.mode_var, values=["key", "click"], state="readonly", width=17)
        mode_box.grid(row=0, column=1, **padding)

        ttk.Label(frm, text="Key (e.g., space, a, enter)").grid(row=1, column=0, sticky="w", **padding)
        self.key_entry = ttk.Entry(frm, textvariable=self.key_var, width=20)
        self.key_entry.grid(row=1, column=1, **padding)

        ttk.Label(frm, text="Mouse button (left/right/middle)").grid(row=2, column=0, sticky="w", **padding)
        self.mouse_entry = ttk.Entry(frm, textvariable=self.mouse_button_var, width=20)
        self.mouse_entry.grid(row=2, column=1, **padding)

        ttk.Label(frm, text="Interval seconds").grid(row=3, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.interval_var, width=20).grid(row=3, column=1, **padding)

        ttk.Label(frm, text="Duration seconds (0 = until Stop)").grid(row=4, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.duration_var, width=20).grid(row=4, column=1, **padding)

        ttk.Label(frm, text="Start delay seconds").grid(row=5, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.start_delay_var, width=20).grid(row=5, column=1, **padding)

        ttk.Label(frm, text="Hold seconds (0 = tap)").grid(row=6, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.hold_var, width=20).grid(row=6, column=1, **padding)

        ttk.Label(frm, text="Send method").grid(row=7, column=0, sticky="w", **padding)
        backend_box = ttk.Combobox(
            frm,
            textvariable=self.backend_var,
            values=["pyautogui"] + (["pydirectinput"] if HAS_PYDIRECT else []),
            state="readonly",
            width=17,
        )
        backend_box.grid(row=7, column=1, **padding)

        ttk.Label(frm, text="Target window (pick or type)").grid(row=8, column=0, sticky="w", **padding)
        window_row = ttk.Frame(frm)
        window_row.grid(row=8, column=1, sticky="w", **padding)
        self.window_combo = ttk.Combobox(window_row, width=18, values=[])
        self.window_combo.grid(row=0, column=0, padx=(0, 6))
        ttk.Button(window_row, text="Refresh", command=self._refresh_windows).grid(row=0, column=1)
        ttk.Entry(frm, textvariable=self.target_window_var, width=20).grid(row=9, column=1, **padding)
        ttk.Checkbutton(frm, text="Force focus each action", variable=self.force_focus_var).grid(
            row=10, column=0, columnspan=2, sticky="w", **padding
        )

        ttk.Label(frm, text="Start/Stop hotkey (global)").grid(row=11, column=0, sticky="w", **padding)
        hotkey_row = ttk.Frame(frm)
        hotkey_row.grid(row=11, column=1, sticky="w", **padding)
        hotkey_entry = ttk.Entry(hotkey_row, textvariable=self.hotkey_var, width=10)
        hotkey_entry.grid(row=0, column=0, padx=(0, 6))
        ttk.Button(hotkey_row, text="Apply", command=self._register_hotkey).grid(row=0, column=1)
        if not HAS_KEYBOARD:
            ttk.Label(frm, text="Install 'keyboard' for hotkey", foreground="red").grid(row=12, column=0, columnspan=2, sticky="w", **padding)

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=13, column=0, columnspan=2, pady=(8, 4))
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start_spam)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_spam, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn.grid(row=0, column=1, padx=6)

        # Built-in test pad: click inside, press Start, and you should see characters appear.
        ttk.Label(frm, text="Test pad (click here, then Start)").grid(row=14, column=0, columnspan=2, sticky="w", **padding)
        self.test_pad = tk.Text(frm, width=38, height=4)
        self.test_pad.grid(row=15, column=0, columnspan=2, **padding)
        ttk.Button(frm, text="Clear test pad", command=lambda: self.test_pad.delete("1.0", tk.END)).grid(
            row=16, column=0, columnspan=2, pady=(0, 6)
        )

        ttk.Label(frm, textvariable=self.status_var, foreground="blue").grid(
            row=17, column=0, columnspan=2, sticky="w", **padding
        )

        self._update_mode_fields()
        self._refresh_windows()

    def _update_mode_fields(self) -> None:
        mode = self.mode_var.get()
        if mode == "key":
            self.key_entry.config(state=tk.NORMAL)
            self.mouse_entry.config(state=tk.DISABLED)
        else:
            self.key_entry.config(state=tk.DISABLED)
            self.mouse_entry.config(state=tk.NORMAL)

    def _refresh_windows(self) -> None:
        if not HAS_GW:
            self.window_combo['values'] = []
            if not self.target_window_var.get():
                self.target_window_var.set("Install pygetwindow for window list")
            return
        titles = [t for t in gw.getAllTitles() if t.strip()]
        self.window_combo['values'] = titles
        if titles and not self.window_combo.get():
            self.window_combo.set(titles[0])

    def _register_hotkey(self) -> None:
        # Remove previous hotkey if any
        if self._hotkey_registered and self._hotkey_handle and HAS_KEYBOARD:
            try:
                keyboard.remove_hotkey(self._hotkey_handle)
            except Exception:
                pass
            self._hotkey_registered = False
            self._hotkey_handle = None

        hotkey = self.hotkey_var.get().strip()
        if not hotkey:
            self.status_var.set("Hotkey not set")
            return

        if not HAS_KEYBOARD:
            self.status_var.set("Install 'keyboard' for hotkey support")
            return

        try:
            self._hotkey_handle = keyboard.add_hotkey(hotkey, lambda: self.root.after(0, self._hotkey_toggle))
            self._hotkey_registered = True
            self.status_var.set(f"Hotkey '{hotkey}' toggles start/stop")
        except Exception as exc:  # pragma: no cover - best effort
            self.status_var.set(f"Hotkey failed: {exc}")

    def _hotkey_toggle(self) -> None:
        # Toggle run state; ensure UI thread handles it
        if self._thread and self._thread.is_alive():
            self.stop_spam()
        else:
            self.start_spam()

    def start_spam(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        mode = self.mode_var.get()
        key = self.key_var.get().strip()
        mouse_button = self.mouse_button_var.get().strip().lower()
        try:
            interval = float(self.interval_var.get())
            duration = float(self.duration_var.get())
            start_delay = float(self.start_delay_var.get())
            hold = float(self.hold_var.get())
            target_window = self.window_combo.get().strip() or self.target_window_var.get().strip() or None
            force_focus = bool(self.force_focus_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Interval, duration, start delay, and hold must be numbers.")
            return

        if mode == "key" and not key:
            messagebox.showerror("Invalid input", "Key cannot be empty.")
            return
        if mode == "click" and not mouse_button:
            messagebox.showerror("Invalid input", "Mouse button cannot be empty (left/right/middle).")
            return

        try:
            if interval <= 0 or duration < 0 or start_delay < 0 or hold < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Invalid input", "Interval must be > 0; duration, start delay, and hold must be >= 0."
            )
            return

        backend = self.backend_var.get()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run_spammer,
            args=(mode, key, mouse_button, interval, duration, start_delay, hold, target_window, force_focus, backend),
            daemon=True,
        )
        self._thread.start()
        self._set_running_state(True)
        self.status_var.set(
            (
                f"Running {mode}: '{key if mode=='key' else mouse_button}' every {interval}s for "
                f"{'until Stop' if duration == 0 else duration}s via {backend}"
            )
        )

    def _run_spammer(
        self,
        mode: str,
        key: str,
        mouse_button: str,
        interval: float,
        duration: float,
        start_delay: float,
        hold: float,
        target_window: str | None,
        force_focus: bool,
        backend: str,
    ) -> None:
        try:
            if mode == "click":
                presses = spam_click(
                    mouse_button, interval, duration, start_delay, hold, target_window, force_focus, self._stop_event, backend
                )
                msg = f"Finished. Sent {presses} clicks of '{mouse_button}'." if not self._stop_event.is_set() else "Stopped."
            else:
                presses = spam_key(
                    key, interval, duration, start_delay, hold, target_window, force_focus, self._stop_event, backend
                )
                msg = f"Finished. Sent {presses} presses of '{key}'." if not self._stop_event.is_set() else "Stopped."
            self.root.after(0, self._finish_run, msg)
        except Exception as exc:  # pragma: no cover - surfaced to UI
            self.root.after(0, self._finish_run, f"Error: {exc}")

    def _finish_run(self, message: str) -> None:
        self.status_var.set(message)
        self._set_running_state(False)

    def stop_spam(self) -> None:
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()
            self.status_var.set("Stopping...")

    def _set_running_state(self, running: bool) -> None:
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)

    def _on_close(self) -> None:
        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()
            if self._hotkey_registered and self._hotkey_handle and HAS_KEYBOARD:
                try:
                    keyboard.remove_hotkey(self._hotkey_handle)
                except Exception:
                    pass
        self.root.destroy()


def launch_gui() -> None:
    root = tk.Tk()
    SpammerApp(root)
    root.mainloop()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spam a key or mouse clicks at a fixed interval.")
    parser.add_argument("--gui", action="store_true", help="Force GUI mode (default when no args).")
    parser.add_argument("--mode", choices=["key", "click"], default="key", help="Run in key or click mode (default: key).")
    parser.add_argument("--key", help="Key name to press (e.g., 'space', 'a', 'enter').")
    parser.add_argument("--button", default="left", help="Mouse button for click mode (left/right/middle).")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between actions (default: 0.2).")
    parser.add_argument(
        "--duration",
        type=float,
        default=10,
        help="How long to run in seconds. Use 0 to run until Ctrl+C (default: 10).",
    )
    parser.add_argument(
        "--start-delay", type=float, default=3, help="Delay before starting so you can focus the window (default: 3)."
    )
    parser.add_argument("--hold", type=float, default=0, help="Hold time in seconds (0 = tap).")
    parser.add_argument("--backend", choices=["pyautogui", "pydirectinput"], default="pyautogui", help="Input backend.")
    parser.add_argument("--target-window", help="Substring of target window title to focus before actions.")
    parser.add_argument("--force-focus", action="store_true", help="Activate target window before each action.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    if not argv:
        launch_gui()
        return

    args = parse_args(argv)
    if args.gui:
        launch_gui()
        return

    if args.mode == "click":
        presses = spam_click(
            args.button,
            args.interval,
            args.duration,
            args.start_delay,
            args.hold,
            args.target_window,
            args.force_focus,
            None,
            args.backend,
        )
        print(f"Done. Sent {presses} clicks of '{args.button}'.")
    else:
        if not args.key:
            sys.exit("--key is required in key mode. Omit arguments to open the GUI.")
        presses = spam_key(
            args.key,
            args.interval,
            args.duration,
            args.start_delay,
            args.hold,
            args.target_window,
            args.force_focus,
            None,
            args.backend,
        )
        print(f"Done. Sent {presses} presses of '{args.key}'.")


if __name__ == "__main__":
    main(sys.argv[1:])
