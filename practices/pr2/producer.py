import time
import struct

import pika
import redis


def _connect_rabbit(host: str, port: int, timeout_s: float = 30.0):
    deadline = time.perf_counter() + timeout_s
    last_err = None
    while time.perf_counter() < deadline:
        try:
            return pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=host,
                    port=port,
                    heartbeat=30,
                    socket_timeout=5,
                    blocked_connection_timeout=10,
                )
            )
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise RuntimeError(f"cannot connect to rabbitmq {host}:{port}: {last_err}")


def _connect_redis(host: str, port: int, timeout_s: float = 30.0):
    deadline = time.perf_counter() + timeout_s
    last_err = None
    while time.perf_counter() < deadline:
        try:
            r = redis.Redis(host=host, port=port, socket_timeout=5)
            r.ping()
            return r
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    raise RuntimeError(f"cannot connect to redis {host}:{port}: {last_err}")


def _payload(size_bytes: int, seq: int, ts_ns: int) -> bytes:
    header = struct.pack(">QQ", seq, ts_ns)
    filler = size_bytes - len(header)
    if filler < 0:
        return header[:size_bytes]
    return header + (b"x" * filler)


class Producer:
    def __init__(self, broker: str, queue: str, host: str, port: int):
        self.broker = broker
        self.queue = queue
        self.host = host
        self.port = port

    def run(self, total_msgs: int, size_bytes: int, target_rate: int) -> dict:
        sent = 0
        errors = 0
        start = time.perf_counter()
        interval = 1.0 / target_rate if target_rate > 0 else 0

        if self.broker == "rabbitmq":
            conn = _connect_rabbit(self.host, self.port)
            ch = conn.channel()
            ch.queue_declare(queue=self.queue, durable=False)
            next_deadline = time.perf_counter()
            for i in range(total_msgs):
                try:
                    body = _payload(size_bytes, i, time.time_ns())
                    ch.basic_publish(exchange="", routing_key=self.queue, body=body)
                    sent += 1
                except Exception:
                    errors += 1
                next_deadline += interval
                sleep_for = next_deadline - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
            conn.close()

        elif self.broker == "redis":
            r = _connect_redis(self.host, self.port)
            next_deadline = time.perf_counter()
            for i in range(total_msgs):
                try:
                    body = _payload(size_bytes, i, time.time_ns())
                    r.rpush(self.queue, body)
                    sent += 1
                except Exception:
                    errors += 1
                next_deadline += interval
                sleep_for = next_deadline - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
        else:
            raise ValueError(f"unknown broker: {self.broker}")

        elapsed = time.perf_counter() - start
        return {
            "sent": sent,
            "errors_produce": errors,
            "produce_elapsed_s": round(elapsed, 3),
            "actual_produce_rate": round(sent / elapsed, 2) if elapsed > 0 else 0,
        }
