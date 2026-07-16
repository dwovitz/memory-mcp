"""Refresh only automation-owned AI index data."""

from ai_index import main


if __name__ == "__main__":
    import sys

    sys.argv.insert(1, "refresh")
    main()
