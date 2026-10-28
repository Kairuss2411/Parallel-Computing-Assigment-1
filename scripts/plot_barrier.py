#!/usr/bin/env python3
"""Plot Task 2 barrier benchmark CSV.

Input rows are emitted by csv_row() in common.h:
platform,task,algorithm,threads,outside_work,metric,value,rep

The CSV is headerless by default; this script also accepts a header row.
Run from the repository root:
    python scripts/plot_barrier.py
    python scripts/plot_barrier.py results/windows/barrier.csv
"""
from pathlib import Path
import csv
import sys
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_INPUTS = [Path("results/barrier.csv")]
OUTPUT_DIR = Path("report/figures")
COLUMNS = [
    "platform", "task", "algorithm", "threads",
    "outside_work", "metric", "value", "rep"
]


def read_rows(paths):
    rows = []
    for path in paths:
        if not path.exists():
            print(f"WARNING: not found: {path}")
            continue
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            for raw in csv.reader(f):
                if not raw or all(not x.strip() for x in raw):
                    continue
                if raw[0].strip().lower() == "platform":
                    continue  # optional header
                if len(raw) < 8:
                    print(f"WARNING: skipping malformed row in {path}: {raw}")
                    continue
                try:
                    rows.append({
                        "platform": raw[0].strip(),
                        "task": int(raw[1]),
                        "algorithm": raw[2].strip(),
                        "threads": int(raw[3]),
                        "outside_work": int(float(raw[4])),
                        "metric": raw[5].strip(),
                        "value": float(raw[6]),
                        "rep": int(raw[7]),
                    })
                except ValueError:
                    print(f"WARNING: skipping invalid row in {path}: {raw}")
    return rows


def median(values):
    values = sorted(values)
    n = len(values)
    if not n:
        return float("nan")
    if n % 2:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) / 2.0


def grouped_medians(rows, metric):
    groups = {}
    for row in rows:
        if row["metric"] != metric:
            continue
        key = (row["algorithm"], row["threads"])
        groups.setdefault(key, []).append(row["value"])
    return {key: median(vals) for key, vals in groups.items()}


def save_line_plot(data, ylabel, title, filename, log_y=False):
    if not data:
        print(f"SKIP {filename}: no data")
        return False

    algorithms = sorted({algo for algo, _ in data})
    thread_counts = sorted({threads for _, threads in data})
    fig, ax = plt.subplots(figsize=(8.5, 5.2))

    for algorithm in algorithms:
        points = sorted(
            (threads, value)
            for (algo, threads), value in data.items()
            if algo == algorithm and math.isfinite(value)
        )
        if not points:
            continue
        xs, ys = zip(*points)
        ax.plot(xs, ys, marker="o", linewidth=2, label=algorithm)

    ax.set_xlabel("Number of threads")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(thread_counts)
    ax.grid(True, alpha=0.3)
    if log_y:
        ax.set_yscale("log")
    ax.legend(title="Barrier algorithm")
    fig.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / filename
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")
    return True


def main():
    paths = [Path(arg) for arg in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_INPUTS
    rows = read_rows(paths)
    if not rows:
        sys.exit(
            "ERROR: no valid benchmark rows found. Run scripts/run_barrier.sh first, "
            "or pass the path to a barrier CSV."
        )

    # Use episodes/sec as the primary performance metric.
    eps = grouped_medians(rows, "episodes_per_sec")
    wall = grouped_medians(rows, "wall_seconds")

    save_line_plot(
        eps,
        "Barrier episodes per second (median)",
        "Task 2 – Barrier throughput vs. thread count",
        "barrier_episodes_per_sec.png",
    )
    save_line_plot(
        wall,
        "Elapsed time (seconds, median)",
        "Task 2 – Barrier elapsed time vs. thread count",
        "barrier_wall_seconds.png",
        log_y=False,
    )

    # Speedup relative to the same algorithm's 1-thread throughput.
    speedup = {}
    for (algo, threads), throughput in eps.items():
        baseline = eps.get((algo, 1))
        if baseline and baseline > 0:
            speedup[(algo, threads)] = throughput / baseline
    save_line_plot(
        speedup,
        "Speedup (throughput / 1-thread throughput)",
        "Task 2 – Barrier throughput speedup",
        "barrier_speedup.png",
    )

    if len({r["threads"] for r in rows}) == 1:
        print(
            "NOTE: CSV contains only one thread count. The plots can be generated, "
            "but meaningful scalability curves require running multiple thread counts."
        )


if __name__ == "__main__":
    main()
