from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Make repo root importable so "import app" works (or any top-level package)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("PY:", sys.version.replace("\n"," "))
print("CWD:", os.getcwd())
print("ROOT:", ROOT)
print("sys.path[0:5]:", sys.path[0:5])

# Try common package names (app is expected, but we probe gracefully)
Base = None
base_src = None

try:
    from app.database import Base  # type: ignore
    base_src = "app.database:Base"
except Exception as e:
    print("note: cannot import app.database.Base:", type(e).__name__, e)

if Base is None:
    # Try other common layouts if you renamed the package
    candidates = [
        ("src.app.database", "src.app.database:Base"),
        ("bot_factory.app.database", "bot_factory.app.database:Base"),
    ]
    for mod, label in candidates:
        try:
            m = __import__(mod, fromlist=["Base"])
            Base = getattr(m, "Base")
            base_src = label
            break
        except Exception as e:
            print(f"note: cannot import {label}:", type(e).__name__, e)

if Base is None:
    print("FATAL: Could not import Base. List repo tree hints below:")
    for p in sorted([p for p in ROOT.iterdir() if p.is_dir()]):
        print(" - dir:", p.name)
    sys.exit(2)

print("Base imported from:", base_src)

# Import model modules (best effort); adjust list later based on your project
mods = [
    "app.models",
    "app.models_investments",
    "app.models_referrals",
    "app.models_telegram",
]
loaded = []
for m in mods:
    try:
        __import__(m)
        loaded.append(m)
    except Exception as e:
        print(f"note: could not import {m}: {type(e).__name__}: {e}")

print("loaded modules:", loaded)

tables = sorted(list(Base.metadata.tables.keys()))
print("metadata tables count:", len(tables))
for t in tables:
    print(" -", t)