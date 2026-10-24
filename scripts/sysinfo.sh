#!/usr/bin/env bash
# Dump machine + toolchain info for results/<platform>/sysinfo.txt
set -u

echo "=== date ==="
date -Iseconds

echo "=== uname -a ==="
uname -a

echo "=== os-release ==="
cat /etc/os-release 2>/dev/null || true

echo "=== lscpu ==="
lscpu

echo "=== nproc ==="
nproc

echo "=== memory ==="
grep -E 'MemTotal|MemAvailable' /proc/meminfo 2>/dev/null || true

echo "=== cache sizes ==="
for f in /sys/devices/system/cpu/cpu0/cache/index*/{level,type,size}; do
    printf '%s: ' "$f"; cat "$f" 2>/dev/null || echo "n/a"
done

echo "=== cpu frequency governor ==="
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "n/a"

echo "=== compiler ==="
g++ --version 2>/dev/null | head -1
make --version 2>/dev/null | head -1
python3 --version 2>/dev/null || true
