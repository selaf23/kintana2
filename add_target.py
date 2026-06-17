#!/usr/bin/env python3
"""
Helper para añadir imágenes objetivo a `targets/` y opcionalmente establecer
opciones por objetivo en `targets/config.json`.

Uso:
  python3 add_target.py RUTA_IMAGEN --click-interval 2 --confidence 0.9 --button left

Esto copiará la imagen a `targets/` manteniendo el nombre de archivo y añadirá/actualizará
una entrada en `targets/config.json` con las opciones proporcionadas. Si deseas un nombre
diferente en targets, usa `--name nuevo_nombre.png`.
"""

import argparse
import json
import os
import shutil
import sys


def ensure_targets_dir(base_dir: str) -> str:
    targets_dir = os.path.join(base_dir, "targets")
    os.makedirs(targets_dir, exist_ok=True)
    return targets_dir


def load_config(targets_dir: str) -> dict:
    cfg_path = os.path.join(targets_dir, "config.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[AVISO] No se pudo leer config.json existente: {e}")
        return {}


def save_config(targets_dir: str, cfg: dict) -> None:
    cfg_path = os.path.join(targets_dir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Añadir una imagen a targets/ y establecer opciones por objetivo."
    )
    parser.add_argument("image", help="Ruta a la imagen a añadir")
    parser.add_argument(
        "--name",
        help="Nombre de archivo a usar dentro de targets/ (por defecto: basename)",
    )
    parser.add_argument(
        "--click-interval",
        type=float,
        help="Segundos mínimos entre clicks para este objetivo",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        help="Confianza de matching para este objetivo (0-1). Requiere opencv-python)",
    )
    parser.add_argument(
        "--jitter", type=int, help="Jitter en píxeles para los clics en este objetivo"
    )
    parser.add_argument(
        "--button", choices=("left", "right", "middle"), help="Botón del ratón a usar"
    )
    parser.add_argument(
        "--enabled", choices=("true", "false"), help="Si el objetivo está habilitado"
    )

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    targets_dir = ensure_targets_dir(base_dir)

    if not os.path.exists(args.image):
        print(f"Error: imagen no encontrada: {args.image}")
        sys.exit(1)

    dest_name = args.name if args.name else os.path.basename(args.image)
    dest_path = os.path.join(targets_dir, dest_name)

    if os.path.exists(dest_path):
        print(f"Aviso: {dest_name} ya existe en targets/ y será sobrescrito")

    try:
        shutil.copy2(args.image, dest_path)
        print(f"Copiado {args.image} -> {dest_path}")
    except Exception as e:
        print(f"Error al copiar la imagen: {e}")
        sys.exit(1)

    cfg = load_config(targets_dir)
    entry = cfg.get(dest_name, {})

    if args.click_interval is not None:
        entry["click_cooldown"] = float(args.click_interval)
    if args.confidence is not None:
        entry["confidence"] = float(args.confidence)
    if args.jitter is not None:
        entry["jitter"] = int(args.jitter)
    if args.button is not None:
        entry["button"] = args.button
    if args.enabled is not None:
        entry["enabled"] = True if args.enabled == "true" else False

    if entry:
        cfg[dest_name] = entry
        save_config(targets_dir, cfg)
        print(f"Actualizado config.json para {dest_name}: {entry}")
    else:
        if dest_name not in cfg:
            cfg[dest_name] = {}
            save_config(targets_dir, cfg)
            print(f"Añadida entrada vacía en config para {dest_name}")

    print("Listo.")


if __name__ == "__main__":
    main()
