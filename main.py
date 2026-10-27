"""Entry point: `uv run main.py` launches Nemesis Protocol."""
import runpy
import sys
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parent / "game"


def main():
    sys.path.insert(0, str(GAME_DIR))   # game modules import each other as top-level
    runpy.run_path(str(GAME_DIR / "game.py"), run_name="__main__")


if __name__ == "__main__":
    main()
