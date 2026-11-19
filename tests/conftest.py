import os
import sys
from pathlib import Path

# Tests always run on an isolated SQLite file and JSON document store, never the real MySQL/MongoDB
os.environ["DB_BACKEND"] = "sqlite"
os.environ["NOSQL_BACKEND"] = "file"

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
