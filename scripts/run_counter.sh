#!/usr/bin/env bash
set -euo pipefail

# Chuyển về thư mục gốc của project
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Nhận tên máy từ tham số đầu tiên
PLAT="${1:?Usage: bash scripts/run_counter.sh <platform>}"
OUT="results/$PLAT"

mkdir -p "$OUT"

echo "=== Build counter programs ==="
make build/test_counter build/bench_counter

echo "=== Run correctness tests ==="
./build/test_counter

echo "=== Run counter benchmark ==="
./build/bench_counter

# Kiểm tra file kết quả
if [ ! -s counter_results.csv ]; then
    echo "ERROR: counter_results.csv is missing or empty."
    exit 1
fi

# Lưu kết quả theo tên máy
cp counter_results.csv "$OUT/counter.csv"

echo "=== Finished ==="
echo "Results saved to $OUT/counter.csv"
