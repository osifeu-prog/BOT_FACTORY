import os, sys, glob

print("PY:", sys.version)
print("CWD:", os.getcwd())
print("ENV PYTHONPATH:", os.getenv("PYTHONPATH"))
print("sys.path[0:5]:", sys.path[:5])

print("\n== Import check (app) ==")
try:
    import app
    print("import app: OK ->", getattr(app, "__file__", "(namespace package)"))
except Exception as e:
    print("import app: ERROR ->", repr(e))

print("\n== Alembic import ==")
try:
    import alembic
    print("alembic:", alembic.__version__)
except Exception as e:
    print("alembic import ERROR:", repr(e))

print("\n== Filesystem ==")
print("has alembic.ini:", os.path.exists("alembic.ini"))
print("has alembic dir:", os.path.isdir("alembic"))
print("has versions dir:", os.path.isdir("alembic/versions"))
files = glob.glob("alembic/versions/*.py")
print("migration files:", len(files))
for f in sorted(files)[-10:]:
    print(" -", f)

print("\n== alembic.ini script_location (RAW, no interpolation) ==")
try:
    import configparser
    cp = configparser.RawConfigParser()  # <— disables %(here)s interpolation entirely
    cp.read("alembic.ini")
    print("script_location:", cp.get("alembic", "script_location", fallback=None))
except Exception as e:
    print("alembic.ini read ERROR:", repr(e))

print("\n== SQLAlchemy inspect ==")
try:
    import sqlalchemy as sa
    from app.database import engine
    insp = sa.inspect(engine)
    tables = sorted(insp.get_table_names())
    print("tables:", tables)
    try:
        with engine.connect() as c:
            rows = c.execute(sa.text("select version_num from alembic_version")).fetchall()
        print("alembic_version rows:", rows)
    except Exception as e:
        print("alembic_version query ERROR:", repr(e))
except Exception as e:
    print("DB inspect ERROR:", repr(e))