#!/usr/bin/env python3
"""
Autoclicker that finds target images in `targets/` and clicks them.

Controls:
 - F6 : toggle start/stop scanning & clicking
 - Esc : exit program

Behavior:
 - Scans all images in the `targets/` directory and clicks any matches.
 - Uses OpenCV-backed confidence matching when `opencv-python` is installed.
 - Per-target options can be provided in `targets/config.json` (see README).

Safety:
 - This program controls your REAL mouse. Do not run it unless you understand
   the consequences and you have accessibility/input-monitoring permission on
   macOS. Use F6 to start/stop and Esc to quit.
"""

import argparse
import glob
import json
import os
import random
import sys
import threading
import time
from typing import Any, Dict, List

import pyautogui
from pynput import keyboard

# Optional: OpenCV improves image recognition accuracy (pyautogui can use it
# to support the `confidence` parameter).
try:
    import cv2  # noqa: F401

    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False

# Defaults (tweakable via CLI)
DEFAULT_TARGETS_DIR = "targets"
DEFAULT_SCAN_INTERVAL = 0.5  # seconds between scans
DEFAULT_CLICK_DELAY = 0.05  # delay between clicks when multiple targets found
DEFAULT_CONFIDENCE = 0.85  # only used if OpenCV is available
DEFAULT_JITTER = 3  # pixels random offset to avoid exact-repeat clicks
DEFAULT_CLICK_COOLDOWN = (
    1.0  # default seconds to wait before clicking same (img,x,y) again
)
DEFAULT_BUTTON = "left"

# Global run flags used by keyboard callback and the scan thread
clicking = False
running = True

# Keep track of last-click times per (image basename, x, y) to avoid re-clicking too
# fast when scans are frequent.
last_click_times: Dict[tuple, float] = {}

pyautogui.FAILSAFE = True


