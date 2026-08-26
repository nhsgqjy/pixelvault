# PixelVault performance report

## Test method

- Date: 2026-08-25
- Host: local Windows development machine
- API: one Uvicorn process on `127.0.0.1:8000`
- Data set: 4 real photo records
- Tool: `backend/performance_test.py` (Python standard library)
- Load profile: `--scale 0.2`, with 10-30 concurrent clients depending on the scenario
- Correctness gate: every measured request returned a successful status; error rate was 0% before and after

The first full-scale baseline did not finish within two minutes. To keep the comparison reproducible, both recorded runs use the same 20% profile. These numbers describe this machine and data set; they are not production capacity claims.

## Results

| Scenario | Requests / concurrency | Baseline req/s | Optimized req/s | Throughput change | Baseline P95 | Optimized P95 | P95 reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Photo list | 60 / 20 | 5.24 | 33.35 | 6.36x | 4156.88 ms | 672.60 ms | 83.8% |
| Album list | 60 / 20 | 5.08 | 33.81 | 6.66x | 4606.23 ms | 609.90 ms | 86.8% |
| Statistics | 30 / 10 | 4.23 | 29.70 | 7.02x | 3859.41 ms | 452.20 ms | 88.3% |
| Thumbnail | 50 / 20 | 4.94 | 34.50 | 6.98x | 4892.38 ms | 578.37 ms | 88.2% |
| Mixed reads | 100 / 30 | 4.58 | 18.41 | 4.02x | 8149.90 ms | 2693.51 ms | 66.9% |
| Upload initialization | 12 / 10 | 3.51 | 7.11 | 2.03x | 3199.89 ms | 1268.89 ms | 60.3% |

## Diagnosis and changes

The API middleware opened SQLite synchronously for authentication and request auditing. Because this happened inside the asynchronous request path, concurrent work was effectively serialized. Every audit insert also repeated a 1000-row retention query.

The optimized implementation:

1. runs session validation in the worker pool rather than blocking the event loop;
2. writes audit events after the response through Starlette background work;
3. enables SQLite WAL mode, a 10-second busy timeout and NORMAL synchronous mode;
4. performs bounded audit cleanup once per 100 inserts instead of on every request.

Read-heavy paths improved by 4.0-7.0x in throughput and 67-88% at P95. Upload initialization improved 2.0x but remains write-bound because SQLite intentionally serializes writers; PostgreSQL plus a dedicated worker queue is the next architecture step if concurrent writes become a product requirement.

## Reproduce

With the API running:

```bash
python -u backend/performance_test.py --scale 0.2 --output artifacts/performance/current.json
```

Raw evidence from this run is stored in `artifacts/performance/baseline.json` and `artifacts/performance/optimized.json`.

## Technical summary

Implemented a reproducible concurrent HTTP benchmark covering gallery, albums, statistics, thumbnails, mixed reads and upload-session initialization; diagnosed synchronous SQLite work in the async middleware path, introduced WAL and deferred/bounded audit writes, increasing read throughput by 4.0-7.0x and reducing mixed-read P95 latency by 66.9% under the recorded local workload with 0% request errors.
