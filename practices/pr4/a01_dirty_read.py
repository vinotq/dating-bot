from common import connect_mysql, run_mysql, Log


def demo():
    lg = Log("results/01_dirty_read.log")
    lg.head("аномалия 1: dirty read (mysql)")

    a = connect_mysql()
    b = connect_mysql()

    run_mysql(a, "T1", "set session transaction isolation level read uncommitted", lg)
    run_mysql(a, "T1", "start transaction", lg)

    run_mysql(b, "T2", "start transaction", lg)
    run_mysql(b, "T2", "update activity set duration_days = 999 where id = 1", lg)

    run_mysql(a, "T1", "select duration_days from activity where id = 1", lg, fetch=True)

    run_mysql(b, "T2", "rollback", lg)

    run_mysql(a, "T1", "select duration_days from activity where id = 1", lg, fetch=True)
    run_mysql(a, "T1", "commit", lg)

    a.close()
    b.close()
    lg.close()


if __name__ == "__main__":
    demo()
