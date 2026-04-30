import json
import os
import time

import psycopg2

from app import strategies, postgresConfig
from load_generator import runWorkload


resultsDir = "/app/results"
os.makedirs(resultsDir, exist_ok=True)

workloads = [
    {"name": "read_heavy", "read_ratio": 0.80, "total_ops": 20000, "concurrency": 16, "key_space": 200},
    {"name": "balanced",   "read_ratio": 0.50, "total_ops": 20000, "concurrency": 16, "key_space": 200},
    {"name": "write_heavy","read_ratio": 0.20, "total_ops": 20000, "concurrency": 16, "key_space": 200},
]


def resetDb():
    for _ in range(60):
        try:
            connection = psycopg2.connect(**postgresConfig)
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("postgres not reachable")
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE profiles")
            cursor.execute(
                """
                INSERT INTO profiles (id, name, age, bio)
                SELECT g, 'user_' || g, 18 + (g % 50), 'bio of user ' || g
                FROM generate_series(1, 1000) g
                """
            )
    connection.close()


def runOne(strategyName, workload):
    print(f"\n=== {strategyName} | {workload['name']} ===", flush=True)
    resetDb()
    cls = strategies[strategyName]
    strategy = cls()
    strategy.flushCache()
    strategy.metrics.__init__()

    stats = runWorkload(
        strategy,
        totalOps=workload["total_ops"],
        readRatio=workload["read_ratio"],
        concurrency=workload["concurrency"],
        keySpace=workload["key_space"],
    )

    extraMetrics = {}
    if strategyName == "write_back":
        flushStart = time.perf_counter()
        pendingCount = strategy.dirtyCount()
        strategy.flushSync()
        flushTime = time.perf_counter() - flushStart
        extraMetrics = {"pending_before_flush": pendingCount, "final_flush_s": round(flushTime, 4)}

    metrics = strategy.metrics.snapshot()
    totalReads = metrics["cache_hits"] + metrics["cache_misses"]
    hitRate = round(metrics["cache_hits"] / totalReads, 4) if totalReads else 0.0

    result = {
        "strategy": strategyName,
        "workload": workload["name"],
        "params": {k: workload[k] for k in ["read_ratio", "total_ops", "concurrency", "key_space"]},
        **stats,
        **metrics,
        "cache_hit_rate": hitRate,
        **extraMetrics,
    }

    print(json.dumps(result, indent=2), flush=True)
    strategy.shutdown()
    return result


def writeBackAccumulation():
    print("\n=== write_back ACCUMULATION DEMO ===", flush=True)
    resetDb()
    cls = strategies["write_back"]
    strategy = cls(flushInterval=5.0, batchSize=500)
    strategy.flushCache()
    strategy.metrics.__init__()

    snapshots = []
    burstStart = time.perf_counter()
    burstSize = 5000
    for i in range(burstSize):
        strategy.set((i % 200) + 1, {"name": f"u{i}", "age": 20 + (i % 30), "bio": f"burst {i}"})
        if i in (0, 500, 1000, 2000, 3500, 4999):
            snapshots.append({
                "after_writes": i + 1,
                "elapsed_s": round(time.perf_counter() - burstStart, 4),
                "dirty_queue": strategy.dirtyCount(),
                "db_writes_so_far": strategy.metrics.db_writes,
            })
    burstDuration = time.perf_counter() - burstStart
    pendingCount = strategy.dirtyCount()
    drainStart = time.perf_counter()
    strategy.flushSync()
    drainDuration = time.perf_counter() - drainStart
    finalMetrics = strategy.metrics.snapshot()
    strategy.shutdown()

    result = {
        "burst_writes": burstSize,
        "burst_duration_s": round(burstDuration, 4),
        "burst_throughput_rps": round(burstSize / burstDuration, 2),
        "snapshots": snapshots,
        "dirty_before_final_drain": pendingCount,
        "drain_duration_s": round(drainDuration, 4),
        "final_db_writes": finalMetrics["db_writes"],
    }
    print(json.dumps(result, indent=2), flush=True)
    return result


def renderTable(results):
    cols = [
        ("strategy", "strategy"),
        ("workload", "workload"),
        ("throughput_rps", "rps"),
        ("avg_latency_ms", "avg_ms"),
        ("p95_latency_ms", "p95_ms"),
        ("p99_latency_ms", "p99_ms"),
        ("db_reads", "db_reads"),
        ("db_writes", "db_writes"),
        ("cache_hits", "hits"),
        ("cache_misses", "miss"),
        ("cache_hit_rate", "hit_rate"),
    ]
    head = "| " + " | ".join(c[1] for c in cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    body = []
    for r in results:
        body.append("| " + " | ".join(str(r.get(c[0], "")) for c in cols) + " |")
    return "\n".join([head, sep] + body)


def main():
    allResults = []
    for workload in workloads:
        for strategyName in ("cache_aside", "write_through", "write_back"):
            allResults.append(runOne(strategyName, workload))

    accumResult = writeBackAccumulation()

    output = {
        "results": allResults,
        "write_back_accumulation": accumResult,
    }
    with open(os.path.join(resultsDir, "results.json"), "w") as f:
        json.dump(output, f, indent=2)

    table = renderTable(allResults)
    with open(os.path.join(resultsDir, "results_table.md"), "w") as f:
        f.write("# Results\n\n")
        f.write(table)
        f.write("\n\n## Write-Back accumulation\n\n")
        f.write("```json\n")
        f.write(json.dumps(accumResult, indent=2))
        f.write("\n```\n")

    print("\n=== FINAL TABLE ===\n")
    print(table)


if __name__ == "__main__":
    main()
