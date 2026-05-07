from common import connect, Log, run


def demo():
    lg = Log("results/02_non_repeatable_read.log")
    lg.head("аномалия 2: non-repeatable read")

    a = connect()
    b = connect()

    base = a.execute("select duration_days from activity where id = 2").fetchone()[0]

    lg.line("--- read committed ---")
    run(a, "T1", "begin isolation level read committed", lg)
    run(a, "T1", "select duration_days from activity where id = 2", lg, fetch=True)

    run(b, "T2", "begin", lg)
    run(b, "T2", "update activity set duration_days = 77 where id = 2", lg)
    run(b, "T2", "commit", lg)

    run(a, "T1", "select duration_days from activity where id = 2", lg, fetch=True)
    run(a, "T1", "commit", lg)

    a.execute(f"update activity set duration_days = {base} where id = 2")

    lg.line("--- repeatable read ---")
    run(a, "T1", "begin isolation level repeatable read", lg)
    run(a, "T1", "select duration_days from activity where id = 2", lg, fetch=True)

    run(b, "T2", "update activity set duration_days = 123 where id = 2", lg)

    run(a, "T1", "select duration_days from activity where id = 2", lg, fetch=True)
    run(a, "T1", "commit", lg)

    a.execute(f"update activity set duration_days = {base} where id = 2")
    a.close()
    b.close()
    lg.close()


if __name__ == "__main__":
    demo()
