#!/usr/bin/env python3
"""Print absolute path of bundled Songmeng image asset."""

from pathlib import Path


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    image_path = skill_root / "assets" / "songmeng_small.jpg"
    print(str(image_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
