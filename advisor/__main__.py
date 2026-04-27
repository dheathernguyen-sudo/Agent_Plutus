# advisor/__main__.py
"""Entry point for `python -m advisor`."""
import sys
from . import run_cli

if __name__ == "__main__":
    sys.exit(run_cli())
