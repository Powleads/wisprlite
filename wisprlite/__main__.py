import sys

if "--settings" in sys.argv:
    from .settings import main
else:
    from .app import main

if __name__ == "__main__":
    main()
