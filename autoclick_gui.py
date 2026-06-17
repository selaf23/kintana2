#!/usr/bin/env python3
"""
Simple GUI wrapper for the image-based autoclicker.

Features:
- Tkinter GUI to add/remove target images (copies into `targets/`).
- Edit per-target options (click interval, confidence, jitter, button, enabled).
- Global controls: scan interval, simulate mode, countdown, Start/Stop.
- Background scanning thread reuses the same matching logic as the CLI script.
- Safe default: simulation mode ON. Use real clicks only when you disable simulate
  mode intentionally (and have given accessibility/input privileges on macOS).

Also supports a headless CLI mode for quick demos/tests: `--nogui --simulate --demo`.
"""

import argparse
import glob
import json
import os
import random
import shutil
import sys
import threading
import time
from typing import Any, Dict, List

# Import GUI modules lazily in main when needed so headless mode can run without them
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:
    tk = None  # type: ignore

import pyautogui

# Optional OpenCV
try:
    import cv2  # noqa: F401

    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False

# Defaults
DEFAULT_TARGETS_DIR = "targets"
DEFAULT_SCAN_INTERVAL = 0.5
DEFAULT_CLICK_DELAY = 0.05
DEFAULT_CONFIDENCE = 0.85
DEFAULT_JITTER = 3
DEFAULT_CLICK_COOLDOWN = 1.0
DEFAULT_BUTTON = "left"

pyautogui.FAILSAFE = True


def exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resolve_targets_dir(cli_path: str | None) -> str:
    if cli_path:
        return os.path.abspath(cli_path)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = os.path.join(meipass, DEFAULT_TARGETS_DIR)
            if os.path.isdir(cand):
                return cand
    return os.path.join(exe_dir(), DEFAULT_TARGETS_DIR)


def ensure_targets_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def list_target_images(targets_dir: str) -> List[str]:
    if not os.path.isdir(targets_dir):
        return []
    exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif")
    paths: List[str] = []
    for e in exts:
        paths.extend(glob.glob(os.path.join(targets_dir, e)))
    return sorted(paths)


def load_targets_config(targets_dir: str) -> Dict[str, Any]:
    cfg_path = os.path.join(targets_dir, "config.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            print(
                f"[WARN] config.json has unexpected format (expected object) — ignoring"
            )
            return {}
    except Exception as e:
        print(f"[WARN] Failed to read config.json: {e}")
        return {}


def save_targets_config(targets_dir: str, cfg: Dict[str, Any]) -> None:
    cfg_path = os.path.join(targets_dir, "config.json")
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to write config.json: {e}")


def get_target_setting(img_path: str, cfg: Dict[str, Any], key: str, default: Any):
    basename = os.path.basename(img_path)
    entry = cfg.get(basename) or cfg.get(img_path) or {}
    return entry.get(key, default)


def locate_all(
    img_path: str, confidence: float, simulate: bool = False, demo: bool = False
):
    """Locate all occurrences on screen.

    When simulate=True this function returns an empty list (no matches) unless demo=True,
    where it will return one synthetic match for demonstration.
    """
    if simulate:
        if demo:
            # return a synthetic bounding box tuple (left, top, width, height)
            return [(100, 100, 20, 20)]
        return []

    try:
        if HAVE_CV2:
            return list(pyautogui.locateAllOnScreen(img_path, confidence=confidence))
        return list(pyautogui.locateAllOnScreen(img_path))
    except Exception as e:
        print(f"[WARN] locate_all failed for {img_path}: {e}")
        return []


def center_of(box) -> tuple[int, int]:
    try:
        return int(box.x + box.width / 2), int(box.y + box.height / 2)
    except Exception:
        try:
            cx, cy = pyautogui.center(box)
            return int(cx), int(cy)
        except Exception:
            return int(box[0] + box[2] / 2), int(box[1] + box[3] / 2)


