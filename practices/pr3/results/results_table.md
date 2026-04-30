# Results

| strategy | workload | rps | avg_ms | p95_ms | p99_ms | db_reads | db_writes | hits | miss | hit_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| cache_aside | read_heavy | 1534.74 | 10.237 | 35.702 | 44.855 | 3684 | 4038 | 12278 | 3684 | 0.7692 |
| write_through | read_heavy | 2569.01 | 6.08 | 33.531 | 46.672 | 197 | 4038 | 15765 | 197 | 0.9877 |
| write_back | read_heavy | 9437.11 | 1.667 | 4.038 | 10.544 | 203 | 2578 | 15759 | 203 | 0.9873 |
| cache_aside | balanced | 565.38 | 28.099 | 52.916 | 68.19 | 5167 | 10090 | 4743 | 5167 | 0.4786 |
| write_through | balanced | 788.55 | 20.015 | 51.922 | 67.814 | 121 | 10090 | 9789 | 121 | 0.9878 |
| write_back | balanced | 10545.22 | 1.494 | 3.73 | 6.531 | 121 | 6374 | 9789 | 121 | 0.9878 |
| cache_aside | write_heavy | 388.92 | 41.09 | 65.064 | 82.342 | 3157 | 16142 | 701 | 3157 | 0.1817 |
| write_through | write_heavy | 450.42 | 35.353 | 63.612 | 81.488 | 46 | 16142 | 3812 | 46 | 0.9881 |
| write_back | write_heavy | 11198.76 | 1.381 | 3.636 | 5.731 | 42 | 10215 | 3816 | 42 | 0.9891 |

## Write-Back accumulation

```json
{
  "burst_writes": 5000,
  "burst_duration_s": 0.1656,
  "burst_throughput_rps": 30189.67,
  "snapshots": [
    {
      "after_writes": 1,
      "elapsed_s": 0.0001,
      "dirty_queue": 1,
      "db_writes_so_far": 0
    },
    {
      "after_writes": 501,
      "elapsed_s": 0.0177,
      "dirty_queue": 501,
      "db_writes_so_far": 0
    },
    {
      "after_writes": 1001,
      "elapsed_s": 0.0351,
      "dirty_queue": 1001,
      "db_writes_so_far": 0
    },
    {
      "after_writes": 2001,
      "elapsed_s": 0.0673,
      "dirty_queue": 2001,
      "db_writes_so_far": 0
    },
    {
      "after_writes": 3501,
      "elapsed_s": 0.1159,
      "dirty_queue": 3501,
      "db_writes_so_far": 0
    },
    {
      "after_writes": 5000,
      "elapsed_s": 0.1656,
      "dirty_queue": 5000,
      "db_writes_so_far": 0
    }
  ],
  "dirty_before_final_drain": 5000,
  "drain_duration_s": 0.1181,
  "final_db_writes": 2000
}
```
