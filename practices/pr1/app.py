import json
import logging
import os
import sys
import time

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@db:5432/store",
)

LOG_FILE = os.getenv("LOG_FILE", "/app/logs/run.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def wait_for_db(engine, retries=15, delay=2):
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            log.info("БД доступна")
            return
        except Exception as e:
            log.info(f"ожидание БД... попытка {attempt + 1}/{retries}: {e}")
            time.sleep(delay)
    raise RuntimeError("БД не доступна")


def dump_table(conn, title, query, params=None):
    rows = conn.execute(text(query), params or {}).mappings().all()
    log.info(f"  {title}:")
    for row in rows:
        log.info(f"    {dict(row)}")


def scenario_1_place_order(engine):
    log.info("Задание 1: размещение заказа")

    items_payload = json.dumps([
        {"product_id": 2, "quantity": 3},
        {"product_id": 3, "quantity": 1},
        {"product_id": 5, "quantity": 2},
    ])

    with engine.begin() as conn:
        order_id = conn.execute(
            text("select place_order(:customer_id, cast(:items as jsonb))"),
            {"customer_id": 2, "items": items_payload},
        ).scalar()
        log.info(f"создан заказ order_id={order_id}")

    with engine.connect() as conn:
        order = conn.execute(
            text(
                "select o.order_id, c.first_name, c.last_name, "
                "o.order_date, o.total_amount "
                "from orders o join customers c on c.customer_id = o.customer_id "
                "where o.order_id = :id"
            ),
            {"id": order_id},
        ).mappings().one()
        log.info(
            f"  заказ #{order['order_id']}: "
            f"{order['first_name']} {order['last_name']}, "
            f"дата {order['order_date']}, сумма {order['total_amount']}"
        )

        dump_table(
            conn,
            "позиции",
            "select p.product_name, oi.quantity, oi.subtotal "
            "from order_items oi join products p on p.product_id = oi.product_id "
            "where oi.order_id = :id",
            {"id": order_id},
        )


def scenario_2_update_email(engine):
    log.info("Задание 2: обновление email")

    with engine.connect() as conn:
        before = conn.execute(
            text("select first_name, last_name, email from customers where customer_id = 2"),
        ).mappings().one()
        log.info(f"  до: {dict(before)}")

    with engine.begin() as conn:
        conn.execute(
            text("select update_customer_email(:id, :email)"),
            {"id": 2, "email": "grisha.kirov@yandex.ru"},
        )

    with engine.connect() as conn:
        after = conn.execute(
            text("select first_name, last_name, email from customers where customer_id = 2"),
        ).mappings().one()
        log.info(f"  после: {dict(after)}")


def scenario_3_add_product(engine):
    log.info("Задание 3: добавление продукта")

    with engine.connect() as conn:
        count_before = conn.execute(text("select count(*) from products")).scalar()
        log.info(f"  товаров до: {count_before}")

    with engine.begin() as conn:
        product_id = conn.execute(
            text("select add_product(:name, :price)"),
            {"name": "webcam", "price": 4200.00},
        ).scalar()

    with engine.connect() as conn:
        product = conn.execute(
            text("select * from products where product_id = :id"),
            {"id": product_id},
        ).mappings().one()
        log.info(f"  добавлен: {dict(product)}")

        count_after = conn.execute(text("select count(*) from products")).scalar()
        log.info(f"  товаров после: {count_after}")


def main():
    engine = create_engine(DATABASE_URL)
    wait_for_db(engine)

    scenario_1_place_order(engine)
    scenario_2_update_email(engine)
    scenario_3_add_product(engine)

    log.info("выполнено")
    log.info(f"лог: {LOG_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("ошибка выполнения")
        sys.exit(1)
