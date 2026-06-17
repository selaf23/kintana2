#!/usr/bin/env python3
"""
Autoclicker que encuentra imágenes objetivo en `targets/` y hace clic en ellas.

Controles:
 - F6 : alternar inicio/detención del escaneo y clics
 - Esc : salir del programa

Comportamiento:
 - Escanea todas las imágenes en la carpeta `targets/` y hace clic en las coincidencias.
 - Usa OpenCV (si está instalado) para matching por `confidence`.
 - Las opciones por objetivo pueden definirse en `targets/config.json`.

Precaución:
 - Este programa controla el ratón REAL. Úsalo con precaución y concede permisos
   de accesibilidad/input-monitoring en macOS si vas a ejecutar clics reales.
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

# OpenCV opcional
try:
    import cv2  # noqa: F401

    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False

# Valores por defecto
DEFAULT_TARGETS_DIR = "targets"
DEFAULT_SCAN_INTERVAL = 0.5
DEFAULT_CLICK_DELAY = 0.05
DEFAULT_CONFIDENCE = 0.85
DEFAULT_JITTER = 3
DEFAULT_CLICK_COOLDOWN = 1.0
DEFAULT_BUTTON = "left"

# Flags globales
clicking = False
running = True

# Registro de últimos clics para evitar clics repetidos rápidos
last_click_times: Dict[tuple, float] = {}

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
                f"[AVISO] config.json tiene formato inesperado (se esperaba un objeto); se ignorará"
            )
            return {}
    except Exception as e:
        print(f"[AVISO] Error al leer config.json: {e}")
        return {}


def locate_all(img_path: str, confidence: float) -> List[pyautogui.Box]:
    try:
        if HAVE_CV2:
            return list(pyautogui.locateAllOnScreen(img_path, confidence=confidence))
        return list(pyautogui.locateAllOnScreen(img_path))
    except Exception as e:
        print(f"[AVISO] locate_all falló para {img_path}: {e}")
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


def get_target_setting(img_path: str, cfg: Dict[str, Any], key: str, default: Any):
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
    global last_click_times

    now = time.time()

    for img in target_images:
        confidence = get_target_setting(img, cfg, "confidence", global_confidence)
        matches = locate_all(img, confidence)
        if not matches:
            continue

        for m in matches:
            cx, cy = center_of(m)
            basename = os.path.basename(img)
            key = (basename, cx, cy)

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
                continue

            jx = random.randint(-int(jitter), int(jitter)) if jitter else 0
            jy = random.randint(-int(jitter), int(jitter)) if jitter else 0
            tx, ty = cx + jx, cy + jy

            try:
                pyautogui.click(tx, ty, button=button)
                last_click_times[key] = time.time()
                print(
                    f"[CLIC] {basename} en ({tx},{ty}) (cooldown={click_cooldown}s, confianza={confidence})"
                )
            except Exception as e:
                print(f"[ERROR] No se pudo clicar {basename} en ({tx},{ty}): {e}")

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
    global running, clicking

    while running:
        if clicking:
            cfg = load_targets_config(targets_dir)
            target_images = list_target_images(targets_dir)
            if not target_images:
                print(
                    f"[AVISO] No se encontraron imágenes objetivo en {targets_dir}. Añade archivos PNG/JPG allí."
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
            time.sleep(0.1)


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


def main():
    parser = argparse.ArgumentParser(
        description="Autoclicker por imágenes — coloca imágenes objetivo en una carpeta `targets/` junto al ejecutable."
    )
    parser.add_argument(
        "-t",
        "--targets",
        help="Ruta a la carpeta targets (por defecto: targets junto al ejecutable)",
    )
    parser.add_argument(
        "-C",
        "--confidence",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help="Confiabilidad de matching (solo con OpenCV). Por defecto: %(default)s",
    )
    parser.add_argument(
        "--scan-interval",
        type=float,
        default=DEFAULT_SCAN_INTERVAL,
        help="Segundos entre escaneos de pantalla. Por defecto: %(default)s",
    )
    parser.add_argument(
        "--click-delay",
        type=float,
        default=DEFAULT_CLICK_DELAY,
        help="Retardo (s) entre clics cuando se encuentran múltiples coincidencias. Por defecto: %(default)s",
    )
    parser.add_argument(
        "--jitter",
        type=int,
        default=DEFAULT_JITTER,
        help="Jitter aleatorio en píxeles aplicado a los clics. Por defecto: %(default)s",
    )
    parser.add_argument(
        "--click-cooldown",
        type=float,
        default=DEFAULT_CLICK_COOLDOWN,
        help="Cooldown por defecto (s) antes de reclicar la misma posición (puede ser anulado por objetivo). Por defecto: %(default)s",
    )
    parser.add_argument(
        "--button",
        choices=("left", "right", "middle"),
        default=DEFAULT_BUTTON,
        help="Botón del ratón a usar para los clics",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Iniciar automáticamente (peligroso). Por defecto debes presionar F6 para iniciar.",
    )

    args = parser.parse_args()

    targets_dir = resolve_targets_dir(args.targets)

    print("=" * 60)
    print("Autoclicker por imágenes")
    print(f"Carpeta de objetivos: {targets_dir}")
    if HAVE_CV2:
        print(f"OpenCV disponible — usando confianza={args.confidence}")
    else:
        print(
            "OpenCV no encontrado — se realizarán búsquedas exactas (instala opencv-python para mejores resultados)"
        )
    print("Controles: presiona F6 para iniciar/detener los clics, Esc para salir")
    print("=" * 60)

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

    global clicking
    clicking = bool(args.auto_start)

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    print("Esperando a que termine el hilo de fondo...")
    t.join(timeout=1)
    print("Adiós")


if __name__ == "__main__":
    main()
