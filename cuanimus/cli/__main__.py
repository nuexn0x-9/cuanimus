"""
Executable module entrypoint: python -m cuanimus.cli
"""
import sys
from cuanimus.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
