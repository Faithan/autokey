"""Key spammer with GUI or CLI.

Run without arguments to open the GUI (double-click friendly). Example CLI usage:
    python spam_key.py --key space --interval 0.1 --duration 10 --start-delay 3

- GUI lets you pick the key, interval, duration (0 = until Stop), and start delay.
- Sends key presses to the active window. Keep the target window focused before the timer ends.
- Press the Stop button (GUI) or Ctrl+C (CLI) to abort early.
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


class SpammerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Key Spammer")
        self.root.resizable(False, False)

        self.key_var = tk.StringVar(value="space")
        self.interval_var = tk.StringVar(value="0.2")
        self.duration_var = tk.StringVar(value="10")
        self.start_delay_var = tk.StringVar(value="3")
        self.hold_var = tk.StringVar(value="0")
        self.backend_var = tk.StringVar(value="pyautogui")
        self.status_var = tk.StringVar(value="Idle")

        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        padding = {"padx": 8, "pady": 4}

        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Key (e.g., space, a, enter)").grid(row=0, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.key_var, width=20).grid(row=0, column=1, **padding)

        ttk.Label(frm, text="Interval seconds").grid(row=1, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.interval_var, width=20).grid(row=1, column=1, **padding)

        ttk.Label(frm, text="Duration seconds (0 = until Stop)").grid(row=2, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.duration_var, width=20).grid(row=2, column=1, **padding)

        ttk.Label(frm, text="Start delay seconds").grid(row=3, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.start_delay_var, width=20).grid(row=3, column=1, **padding)

        ttk.Label(frm, text="Hold seconds (0 = tap)").grid(row=4, column=0, sticky="w", **padding)
        ttk.Entry(frm, textvariable=self.hold_var, width=20).grid(row=4, column=1, **padding)

        ttk.Label(frm, text="Send method").grid(row=5, column=0, sticky="w", **padding)
        backend_box = ttk.Combobox(
            frm,
            textvariable=self.backend_var,
            values=["pyautogui"] + (["pydirectinput"] if HAS_PYDIRECT else []),
            state="readonly",
            width=17,
        )
        backend_box.grid(row=5, column=1, **padding)

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(8, 4))
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start_spam)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_spam, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn.grid(row=0, column=1, padx=6)

        # Built-in test pad: click inside, press Start, and you should see characters appear.
        ttk.Label(frm, text="Test pad (click here, then Start)").grid(row=7, column=0, columnspan=2, sticky="w", **padding)
        self.test_pad = tk.Text(frm, width=38, height=4)
        self.test_pad.grid(row=8, column=0, columnspan=2, **padding)
        ttk.Button(frm, text="Clear test pad", command=lambda: self.test_pad.delete("1.0", tk.END)).grid(
            row=9, column=0, columnspan=2, pady=(0, 6)
        )

        ttk.Label(frm, textvariable=self.status_var, foreground="blue").grid(
            row=10, column=0, columnspan=2, sticky="w", **padding
        )

    def start_spam(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        key = self.key_var.get().strip()
        try:
            interval = float(self.interval_var.get())
            duration = float(self.duration_var.get())
            start_delay = float(self.start_delay_var.get())
            hold = float(self.hold_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Interval, duration, start delay, and hold must be numbers.")
            return

        if not key:
            messagebox.showerror("Invalid input", "Key cannot be empty.")
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
            target=self._run_spammer, args=(key, interval, duration, start_delay, hold, backend), daemon=True
        )
        self._thread.start()
        self._set_running_state(True)
        self.status_var.set(
            f"Running: '{key}' every {interval}s for {'until Stop' if duration == 0 else duration}s via {backend}"
        )

    def _run_spammer(
        self, key: str, interval: float, duration: float, start_delay: float, hold: float, backend: str
    ) -> None:
        try:
            presses = spam_key(key, interval, duration, start_delay, hold, self._stop_event, backend)
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
        self.root.destroy()


def launch_gui() -> None:
    root = tk.Tk()
    SpammerApp(root)
    root.mainloop()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spam a key at a fixed interval.")
    parser.add_argument("--gui", action="store_true", help="Force GUI mode (default when no args).")
    parser.add_argument("--key", help="Key name to press (e.g., 'space', 'a', 'enter').")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between presses (default: 0.2).")
    parser.add_argument(
        "--duration",
        type=float,
        default=10,
        help="How long to run in seconds. Use 0 to run until Ctrl+C (default: 10).",
    )
    parser.add_argument(
        "--start-delay", type=float, default=3, help="Delay before starting so you can focus the window (default: 3)."
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    if not argv:
        launch_gui()
        return

    args = parse_args(argv)
    if args.gui:
        launch_gui()
        return

    if not args.key:
        sys.exit("--key is required in CLI mode. Omit arguments to open the GUI.")

    presses = spam_key(args.key, args.interval, args.duration, args.start_delay)
    print(f"Done. Sent {presses} presses of '{args.key}'.")


if __name__ == "__main__":
    main(sys.argv[1:])
