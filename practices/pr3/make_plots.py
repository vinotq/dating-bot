import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

resultsDir = os.environ.get("RESULTS_DIR", "results")
with open(os.path.join(resultsDir, "results.json")) as f:
    data = json.load(f)

allResults = data["results"]
workloads = ["read_heavy", "balanced", "write_heavy"]
strategyNames = ["cache_aside", "write_through", "write_back"]
colors = {"cache_aside": "#4C78A8", "write_through": "#F58518", "write_back": "#54A24B"}


def getValue(strategy, workload, key):
    for r in allResults:
        if r["strategy"] == strategy and r["workload"] == workload:
            return r[key]
    return None


def groupedBar(metric, title, ylabel, fname, log=False):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    xPos = range(len(workloads))
    width = 0.26
    for i, s in enumerate(strategyNames):
        values = [getValue(s, w, metric) for w in workloads]
        offsets = [xi + (i - 1) * width for xi in xPos]
        bars = ax.bar(offsets, values, width, label=s, color=colors[s])
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:g}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(xPos))
    ax.set_xticklabels(workloads)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    if log:
        ax.set_yscale("log")
    fig.tight_layout()
    outputPath = os.path.join(resultsDir, fname)
    fig.savefig(outputPath, dpi=130)
    plt.close(fig)
    print("wrote", outputPath)


groupedBar("throughput_rps", "Пропускная способность по стратегии и нагрузке", "запросов/с", "chart_throughput.png")
groupedBar("avg_latency_ms", "Средняя задержка", "мс", "chart_latency.png")
groupedBar("cache_hit_rate", "Доля попаданий в кеш", "доля (0..1)", "chart_hit_rate.png")
groupedBar("db_reads", "Чтений из БД", "количество (лог. шкала)", "chart_db_reads.png", log=True)
groupedBar("db_writes", "Записей в БД", "количество", "chart_db_writes.png")

fig, ax = plt.subplots(figsize=(8, 4.5))
percentileKeys = ["p50_latency_ms", "p95_latency_ms", "p99_latency_ms"]
percentileLabels = ["p50", "p95", "p99"]
xPos = range(len(percentileLabels))
width = 0.26
for i, s in enumerate(strategyNames):
    values = [getValue(s, "balanced", k) for k in percentileKeys]
    offsets = [xi + (i - 1) * width for xi in xPos]
    bars = ax.bar(offsets, values, width, label=s, color=colors[s])
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:g}", ha="center", va="bottom", fontsize=8)
ax.set_xticks(list(xPos))
ax.set_xticklabels(percentileLabels)
ax.set_ylabel("ms")
ax.set_title("Перцентили задержки, равномерная нагрузка")
ax.legend()
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(resultsDir, "chart_latency_percentiles.png"), dpi=130)
plt.close(fig)
print("wrote chart_latency_percentiles.png")

accumData = data["write_back_accumulation"]
snapshots = accumData["snapshots"]
xValues = [s["after_writes"] for s in snapshots]
dirtyValues = [s["dirty_queue"] for s in snapshots]
dbWriteValues = [s["db_writes_so_far"] for s in snapshots]
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(xValues, dirtyValues, marker="o", label="dirty_queue", color="#E45756")
ax.plot(xValues, dbWriteValues, marker="s", label="db_writes (during burst)", color="#4C78A8")
ax.set_xlabel("client writes issued")
ax.set_ylabel("count")
ax.set_title("Write-Back: очередь растёт, БД не затронута во время бурста")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(resultsDir, "chart_writeback_accumulation.png"), dpi=130)
plt.close(fig)
print("wrote chart_writeback_accumulation.png")
