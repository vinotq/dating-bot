from common import connect, Log, run


def demo():
    lg = Log("results/03_phantom_read.log")
    lg.head("аномалия 3: phantom read")

    a = connect()
    b = connect()

    a.execute("delete from activity where name = 'фантомная активность'")

    insert_sql = (
        "insert into activity (alchemist_id, manuscript_id, name, goal, result, duration_days) "
        "values (1, 1, 'фантомная активность', 'появиться без спросу', 'появилась', 1)"
    )

    lg.line("--- read committed ---")
    run(a, "T1", "begin isolation level read committed", lg)
    run(a, "T1", "select count(*) from activity where alchemist_id = 1", lg, fetch=True)

    run(b, "T2", insert_sql, lg)

    run(a, "T1", "select count(*) from activity where alchemist_id = 1", lg, fetch=True)
    run(a, "T1", "commit", lg)

    a.execute("delete from activity where name = 'фантомная активность'")

    lg.line("--- repeatable read ---")
    run(a, "T1", "begin isolation level repeatable read", lg)
    run(a, "T1", "select count(*) from activity where alchemist_id = 1", lg, fetch=True)

    run(b, "T2", insert_sql, lg)

    run(a, "T1", "select count(*) from activity where alchemist_id = 1", lg, fetch=True)
    run(a, "T1", "commit", lg)

    a.execute("delete from activity where name = 'фантомная активность'")
    a.close()
    b.close()
    lg.close()


if __name__ == "__main__":
    demo()
