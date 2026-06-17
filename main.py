"""
Autoclicker simple
------------------
Hace clic repetidamente en una posición fija de la pantalla (por ejemplo una zona
de un juego en el navegador), con intervalo configurable.

CONFIGURACIÓN (ejecuta esto una vez en tu máquina):
    pip install pyautogui pynput

COMO FUNCIONA:
    1. Ejecuta el script.
    2. Te da unos segundos para posicionar el ratón en el punto donde quieres clicar
       (o puedes fijar coordenadas en FIXED_X, FIXED_Y).
    3. Presiona F6 para iniciar/parar. Presiona Esc para salir.

NOTAS:
    - Este script controla el cursor REAL. No muevas el ratón mientras está activo.
    - Algunos juegos detectan automatizaciones. Usa bajo tu responsabilidad.
"""

import threading
import time

import pyautogui
from pynput import keyboard

# ---------------- CONFIGURACIÓN ----------------
CLICK_INTERVAL = 0.1  # segundos entre clicks (0.1 = 10 clicks/seg)
USE_CURRENT_MOUSE_POS = True  # True = clicar donde esté el ratón al iniciar
FIXED_X, FIXED_Y = 500, 500  # usado solo si USE_CURRENT_MOUSE_POS = False
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
        state = "INICIADO" if clicking else "DETENIDO"
        print(f"[Autoclicker] {state}")
    elif key == keyboard.Key.esc:
        print("[Autoclicker] Saliendo...")
        running = False
        return False  # detiene el listener


def main():
    print("=" * 50)
    print("Autoclicker listo.")
    print("Presiona F6 para iniciar/parar los clics.")
    print("Presiona Esc para salir.")
    if USE_CURRENT_MOUSE_POS:
        print("Modo: clics en la posición actual del ratón.")
    else:
        print(f"Modo: clics en la posición fija ({FIXED_X}, {FIXED_Y})")
    print("=" * 50)

    t = threading.Thread(target=click_loop, daemon=True)
    t.start()

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
