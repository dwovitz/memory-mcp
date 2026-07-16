"""Run the non-mutating AI index contract check."""

from ai_index import main


if __name__ == "__main__":
    import sys

    sys.argv.insert(1, "check")
    main()
