import os, sys, glob

print("PY:", sys.version)

print("\n== Alembic import ==")
try:
    import alembic
    print("alembic:", alembic.__version__)
except Exception as e:
    print("alembic import ERROR:", repr(e))

print("\n== Filesystem ==")
print("cwd:", os.getcwd())
print("has alembic.ini:", os.path.exists("alembic.ini"))
print("has alembic dir:", os.path.isdir("alembic"))
print("has versions dir:", os.path.isdir("alembic/versions"))
files = sorted(glob.glob("alembic/versions/*.py"))
print("migration files:", len(files))
for f in files[-10:]:
    print(" -", f)

print("\n== alembic.ini quick check ==")
try:
    import configparser
    cp = configparser.ConfigParser()
    cp.read("alembic.ini")
    print("script_location:", cp.get("alembic", "script_location", fallback=None))
except Exception as e:
    print("alembic.ini read ERROR:", repr(e))

print("\n== Env vars ==")
dbu = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
print("DATABASE_URL present:", bool(dbu))

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