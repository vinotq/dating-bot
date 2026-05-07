import os
import psycopg


def connect():
    return psycopg.connect(
        host=os.environ.get("PG_HOST", "postgres"),
        port=int(os.environ.get("PG_PORT", 5432)),
        user=os.environ.get("PG_USER", "app"),
        password=os.environ.get("PG_PASSWORD", "app"),
        dbname=os.environ.get("PG_DB", "app"),
        autocommit=True,
    )


class Log:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def head(self, title):
        bar = "=" * 70
        self.line(bar)
        self.line(title)
        self.line(bar)

    def line(self, s):
        print(s)
        self.f.write(s + "\n")
        self.f.flush()

    def close(self):
        self.f.close()


def run(conn, who, sql, lg, fetch=False):
    lg.line(f"[{who}] {sql}")
    try:
        cur = conn.execute(sql)
    except Exception as e:
        lg.line(f"[{who}] !! {type(e).__name__}: {e}")
        raise
    if fetch:
        rows = cur.fetchall()
        lg.line(f"[{who}] -> {rows}")
        return rows
    return None