class Scanner:
    """Encapsulates background scanning logic so GUI and CLI can reuse it."""

    def __init__(
        self,
        targets_dir: str,
        scan_interval: float = DEFAULT_SCAN_INTERVAL,
        default_confidence: float = DEFAULT_CONFIDENCE,
        default_jitter: int = DEFAULT_JITTER,
        default_click_delay: float = DEFAULT_CLICK_DELAY,
        default_click_cooldown: float = DEFAULT_CLICK_COOLDOWN,
        default_button: str = DEFAULT_BUTTON,
        simulate: bool = True,
        demo: bool = False,
        log_fn=None,
    ):
        self.targets_dir = targets_dir
        ensure_targets_dir(self.targets_dir)
        self.scan_interval = scan_interval
        self.default_confidence = default_confidence
        self.default_jitter = default_jitter
        self.default_click_delay = default_click_delay
        self.default_click_cooldown = default_click_cooldown
        self.default_button = default_button
        self.simulate = simulate
        self.demo = demo
        self.log_fn = log_fn or (lambda s: print(s))

        self.running = False
        self.thread = None
        # (basename, x, y) -> last click time
        self.last_click_times: Dict[tuple, float] = {}

    def log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.log_fn(f"[{ts}] {msg}")

    def find_and_click_once(self, target_images: List[str], cfg: Dict[str, Any]):
        now = time.time()
        for img in target_images:
            confidence = get_target_setting(
                img, cfg, "confidence", self.default_confidence
            )
            matches = locate_all(
                img, confidence, simulate=self.simulate, demo=self.demo
            )
            if not matches:
                continue
            for m in matches:
                cx, cy = center_of(m)
                basename = os.path.basename(img)
                key = (basename, cx, cy)

                click_cooldown = get_target_setting(
                    img, cfg, "click_cooldown", self.default_click_cooldown
                )
                jitter = get_target_setting(img, cfg, "jitter", self.default_jitter)
                click_delay = get_target_setting(
                    img, cfg, "click_delay", self.default_click_delay
                )
                button = get_target_setting(img, cfg, "button", self.default_button)
                enabled = get_target_setting(img, cfg, "enabled", True)

                if not enabled:
                    continue

                last = self.last_click_times.get(key, 0)
                if now - last < float(click_cooldown):
                    continue

                jx = random.randint(-int(jitter), int(jitter)) if jitter else 0
                jy = random.randint(-int(jitter), int(jitter)) if jitter else 0
                tx, ty = cx + jx, cy + jy

                if self.simulate:
                    self.log(
                        f"SIM CLICK {basename} @ ({tx},{ty}) (cooldown={click_cooldown}s, conf={confidence})"
                    )
                else:
                    try:
                        pyautogui.click(tx, ty, button=button)
                        self.log(
                            f"CLICK {basename} @ ({tx},{ty}) (button={button}, conf={confidence})"
                        )
                    except Exception as e:
                        self.log(
                            f"[ERROR] Failed to click {basename} at ({tx},{ty}): {e}"
                        )

                self.last_click_times[key] = time.time()
                time.sleep(float(click_delay))

    def scan_loop(self):
        self.log("Scanner thread started")
        while self.running:
            cfg = load_targets_config(self.targets_dir)
            imgs = list_target_images(self.targets_dir)
            if not imgs and not self.demo:
                self.log(f"No target images found in {self.targets_dir}")
            else:
                self.find_and_click_once(imgs, cfg)
            time.sleep(self.scan_interval)
        self.log("Scanner thread stopped")

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.scan_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None


