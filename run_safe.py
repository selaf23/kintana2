#!/usr/bin/env python3
"""
Safe runner for main.py: monkeypatches pyautogui.click to print instead of moving the mouse,
forces clicking=True, runs the click loop for a short duration, then stops.
"""

import threading
import time

import main

# Shorten interval for demo
main.CLICK_INTERVAL = 0.05


# Monkeypatch the click function to print instead of moving the real mouse.
def fake_click(*args, **kwargs):
    print(f"[SIMULADO] CLIC args={args} kwargs={kwargs}")


main.pyautogui.click = fake_click

print("Iniciando autoclicker simulado durante 2 segundos...")
main.clicking = True
main.running = True

# Start the click loop in a thread
t = threading.Thread(target=main.click_loop, daemon=True)
t.start()

# Let it run briefly
time.sleep(2)

# Stop the loop and wait for thread to finish
main.running = False
t.join(timeout=1)
print("Simulación finalizada.")
