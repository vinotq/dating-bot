import threading
import time

from common import connect, Log, run


def demo():
    lg = Log("results/04_lost_update.log")
    lg.head("аномалия 4: lost update")

    base = connect().execute("select death_year from alchemist where id = 1").fetchone()[0]

    lg.line("--- read committed без блокировок ---")
    a = connect()
    b = connect()

    run(a, "T1", "begin isolation level read committed", lg)
    run(b, "T2", "begin isolation level read committed", lg)

    v1 = run(a, "T1", "select death_year from alchemist where id = 1", lg, fetch=True)[0][0]
    v2 = run(b, "T2", "select death_year from alchemist where id = 1", lg, fetch=True)[0][0]

    run(a, "T1", f"update alchemist set death_year = {v1 + 5} where id = 1", lg)

    def t2_update():
        run(b, "T2", f"update alchemist set death_year = {v2 + 7} where id = 1", lg)

    th = threading.Thread(target=t2_update)
    th.start()
    time.sleep(0.5)

    run(a, "T1", "commit", lg)
    th.join()
    run(b, "T2", "commit", lg)

    final = a.execute("select death_year from alchemist where id = 1").fetchone()[0]
    lg.line(f"[--] death_year = {final}")

    a.execute(f"update alchemist set death_year = {base} where id = 1")
    a.close()
    b.close()

    lg.line("--- select for update ---")
    a = connect()
    b = connect()

    run(a, "T1", "begin", lg)
    run(b, "T2", "begin", lg)

    v1 = run(a, "T1", "select death_year from alchemist where id = 1 for update", lg, fetch=True)[0][0]

    holder = {}

    def t2_locking_select():
        rows = run(b, "T2", "select death_year from alchemist where id = 1 for update", lg, fetch=True)
        holder["v"] = rows[0][0]
        run(b, "T2", f"update alchemist set death_year = {holder['v'] + 7} where id = 1", lg)
        run(b, "T2", "commit", lg)

    th = threading.Thread(target=t2_locking_select)
    th.start()
    time.sleep(0.5)

    run(a, "T1", f"update alchemist set death_year = {v1 + 5} where id = 1", lg)
    run(a, "T1", "commit", lg)
    th.join()

    final = a.execute("select death_year from alchemist where id = 1").fetchone()[0]
    lg.line(f"[--] death_year = {final}")

    a.execute(f"update alchemist set death_year = {base} where id = 1")
    a.close()
    b.close()
    lg.close()


if __name__ == "__main__":
    demo()
