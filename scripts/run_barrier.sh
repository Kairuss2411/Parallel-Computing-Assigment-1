#!/usr/bin/env bash
# Run Task 2 barrier benchmarks for several algorithms/thread counts and save CSV.
# Run from repository root in MSYS2 UCRT64, Git Bash, or Linux.
set -euo pipefail

PLATFORM="${1:-windows}"
EPISODES="${EPISODES:-100000}"
REPS="${REPS:-5}"
THREADS="${THREADS:-1 2 4 8}"
OUT="results/${PLATFORM}/barrier.csv"

mkdir -p "results/${PLATFORM}"
: > "$OUT"

for algorithm in srb srb_backoff std_barrier; do
  for threads in $THREADS; do
    echo "Running ${algorithm}, threads=${threads}, episodes=${EPISODES}, reps=${REPS}"
    ./build/bench_barrier \
      --algorithm="${algorithm}" \
      --threads="${threads}" \
      --episodes="${EPISODES}" \
      --reps="${REPS}" \
      --platform="${PLATFORM}" >> "$OUT"
  done
done

echo "CSV saved to: $OUT"
echo "Generate plots with:"
echo "  python scripts/plot_barrier.py $OUT"
