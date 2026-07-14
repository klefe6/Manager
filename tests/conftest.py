import sys
from pathlib import Path

# Manager is a flat repo (service_config.py sits at the root), so make the repo
# root importable without requiring an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
