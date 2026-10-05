"""
CUANIMUS Zero-Dependency Environment Variable Loader (.env).
Loads key-value pairs from .env into os.environ without requiring external packages.
Preserves existing shell environment variables, handles comments, and unquotes values.
"""
import os
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def load_env_file(dotenv_path: Optional[str] = None, override: bool = False) -> Dict[str, str]:
    """
    Parses .env file and injects variables into os.environ.
    Defaults to the project root .env file.
    """
    if dotenv_path is None:
        dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

    loaded: Dict[str, str] = {}
    if not os.path.exists(dotenv_path):
        return loaded

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip enclosing quotes if present
                    if len(val) >= 2 and ((val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'"))):
                        val = val[1:-1]
                    loaded[key] = val
                    if override or key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        logger.warning(f"Could not load .env file from {dotenv_path}: {e}")

    return loaded
