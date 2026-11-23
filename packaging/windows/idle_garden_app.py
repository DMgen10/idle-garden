"""Entry point PyInstaller freezes into IdleGarden.exe."""

import sys

from idle_garden.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
