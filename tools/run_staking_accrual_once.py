import json
    finally:
        # Release advisory lock safely (and clean broken transaction if needed)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            c.execute(text("SELECT pg_advisory_unlock(912345678)"))
        except Exception:
            try:
                with engine.connect() as c2:
                    c2.execute(text("SELECT pg_advisory_unlock(912345678)"))
            except Exception:
                pass

if __name__ == "__main__":
    main()