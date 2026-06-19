"""Entry point for `python launch.py` and for PyInstaller builds.

Pass --settings to open the settings window instead of the app.
"""

import sys

if "--settings" in sys.argv:
    from wisprlite.settings import main
else:
    from wisprlite.app import main

if __name__ == "__main__":
    main()
