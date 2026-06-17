"""
Simple Autoclicker
-------------------
Clicks repeatedly at a fixed screen position (e.g. a spot on a game's
canvas in your browser), with a configurable interval.

SETUP (run these once on your own machine, in a terminal):
    pip install pyautogui pynput

HOW IT WORKS:
    1. Run the script.
    2. It gives you a few seconds to move your mouse to the spot you
       want to click (e.g. the button/canvas area in your game), OR
       you can hardcode the X, Y coordinates below.
    3. Press F6 to start/stop clicking. Press Esc to quit entirely.

NOTES:
    - This controls your REAL mouse cursor. Don't move it elsewhere
      while it's running, or clicks will land in the wrong place.
    - Some games detect/ban automated clicking. Check the game's
      rules before using this, and use at your own risk.
"""

import time
import threading
import pyautogui
from pynput import keyboard

# ---------------- CONFIGURATION ----------------
CLICK_INTERVAL = 0.1     # seconds between clicks (0.1 = 10 clicks/sec)
USE_CURRENT_MOUSE_POS = True   # True = click wherever mouse is when started
FIXED_X, FIXED_Y = 500, 500    # used only if USE_CURRENT_MOUSE_POS = False
# -------------------------------------------------

clicking = False
running = True


def click_loop():
    while running:
        if clicking:
            if USE_CURRENT_MOUSE_POS:
                pyautogui.click()
            else:
                pyautogui.click(FIXED_X, FIXED_Y)
            time.sleep(CLICK_INTERVAL)
        else:
            time.sleep(0.05)


def on_press(key):
    global clicking, running
    if key == keyboard.Key.f6:
        clicking = not clicking
        state = "STARTED" if clicking else "STOPPED"
        print(f"[Autoclicker] {state}")
    elif key == keyboard.Key.esc:
        print("[Autoclicker] Exiting...")
        running = False
        return False  # stops the listener


def main():
    print("=" * 50)
    print("Autoclicker ready.")
    print("Press F6 to start/stop clicking.")
    print("Press Esc to quit.")
    if USE_CURRENT_MOUSE_POS:
        print("Mode: clicks at wherever your mouse is positioned.")
    else:
        print(f"Mode: clicks at fixed position ({FIXED_X}, {FIXED_Y})")
    print("=" * 50)

    t = threading.Thread(target=click_loop, daemon=True)
    t.start()

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()