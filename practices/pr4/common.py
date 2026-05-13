import os
import psycopg
import pymysql


def connect():
    return psycopg.connect(
        host=os.environ.get("PG_HOST", "postgres"),
        port=int(os.environ.get("PG_PORT", 5432)),
        user=os.environ.get("PG_USER", "app"),
        password=os.environ.get("PG_PASSWORD", "app"),
        dbname=os.environ.get("PG_DB", "app"),
        autocommit=True,
    )


def connect_mysql():
    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "mysql"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ.get("MYSQL_USER", "app"),
        password=os.environ.get("MYSQL_PASSWORD", "app"),
        database=os.environ.get("MYSQL_DB", "app"),
        charset="utf8mb4",
        autocommit=False,
    )
    return conn


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


def run_mysql(conn, who, sql, lg, fetch=False):
    lg.line(f"[{who}] {sql}")
    try:
        cur = conn.cursor()
        cur.execute(sql)
        if fetch:
            rows = cur.fetchall()
            lg.line(f"[{who}] -> {rows}")
            return rows
    except Exception as e:
        lg.line(f"[{who}] !! {type(e).__name__}: {e}")
        raise
    return None


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
