import json
import os
import threading
import time
import uuid
from pathlib import Path

import psutil
import requests
import redis as redis_lib

from producer import Producer, _connect_redis
from consumer import Consumer

RABBIT_HOST = os.environ.get("RABBIT_HOST", "localhost")
RABBIT_PORT = int(os.environ.get("RABBIT_PORT", 5672))
RABBIT_MGMT_URL = f"http://{RABBIT_HOST}:15672"
RABBIT_AUTH = ("guest", "guest")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

BROKERS = {
    "rabbitmq": (RABBIT_HOST, RABBIT_PORT),
    "redis": (REDIS_HOST, REDIS_PORT),
}

class StatsSampler:
    def __init__(self, broker: str, queue: str):
        self.broker = broker
        self.queue = queue
        self._stop = threading.Event()
        self.cpu_samples: list[float] = []
        self.mem_broker_mb: list[float] = []
        self.backlog_samples: list[int] = []
        self._proc = psutil.Process()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=3)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.cpu_samples.append(self._proc.cpu_percent(interval=None))
            except Exception:
                pass

            try:
                if self.broker == "rabbitmq":
                    resp = requests.get(
                        f"{RABBIT_MGMT_URL}/api/queues/%2F/{self.queue}",
                        auth=RABBIT_AUTH,
                        timeout=1,
                    )
                    if resp.ok:
                        data = resp.json()
                        self.backlog_samples.append(data.get("messages", 0))
                        mem = data.get("memory", 0)
                        self.mem_broker_mb.append(mem / 1024 / 1024)

                elif self.broker == "redis":
                    r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT)
                    info = r.info("memory")
                    self.mem_broker_mb.append(
                        info.get("used_memory", 0) / 1024 / 1024
                    )
                    self.backlog_samples.append(r.llen(self.queue))
            except Exception:
                pass

            time.sleep(0.2)

    def summary(self) -> dict:
        def _avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else 0

        def _max(lst):
            return round(max(lst), 2) if lst else 0

        return {
            "cpu_avg_pct": _avg(self.cpu_samples),
            "cpu_max_pct": _max(self.cpu_samples),
            "broker_mem_avg_mb": _avg(self.mem_broker_mb),
            "broker_mem_max_mb": _max(self.mem_broker_mb),
            "backlog_avg": _avg(self.backlog_samples),
            "backlog_max": _max(self.backlog_samples),
        }


def run_scenario(broker: str, total: int, size_bytes: int, rate: int) -> dict:
    host, port = BROKERS[broker]
    queue = f"bench_{uuid.uuid4().hex[:8]}"

    prod = Producer(broker, queue, host, port)
    cons = Consumer(broker, queue, host, port)
    sampler = StatsSampler(broker, queue)

    consumer_result = {}

    def _consume():
        consumer_result.update(cons.drain(expected=total, idle_timeout_s=10.0))

    t = threading.Thread(target=_consume, daemon=True)
    t.start()
    time.sleep(0.5)

    sampler.start()
    prod_result = prod.run(total_msgs=total, size_bytes=size_bytes, target_rate=rate)
    t.join(timeout=90)
    sampler.stop()

    return {
        "broker": broker,
        "total": total,
        "size_bytes": size_bytes,
        "target_rate": rate,
        **prod_result,
        **consumer_result,
        **sampler.summary(),
    }

SCENARIOS = [
    {"tag": "baseline",         "total": 20000, "size_bytes": 1024,         "rate": 5000},

    {"tag": "size_128B",        "total": 10000, "size_bytes": 128,          "rate": 2000},
    {"tag": "size_1KB",         "total": 10000, "size_bytes": 1024,         "rate": 2000},
    {"tag": "size_10KB",        "total": 10000, "size_bytes": 10 * 1024,    "rate": 2000},
    {"tag": "size_100KB",       "total": 10000, "size_bytes": 100 * 1024,   "rate": 2000},

    {"tag": "rate_1k",          "total": 20000, "size_bytes": 512,          "rate": 1000},
    {"tag": "rate_5k",          "total": 20000, "size_bytes": 512,          "rate": 5000},
    {"tag": "rate_10k",         "total": 20000, "size_bytes": 512,          "rate": 10000},
    {"tag": "rate_20k",         "total": 20000, "size_bytes": 512,          "rate": 20000},
]


def main():
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    all_results = []

    for sc in SCENARIOS:
        for broker in ("rabbitmq", "redis"):
            print(
                f"\n=== {sc['tag']} [{broker}] "
                f"total={sc['total']} size={sc['size_bytes']}B rate={sc['rate']}/s ===",
                flush=True,
            )
            try:
                r = run_scenario(broker, sc["total"], sc["size_bytes"], sc["rate"])
                r["tag"] = sc["tag"]
                print(json.dumps(r, ensure_ascii=False), flush=True)
                all_results.append(r)
            except Exception as e:
                err = {"tag": sc["tag"], "broker": broker, "error": str(e), **sc}
                print("ERROR:", err, flush=True)
                all_results.append(err)

    (out_dir / "results.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2)
    )

    cols = [
        ("tag",                 "сценарий"),
        ("broker",              "брокер"),
        ("sent",                "отправлено"),
        ("received",            "получено"),
        ("lost",                "потеряно"),
        ("actual_produce_rate", "произв., msg/s"),
        ("consume_rate",        "потребл., msg/s"),
        ("latency_avg_ms",      "avg, мс"),
        ("latency_p95_ms",      "p95, мс"),
        ("latency_max_ms",      "max, мс"),
        ("broker_mem_avg_mb",   "RAM брокера, МБ"),
        ("backlog_max",         "backlog max"),
    ]
    header = "| " + " | ".join(h for _, h in cols) + " |"
    sep    = "|" + "|".join("---" for _ in cols) + "|"
    rows = [header, sep]
    for r in all_results:
        if "error" in r:
            row = f"| {r['tag']} | {r['broker']} | **ОШИБКА подключения** |" + " |" * (len(cols) - 3)
        else:
            row = "| " + " | ".join(str(r.get(k, "")) for k, _ in cols) + " |"
        rows.append(row)

    (out_dir / "results.md").write_text("\n".join(rows) + "\n")
    print("\nГОТОВО. Результаты в results/results.md", flush=True)


if __name__ == "__main__":
    main()
