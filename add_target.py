#!/usr/bin/env python3
"""
Helper to add target images into `targets/` and optionally set per-target options
in `targets/config.json`.

Usage:
  python3 add_target.py PATH_TO_IMAGE --click-interval 2 --confidence 0.9 --button left

This will copy the image into `targets/` retaining the filename and add/update an
entry in `targets/config.json` with the provided options. If you want a different
filename in targets, pass `--name newname.png`.
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
        print(f"[WARN] Failed to read existing config.json: {e}")
        return {}


def save_config(targets_dir: str, cfg: dict) -> None:
    cfg_path = os.path.join(targets_dir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Add an image to targets/ and set per-target options."
    )
    parser.add_argument("image", help="Path to the image to add")
    parser.add_argument(
        "--name", help="Filename to use inside targets/ (defaults to source basename)"
    )
    parser.add_argument(
        "--click-interval",
        type=float,
        help="Minimum seconds between clicks on this target",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        help="Matching confidence for this target (0-1). Requires opencv-python)",
    )
    parser.add_argument(
        "--jitter", type=int, help="Pixel jitter for clicks on this target"
    )
    parser.add_argument(
        "--button", choices=("left", "right", "middle"), help="Mouse button to use"
    )
    parser.add_argument(
        "--enabled", choices=("true", "false"), help="Whether this target is enabled"
    )

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    targets_dir = ensure_targets_dir(base_dir)

    if not os.path.exists(args.image):
        print(f"Error: image not found: {args.image}")
        sys.exit(1)

    dest_name = args.name if args.name else os.path.basename(args.image)
    dest_path = os.path.join(targets_dir, dest_name)

    # Prevent overwriting unless user explicitly overwrites
    if os.path.exists(dest_path):
        print(
            f"Warning: {dest_name} already exists in targets/ and will be overwritten"
        )

    try:
        shutil.copy2(args.image, dest_path)
        print(f"Copied {args.image} -> {dest_path}")
    except Exception as e:
        print(f"Failed to copy image: {e}")
        sys.exit(1)

    cfg = load_config(targets_dir)
    entry = cfg.get(dest_name, {})

    # Apply provided options
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

    # Save the entry only if we have options; otherwise ensure there's at least an empty entry
    if entry:
        cfg[dest_name] = entry
        save_config(targets_dir, cfg)
        print(f"Updated config.json for {dest_name}: {entry}")
    else:
        # No options provided; ensure target exists in index (optional)
        if dest_name not in cfg:
            cfg[dest_name] = {}
            save_config(targets_dir, cfg)
            print(f"Added empty config entry for {dest_name}")

    print("Done.")


if __name__ == "__main__":
    main()
