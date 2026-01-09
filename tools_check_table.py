import os
import psycopg2

dsn = os.environ["DATABASE_URL"]
pw  = os.environ["PGPASSWORD"]

conn = psycopg2.connect(dsn, password=pw)
cur = conn.cursor()
cur.execute("SELECT to_regclass('public.telegram_updates');")
print("telegram_updates =", cur.fetchone()[0])
cur.close()
conn.close()
