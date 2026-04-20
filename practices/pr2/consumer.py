import struct
import time

import pika
import redis

from producer import _connect_rabbit, _connect_redis


class Consumer:
    def __init__(self, broker: str, queue: str, host: str, port: int):
        self.broker = broker
        self.queue = queue
        self.host = host
        self.port = port

    def drain(self, expected: int, idle_timeout_s: float = 5.0) -> dict:
        received = 0
        latencies_ns = []
        start = time.perf_counter()
        last_msg_ts = time.perf_counter()

        if self.broker == "rabbitmq":
            conn = _connect_rabbit(self.host, self.port)
            ch = conn.channel()
            ch.queue_declare(queue=self.queue, durable=False)
            while received < expected:
                method, _props, body = ch.basic_get(queue=self.queue, auto_ack=True)
                if method is None:
                    if time.perf_counter() - last_msg_ts > idle_timeout_s:
                        break
                    time.sleep(0.001)
                    continue
                _seq, ts_ns = struct.unpack(">QQ", body[:16])
                latencies_ns.append(time.time_ns() - ts_ns)
                received += 1
                last_msg_ts = time.perf_counter()
            conn.close()

        elif self.broker == "redis":
            r = _connect_redis(self.host, self.port)
            while received < expected:
                item = r.blpop(self.queue, timeout=1)
                if item is None:
                    if time.perf_counter() - last_msg_ts > idle_timeout_s:
                        break
                    continue
                _k, body = item
                _seq, ts_ns = struct.unpack(">QQ", body[:16])
                latencies_ns.append(time.time_ns() - ts_ns)
                received += 1
                last_msg_ts = time.perf_counter()
        else:
            raise ValueError(f"unknown broker: {self.broker}")

        elapsed = time.perf_counter() - start
        lost = max(0, expected - received)
        lat_ms = [x / 1_000_000 for x in latencies_ns]
        lat_ms.sort()
        n = len(lat_ms)
        avg = sum(lat_ms) / n if n else 0
        p95 = lat_ms[int(0.95 * (n - 1))] if n else 0
        mx = lat_ms[-1] if n else 0

        return {
            "received": received,
            "lost": lost,
            "consume_elapsed_s": round(elapsed, 3),
            "consume_rate": round(received / elapsed, 2) if elapsed > 0 else 0,
            "latency_avg_ms": round(avg, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_max_ms": round(mx, 2),
        }
