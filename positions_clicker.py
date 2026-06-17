#!/usr/bin/env python3
"""
Herramienta simple para registrar posiciones de pantalla y hacer clics en ellas.

Flujo:
 1) Registrar posiciones moviendo el ratón al punto y pulsando Enter.
 2) Guardar las posiciones en `targets/positions.json` (opcional).
 3) Ejecutar el bucle de clics: F6 para iniciar/detener, Esc para salir.

Opciones de seguridad:
 - Por defecto se ejecuta en modo simulado (no hace clics reales).
 - Pasa --real para permitir clics reales (haz una cuenta regresiva antes de empezar).

Uso rápido:
  python positions_clicker.py        # interactivo
  python positions_clicker.py --real # clicks reales (con confirmación)
"""

import argparse
import json
import os
import threading
import time

import pyautogui
from pynput import keyboard

TARGETS_DIR = os.path.join(os.path.dirname(__file__), "targets")
POSITIONS_FILE = os.path.join(TARGETS_DIR, "positions.json")

pyautogui.FAILSAFE = True

clicking = False
running = True
last_click_times = {}


def ensure_targets_dir():
    os.makedirs(TARGETS_DIR, exist_ok=True)


def load_positions():
    if not os.path.exists(POSITIONS_FILE):
        return {}
    try:
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_positions(positions: dict):
    ensure_targets_dir()
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, indent=2, ensure_ascii=False)


def record_positions_interactive():
    print("Registrar posiciones. Mueve el ratón a la posición deseada y pulsa Enter.")
    print("Escribe 'done' y pulsa Enter cuando hayas terminado.")
    positions = {}
    idx = 1
    while True:
        s = input(
            f"Registrar posición #{idx} (Enter para capturar / 'done' para terminar): "
        ).strip()
        if s.lower() == "done":
            break
        pos = pyautogui.position()
        name = input(
            f"Nombre para la posición #{idx} (por defecto pos_{idx}): "
        ).strip()
        if not name:
            name = f"pos_{idx}"
        positions[name] = {
            "x": pos.x,
            "y": pos.y,
            "click_cooldown": 1.0,
            "jitter": 0,
            "button": "left",
            "enabled": True,
        }
        print(f"Registrada {name} -> ({pos.x},{pos.y})")
        idx += 1
    return positions


def on_press(key):
    global clicking, running
    try:
        if key == keyboard.Key.f6:
            clicking = not clicking
            state = "INICIADO" if clicking else "DETENIDO"
            print(f"[Autoclicker] {state}")
        elif key == keyboard.Key.esc:
            print("[Autoclicker] Saliendo...")
            running = False
            return False
    except Exception:
        pass


def click_loop(positions_list, global_interval, simulate):
    global running, clicking, last_click_times
    print("Hilo de clics iniciado. Presiona F6 para comenzar/parar, Esc para salir.")
    while running:
        if clicking:
            now = time.time()
            for name, info in positions_list.items():
                if not info.get("enabled", True):
                    continue
                x = int(info.get("x", 0))
                y = int(info.get("y", 0))
                cooldown = float(info.get("click_cooldown", global_interval))
                jitter = int(info.get("jitter", 0))
                button = info.get("button", "left")
                last = last_click_times.get((name, x, y), 0)
                if now - last < cooldown:
                    continue
                jx = 0
                jy = 0
                if jitter:
                    jx = pyautogui.random.randint(-jitter, jitter)
                    jy = pyautogui.random.randint(-jitter, jitter)
                tx, ty = x + jx, y + jy
                if simulate:
                    print(
                        f"[SIMULADO] CLIC {name} en ({tx},{ty}) (cooldown={cooldown}s)"
                    )
                else:
                    try:
                        pyautogui.click(tx, ty, button=button)
                        print(f"[CLIC] {name} en ({tx},{ty}) (boton={button})")
                    except Exception as e:
                        print(f"[ERROR] No se pudo clicar {name} en ({tx},{ty}): {e}")
                last_click_times[(name, x, y)] = time.time()
                time.sleep(float(info.get("click_delay", 0.05)))
            # pausa entre pasadas
            time.sleep(global_interval)
        else:
            time.sleep(0.1)
    print("Hilo de clics detenido")


def main():
    parser = argparse.ArgumentParser(
        description="Registrar posiciones y clicarlas en secuencia"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Permite clics reales (por defecto simulado)",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Iniciar automáticamente el clic (riesgoso)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Intervalo por defecto entre pasadas (s)",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=3,
        help="Cuenta regresiva antes de iniciar (s) si --real)",
    )
    args = parser.parse_args()

    simulate = not args.real

    ensure_targets_dir()
    positions = {}
    if os.path.exists(POSITIONS_FILE):
        s = input("Se encontró positions.json. ¿Cargarla? [Y/n]: ").strip().lower()
        if s == "" or s == "y" or s == "s":
            positions = load_positions()
        else:
            positions = record_positions_interactive()
    else:
        positions = record_positions_interactive()

    if not positions:
        print("No se registraron posiciones. Saliendo.")
        return

    s = input("¿Guardar posiciones en targets/positions.json? [Y/n]: ").strip().lower()
    if s == "" or s == "y" or s == "s":
        save_positions(positions)
        print(f"Guardadas {len(positions)} posiciones en {POSITIONS_FILE}")

    print(f"Posiciones: {positions}")
    print(f"Modo: {'SIMULADO' if simulate else 'REAL'}")

    if not simulate:
        print(
            "ADVERTENCIA: se habilitarán clics reales. Asegúrate de que el cursor esté en una zona segura."
        )
        print(f"Iniciando en {args.countdown} segundos...")
        time.sleep(args.countdown)

    # Start background thread
    t = threading.Thread(
        target=click_loop, args=(positions, args.interval, simulate), daemon=True
    )
    t.start()

    # Keyboard listener (F6 to toggle, Esc to exit)
    with keyboard.Listener(on_press=on_press) as listener:
        if args.auto_start:
            global clicking
            clicking = True
            print("Autostart activado: comenzando a clicar")
        listener.join()

    # Clean shutdown
    running = False
    t.join(timeout=1)


if __name__ == "__main__":
    main()