# GUI implementation
class AutoclickGUI:
    def __init__(self, targets_dir: str):
        if tk is None:
            raise RuntimeError("Tkinter is not available in this Python environment")

        self.targets_dir = resolve_targets_dir(targets_dir)
        ensure_targets_dir(self.targets_dir)

        self.root = tk.Tk()
        self.root.title("Image Autoclicker — GUI")
        self.root.geometry("900x600")

        # Variables
        self.scan_interval_var = tk.DoubleVar(value=DEFAULT_SCAN_INTERVAL)
        self.simulate_var = tk.BooleanVar(value=True)
        self.countdown_var = tk.IntVar(value=3)

        # Selected target vars
        self.sel_enabled = tk.BooleanVar(value=True)
        self.sel_click_interval = tk.DoubleVar(value=DEFAULT_CLICK_COOLDOWN)
        self.sel_confidence = tk.DoubleVar(value=DEFAULT_CONFIDENCE)
        self.sel_jitter = tk.IntVar(value=DEFAULT_JITTER)
        self.sel_button = tk.StringVar(value=DEFAULT_BUTTON)
        self.sel_click_delay = tk.DoubleVar(value=DEFAULT_CLICK_DELAY)

        # Scanner placeholder
        self.scanner: Scanner | None = None

        # Build UI
        self._build_ui()

        # Log queue
        self._log_queue: List[str] = []
        self._poll_log()

        # Bind close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        left_frame = tk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=8, pady=8)

        lb_label = tk.Label(left_frame, text="Targets (in targets/)")
        lb_label.pack(anchor=tk.W)

        self.listbox = tk.Listbox(left_frame, width=40, height=25)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=6)
        tk.Button(btn_frame, text="Add image", command=self._add_image).pack(
            side=tk.LEFT
        )
        tk.Button(
            btn_frame, text="Remove selected", command=self._remove_selected
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Refresh", command=self._refresh_list).pack(
            side=tk.LEFT
        )

        right_frame = tk.Frame(self.root)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        settings_frame = tk.LabelFrame(right_frame, text="Selected target settings")
        settings_frame.pack(fill=tk.X)

        row = 0
        tk.Checkbutton(settings_frame, text="Enabled", variable=self.sel_enabled).grid(
            row=row, column=0, sticky=tk.W
        )
        row += 1
        tk.Label(settings_frame, text="Click interval (s)").grid(
            row=row, column=0, sticky=tk.W
        )
        tk.Entry(settings_frame, textvariable=self.sel_click_interval, width=10).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        tk.Label(settings_frame, text="Confidence (0-1)").grid(
            row=row, column=0, sticky=tk.W
        )
        tk.Entry(settings_frame, textvariable=self.sel_confidence, width=10).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        tk.Label(settings_frame, text="Jitter (px)").grid(
            row=row, column=0, sticky=tk.W
        )
        tk.Entry(settings_frame, textvariable=self.sel_jitter, width=10).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        tk.Label(settings_frame, text="Click delay (s)").grid(
            row=row, column=0, sticky=tk.W
        )
        tk.Entry(settings_frame, textvariable=self.sel_click_delay, width=10).grid(
            row=row, column=1, sticky=tk.W
        )
        row += 1
        tk.Label(settings_frame, text="Button").grid(row=row, column=0, sticky=tk.W)
        ttk.Combobox(
            settings_frame,
            textvariable=self.sel_button,
            values=("left", "right", "middle"),
            width=8,
        ).grid(row=row, column=1, sticky=tk.W)
        row += 1
        tk.Button(settings_frame, text="Save target", command=self._save_selected).grid(
            row=row, column=0, columnspan=2, pady=6
        )

        global_frame = tk.LabelFrame(right_frame, text="Global controls")
        global_frame.pack(fill=tk.X, pady=8)

        tk.Label(global_frame, text="Scan interval (s)").grid(
            row=0, column=0, sticky=tk.W
        )
        tk.Entry(global_frame, textvariable=self.scan_interval_var, width=8).grid(
            row=0, column=1, sticky=tk.W
        )
        tk.Checkbutton(
            global_frame, text="Simulate (no real clicks)", variable=self.simulate_var
        ).grid(row=0, column=2, padx=12)

        tk.Label(global_frame, text="Countdown before start (s)").grid(
            row=1, column=0, sticky=tk.W
        )
        tk.Entry(global_frame, textvariable=self.countdown_var, width=8).grid(
            row=1, column=1, sticky=tk.W
        )

        ctrl_frame = tk.Frame(global_frame)
        ctrl_frame.grid(row=2, column=0, columnspan=3, pady=8)
        tk.Button(ctrl_frame, text="Start", command=self._start).pack(side=tk.LEFT)
        tk.Button(ctrl_frame, text="Stop", command=self._stop).pack(
            side=tk.LEFT, padx=8
        )

        log_frame = tk.LabelFrame(right_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Fill list on startup
        self._refresh_list()

    # UI helpers
    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        imgs = list_target_images(self.targets_dir)
        for p in imgs:
            self.listbox.insert(tk.END, os.path.basename(p))

    def _on_select(self, evt=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        name = self.listbox.get(idx)
        cfg = load_targets_config(self.targets_dir)
        entry = cfg.get(name, {})
        self.sel_enabled.set(bool(entry.get("enabled", True)))
        self.sel_click_interval.set(
            float(entry.get("click_cooldown", DEFAULT_CLICK_COOLDOWN))
        )
        self.sel_confidence.set(float(entry.get("confidence", DEFAULT_CONFIDENCE)))
        self.sel_jitter.set(int(entry.get("jitter", DEFAULT_JITTER)))
        self.sel_button.set(entry.get("button", DEFAULT_BUTTON))
        self.sel_click_delay.set(float(entry.get("click_delay", DEFAULT_CLICK_DELAY)))

    def _add_image(self):
        path = filedialog.askopenfilename(
            title="Select image to add",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")],
        )
        if not path:
            return
        dest = os.path.join(self.targets_dir, os.path.basename(path))
        try:
            shutil.copy2(path, dest)
            # ensure there's an entry in config
            cfg = load_targets_config(self.targets_dir)
            if os.path.basename(path) not in cfg:
                cfg[os.path.basename(path)] = {}
                save_targets_config(self.targets_dir, cfg)
            self._refresh_list()
            self._log(f"Added {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add image: {e}")

    def _remove_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        name = self.listbox.get(idx)
        if not messagebox.askyesno("Remove", f"Delete {name} from targets/?"):
            return
        try:
            os.remove(os.path.join(self.targets_dir, name))
        except Exception:
            pass
        cfg = load_targets_config(self.targets_dir)
        if name in cfg:
            cfg.pop(name, None)
            save_targets_config(self.targets_dir, cfg)
        self._refresh_list()
        self._log(f"Removed {name}")

    def _save_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("No selection", "Select a target first")
            return
        name = self.listbox.get(sel[0])
        cfg = load_targets_config(self.targets_dir)
        entry = cfg.get(name, {})
        entry["enabled"] = bool(self.sel_enabled.get())
        entry["click_cooldown"] = float(self.sel_click_interval.get())
        entry["confidence"] = float(self.sel_confidence.get())
        entry["jitter"] = int(self.sel_jitter.get())
        entry["button"] = str(self.sel_button.get())
        entry["click_delay"] = float(self.sel_click_delay.get())
        cfg[name] = entry
        save_targets_config(self.targets_dir, cfg)
        self._log(f"Saved config for {name}")

    def _append_log(self, s: str):
        self._log_queue.append(s)

    def _poll_log(self):
        if self._log_queue:
            for s in self._log_queue:
                self.log_text.insert(tk.END, s + "\n")
            self.log_text.see(tk.END)
            self._log_queue.clear()
        self.root.after(200, self._poll_log)

    def _log(self, s: str):
        # Thread-safe enqueue for scanner threads
        self._append_log(s)

    def _start(self):
        if self.scanner and self.scanner.running:
            messagebox.showinfo("Already running", "Scanner is already running")
            return
        # Create scanner with current settings
        simulate = bool(self.simulate_var.get())
        scanner = Scanner(
            self.targets_dir,
            scan_interval=float(self.scan_interval_var.get()),
            default_confidence=float(self.sel_confidence.get()),
            default_jitter=int(self.sel_jitter.get()),
            default_click_delay=float(self.sel_click_delay.get()),
            default_click_cooldown=float(self.sel_click_interval.get()),
            default_button=str(self.sel_button.get()),
            simulate=simulate,
            demo=False,
            log_fn=self._log,
        )
        self.scanner = scanner

        countdown = int(self.countdown_var.get() or 0)
        if countdown > 0:
            self._countdown_and_start(countdown)
        else:
            scanner.start()

    def _countdown_and_start(self, n: int):
        if n <= 0:
            if self.scanner:
                self.scanner.start()
            return
        self._log(f"Starting in {n}...")
        # schedule next second
        self.root.after(1000, lambda: self._countdown_and_start(n - 1))

    def _stop(self):
        if self.scanner:
            self.scanner.stop()
            self._log("Stopped scanner")
            self.scanner = None

    def _on_close(self):
        if self.scanner and self.scanner.running:
            if not messagebox.askyesno("Quit", "Scanner is running. Quit anyway?"):
                return
        if self.scanner:
            self.scanner.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_headless(
    targets_dir: str, simulate: bool, demo: bool, duration: float, scan_interval: float
):
    targets_dir = resolve_targets_dir(targets_dir)
    scanner = Scanner(
        targets_dir,
        scan_interval=scan_interval,
        simulate=simulate,
        demo=demo,
        log_fn=lambda s: print(s),
    )
    scanner.start()
    try:
        if duration and duration > 0:
            time.sleep(duration)
        else:
            # run until Ctrl-C
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        scanner.stop()


def main():
    parser = argparse.ArgumentParser(description="Autoclicker GUI / headless runner")
    parser.add_argument(
        "--targets", help="Path to targets folder (default: targets next to script)"
    )
    parser.add_argument("--nogui", action="store_true", help="Run in headless CLI mode")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Simulate clicks (no real mouse click). In GUI default is ON",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Headless demo: simulate detection even without real images",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Duration (s) to run in headless demo; default 2s",
    )
    parser.add_argument(
        "--scan-interval",
        type=float,
        default=DEFAULT_SCAN_INTERVAL,
        help="Scan interval for headless run",
    )

    args = parser.parse_args()

    targets_dir = resolve_targets_dir(args.targets)

    if args.nogui:
        # default to simulate True in headless unless user specifically provided --simulate
        simulate = bool(args.simulate) if args.simulate else True
        run_headless(
            targets_dir,
            simulate=simulate,
            demo=args.demo,
            duration=args.duration,
            scan_interval=args.scan_interval,
        )
        return

    # GUI mode
    app = AutoclickGUI(targets_dir)
    app.run()


if __name__ == "__main__":
    main()
