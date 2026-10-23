"""
Standalone load test runner for NFR-01 and NFR-02.
Executes Locust in headless mode or concurrent HTTP benchmarking against the API,
tabulates p50, p95, p99 latencies, compares them against targets, and profiles
the request path.
"""
import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any


def run_locust_cli(
    host: str = "http://localhost:8000",
    users: int = 1000,
    spawn_rate: int = 50,
    run_time: str = "30s",
    csv_prefix: str = "tests/load/results"
) -> int:
    """
    Executes Locust CLI in headless mode, writing summary metrics to CSV.
    """
    cmd = [
        sys.executable,
        "-m", "locust",
        "-f", "tests/load/locustfile.py",
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", run_time,
        "--host", host,
        f"--csv={csv_prefix}",
        "--only-summary"
    ]

    print(f"Executing Locust Benchmark: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


def profile_and_report_results(csv_prefix: str = "tests/load/results") -> Dict[str, Any]:
    """
    Reads the generated stats CSV and prints a clean report comparing p95 with targets.
    """
    stats_file = Path(f"{csv_prefix}_stats.csv")
    if not stats_file.exists():
        print(f"Warning: Stats file {stats_file} not found.")
        return {}

    import csv
    results = {}
    with open(stats_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "")
            if name and name != "Aggregated":
                results[name] = {
                    "requests": int(row.get("Request Count", 0)),
                    "failures": int(row.get("Failure Count", 0)),
                    "median": float(row.get("50%", 0)),
                    "p95": float(row.get("95%", 0)),
                    "p99": float(row.get("99%", 0)),
                    "avg": float(row.get("Average Response Time", 0)),
                }

    print("\n" + "=" * 80)
    print("                    PERFORMANCE BENCHMARK REPORT                    ")
    print("=" * 80)

    for endpoint, metrics in results.items():
        print(f"\nEndpoint: {endpoint}")
        print(f"  Requests Processed: {metrics['requests']} (Failures: {metrics['failures']})")
        print(f"  Median (p50):       {metrics['median']:.2f} ms")
        print(f"  95th Percentile:    {metrics['p95']:.2f} ms")
        print(f"  99th Percentile:    {metrics['p99']:.2f} ms")
        print(f"  Average:            {metrics['avg']:.2f} ms")

        # Evaluate against targets
        if "recommendations" in endpoint:
            target_p95 = 500.0  # NFR-01
            passed = metrics['p95'] < target_p95
            status = "PASSED [OK]" if passed else "FAILED [BREACH]"
            print(f"  NFR-01 Target (< 500 ms p95): {metrics['p95']:.2f} ms <= 500 ms -> {status}")
        elif "heatmap" in endpoint:
            target_p95 = 3000.0  # NFR-02
            passed = metrics['p95'] < target_p95
            status = "PASSED [OK]" if passed else "FAILED [BREACH]"
            print(f"  NFR-02 Target (< 3.0 s):      {metrics['p95']:.2f} ms <= 3000 ms -> {status}")

    print("=" * 80 + "\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Locust load test for NFR-01 and NFR-02")
    parser.add_argument("--host", default="http://localhost:8000", help="Host under test")
    parser.add_argument("--users", type=int, default=1000, help="Concurrent learners (default: 1000)")
    parser.add_argument("--spawn-rate", type=int, default=50, help="Users to spawn per second")
    parser.add_argument("--run-time", default="30s", help="Duration of load test (e.g. 30s, 1m)")
    parser.add_argument("--csv", default="tests/load/results", help="CSV results prefix")

    args = parser.parse_args()
    code = run_locust_cli(
        host=args.host,
        users=args.users,
        spawn_rate=args.spawn_rate,
        run_time=args.run_time,
        csv_prefix=args.csv
    )
    if code == 0:
        profile_and_report_results(args.csv)
    sys.exit(code)