def exe_dir() -> str:
    """Return directory where the script or executable lives."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resolve_targets_dir(cli_path: str | None) -> str:
    """Resolve the targets directory.

    Order of resolution:
      1) CLI override if provided
      2) If frozen bundle contains an embedded targets/ folder, use it
      3) Otherwise use a `targets/` folder next to the script/executable
    """
    if cli_path:
        return os.path.abspath(cli_path)

    # If running from a PyInstaller bundle, first check the bundle temp dir
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = os.path.join(meipass, DEFAULT_TARGETS_DIR)
            if os.path.isdir(cand):
                return cand

    # Fallback: `targets/` next to the script/executable
    return os.path.join(exe_dir(), DEFAULT_TARGETS_DIR)


def list_target_images(targets_dir: str) -> List[str]:
    """Return sorted list of image file paths inside targets_dir."""
    if not os.path.isdir(targets_dir):
        return []
    exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif")
    paths: List[str] = []
    for e in exts:
        paths.extend(glob.glob(os.path.join(targets_dir, e)))
    return sorted(paths)


def load_targets_config(targets_dir: str) -> Dict[str, Any]:
    """Load `targets/config.json` if present. Returns mapping by filename (basename)."""
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


def locate_all(img_path: str, confidence: float) -> List[pyautogui.Box]:
    """Locate all occurrences of `img_path` on screen.

    If OpenCV is available the `confidence` parameter is used; otherwise a
    basic (exact) search is performed.
    """
    try:
        if HAVE_CV2:
            return list(pyautogui.locateAllOnScreen(img_path, confidence=confidence))
        return list(pyautogui.locateAllOnScreen(img_path))
    except Exception as e:
        # PyAutoGUI raises when the image format isn't supported or other issues
        print(f"[WARN] locate_all failed for {img_path}: {e}")
        return []


def center_of(box) -> tuple[int, int]:
    """Return integer (x,y) center coords for a pyautogui Box or tuple."""
    try:
        # pyautogui.center returns a Point-like object with x,y attributes
        return int(box.x + box.width / 2), int(box.y + box.height / 2)
    except Exception:
        # Fallback: some pyautogui versions return a tuple
        try:
            cx, cy = pyautogui.center(box)
            return int(cx), int(cy)
        except Exception:
            # Last fallback: try to index
            return int(box[0] + box[2] / 2), int(box[1] + box[3] / 2)


def get_target_setting(img_path: str, cfg: Dict[str, Any], key: str, default: Any):
    """Return per-target setting from config (lookup by basename)."""
    basename = os.path.basename(img_path)
    entry = cfg.get(basename) or cfg.get(img_path) or {}
    return entry.get(key, default)


def find_and_click_once(
    target_images: List[str],
    global_confidence: float,
    global_jitter: int,
    global_click_delay: float,
    global_click_cooldown: float,
    global_button: str,
    cfg: Dict[str, Any],
):
    """Find matches for each target image and click them once respecting per-target cooldowns."""
    global last_click_times

    now = time.time()

    for img in target_images:
        # Per-target confidence (falls back to the global confidence arg)
        confidence = get_target_setting(img, cfg, "confidence", global_confidence)
        matches = locate_all(img, confidence)
        if not matches:
            continue

        for m in matches:
            cx, cy = center_of(m)
            basename = os.path.basename(img)
            key = (basename, cx, cy)

            # Determine per-target cooldown and other overrides
            click_cooldown = get_target_setting(
                img, cfg, "click_cooldown", global_click_cooldown
            )
            jitter = get_target_setting(img, cfg, "jitter", global_jitter)
            click_delay = get_target_setting(
                img, cfg, "click_delay", global_click_delay
            )
            button = get_target_setting(img, cfg, "button", global_button)
            enabled = get_target_setting(img, cfg, "enabled", True)

            if not enabled:
                continue

            last = last_click_times.get(key, 0)
            if now - last < float(click_cooldown):
                # skip because we clicked this spot recently
                continue

            # Add a small random jitter so clicks are not identical every pass
            jx = random.randint(-int(jitter), int(jitter)) if jitter else 0
            jy = random.randint(-int(jitter), int(jitter)) if jitter else 0
            tx, ty = cx + jx, cy + jy

            try:
                pyautogui.click(tx, ty, button=button)
                last_click_times[key] = time.time()
                print(
                    f"[CLICK] {basename} @ ({tx},{ty}) (cooldown={click_cooldown}s, confidence={confidence})"
                )
            except Exception as e:
                print(f"[ERROR] Failed to click {img} at ({tx},{ty}): {e}")

            # Small pause between clicks to avoid firing too fast
            time.sleep(float(click_delay))


def scan_loop(
    targets_dir: str,
    confidence: float,
    scan_interval: float,
    jitter: int,
    click_delay: float,
    click_cooldown: float,
    button: str,
):
    """Background loop that scans the screen and clicks when enabled."""
    global running, clicking

    while running:
        if clicking:
            # Reload config each pass so changes while running are honored
            cfg = load_targets_config(targets_dir)
            target_images = list_target_images(targets_dir)
            if not target_images:
                print(
                    f"[WARN] No target images found in {targets_dir}. Add PNG/JPG files there."
                )
            else:
                find_and_click_once(
                    target_images,
                    confidence,
                    jitter,
                    click_delay,
                    click_cooldown,
                    button,
                    cfg,
                )

            time.sleep(scan_interval)
        else:
            # idle sleep when paused
            time.sleep(0.1)


def on_press(key):
    """Keyboard callback: F6 toggles clicking, Esc exits."""
    global clicking, running
    try:
        if key == keyboard.Key.f6:
            clicking = not clicking
            state = "STARTED" if clicking else "STOPPED"
            print(f"[Autoclicker] {state}")
        elif key == keyboard.Key.esc:
            print("[Autoclicker] Exiting...")
            running = False
            return False
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Image-based autoclicker — place target images in a `targets/` folder next to the executable."
    )
    parser.add_argument(
        "-t",
        "--targets",
        help="Path to targets folder (default: targets next to executable)",
    )
    parser.add_argument(
        "-C",
        "--confidence",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help="Matching confidence (only with OpenCV). Default: %(default)s",
    )
    parser.add_argument(
        "--scan-interval",
        type=float,
        default=DEFAULT_SCAN_INTERVAL,
        help="Seconds between screen scans. Default: %(default)s",
    )
    parser.add_argument(
        "--click-delay",
        type=float,
        default=DEFAULT_CLICK_DELAY,
        help="Delay (s) between clicks when multiple targets found. Default: %(default)s",
    )
    parser.add_argument(
        "--jitter",
        type=int,
        default=DEFAULT_JITTER,
        help="Random pixel jitter to apply to clicks. Default: %(default)s",
    )
    parser.add_argument(
        "--click-cooldown",
        type=float,
        default=DEFAULT_CLICK_COOLDOWN,
        help="Default cooldown (s) before re-clicking same (image,x,y). This can be overridden per-target in targets/config.json",
    )
    parser.add_argument(
        "--button",
        choices=("left", "right", "middle"),
        default=DEFAULT_BUTTON,
        help="Mouse button to use for clicks",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Start clicking immediately (dangerous). By default you must press F6 to start.",
    )

    args = parser.parse_args()

    targets_dir = resolve_targets_dir(args.targets)

    print("=" * 60)
    print("Image Autoclicker")
    print(f"Targets dir: {targets_dir}")
    if HAVE_CV2:
        print(f"OpenCV available — using confidence={args.confidence}")
    else:
        print(
            "OpenCV not found — running exact-image searches (install opencv-python for better results)"
        )
    print("Controls: press F6 to start/stop clicking, Esc to exit")
    print("=" * 60)

    # Start scanning thread
    t = threading.Thread(
        target=scan_loop,
        args=(
            targets_dir,
            args.confidence,
            args.scan_interval,
            args.jitter,
            args.click_delay,
            args.click_cooldown,
            args.button,
        ),
        daemon=True,
    )
    t.start()

    # Optionally start immediately
    global clicking
    clicking = bool(args.auto_start)

    # Keyboard listener blocks until Esc is pressed (or listener returns False)
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    # Clean shutdown
    print("Waiting for background thread to finish...")
    t.join(timeout=1)
    print("Goodbye")


if __name__ == "__main__":
    main()
