import random
import threading
import time


def makeValue(profileId, version):
    return {
        "name": f"user_{profileId}",
        "age": 18 + (profileId % 50),
        "bio": f"bio of user {profileId} v{version}",
    }


def runWorkload(strategy, *, totalOps, readRatio, concurrency, keySpace, seed=47):
    opsPerWorker = totalOps // concurrency
    actualTotal = opsPerWorker * concurrency
    latencies = [None] * concurrency
    errors = [0] * concurrency

    def worker(idx):
        rnd = random.Random(seed + idx)
        localLatencies = []
        for i in range(opsPerWorker):
            profileId = rnd.randint(1, keySpace)
            isRead = rnd.random() < readRatio
            opStart = time.perf_counter()
            try:
                if isRead:
                    strategy.get(profileId)
                else:
                    strategy.set(profileId, makeValue(profileId, i))
            except Exception:
                errors[idx] += 1
            localLatencies.append(time.perf_counter() - opStart)
        latencies[idx] = localLatencies

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(concurrency)]
    workloadStart = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    workloadEnd = time.perf_counter()

    allLatencies = []
    for chunk in latencies:
        if chunk:
            allLatencies.extend(chunk)
    allLatencies.sort()
    count = len(allLatencies)

    def percentile(p):
        if count == 0:
            return 0.0
        idx = min(count - 1, int(round(p * (count - 1))))
        return allLatencies[idx]

    duration = workloadEnd - workloadStart
    return {
        "duration_s": round(duration, 4),
        "ops_total": actualTotal,
        "ops_errors": sum(errors),
        "throughput_rps": round(actualTotal / duration, 2) if duration > 0 else 0.0,
        "avg_latency_ms": round((sum(allLatencies) / count) * 1000, 3) if count else 0.0,
        "p50_latency_ms": round(percentile(0.50) * 1000, 3),
        "p95_latency_ms": round(percentile(0.95) * 1000, 3),
        "p99_latency_ms": round(percentile(0.99) * 1000, 3),
    }
