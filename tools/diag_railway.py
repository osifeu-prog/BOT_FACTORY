import os, sys, glob

# ensure imports work even when executed from /app/tools etc.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")
print("PY:", sys.version)
print("CWD:", os.getcwd())
print("sys.path[0:3]:", sys.path[0:3])

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

print("\n== alembic.ini raw script_location line ==")
try:
    with open("alembic.ini","r",encoding="utf-8") as fh:
        for line in fh:
            if line.strip().startswith("script_location"):
                print(line.strip())
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