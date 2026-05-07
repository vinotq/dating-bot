from common import connect, Log, run


def demo():
    lg = Log("results/01_dirty_read.log")
    lg.head("аномалия 1: dirty read")

    a = connect()
    b = connect()

    run(a, "T1", "begin isolation level read uncommitted", lg)
    run(b, "T2", "begin isolation level read committed", lg)

    run(b, "T2", "update activity set duration_days = 999 where id = 1", lg)
    run(a, "T1", "select duration_days from activity where id = 1", lg, fetch=True)

    run(b, "T2", "rollback", lg)
    run(a, "T1", "select duration_days from activity where id = 1", lg, fetch=True)
    run(a, "T1", "commit", lg)

    a.close()
    b.close()
    lg.close()


if __name__ == "__main__":
    demo()
