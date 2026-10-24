#!/usr/bin/env bash
# Part 1 (mutex locks) -- full benchmark sweep = three parameter sets.
#
# Usage: scripts/run_lock.sh <platform> [options]
#
# Options:
#   --reps N          repetitions per configuration   (default 5)
#   --threads "..."   override the thread list used by every set
#                     (default: 1 2 4 8 <cores>)
#   --sets "1 2 3"    only run the listed sets        (default: all)
#   --no-warmup       skip the discarded warm-up run of each configuration
#   --force           delete the CSVs of this platform first (fresh run)
#   -h, --help        show this help
#
# Appends one row per run to results/<platform>/:
#
#   set 1  lock.csv          algo,threads,iters,outside_work,N,time_ms,rep
#          main sweep: 8 algos x threads(1..cores) x OUTSIDE_WORK{0,1,4}
#          (CS holds 100% / 50% / 20% of the work),
#          N=10007 (~15 us per is_prime), iters=2000                     600 runs
#
#   set 2  lock_nscan.csv    same columns, N=100003 (10x costlier CS),
#          iters=200, threads{1,4,cores}, OUTSIDE_WORK{0,4}             240 runs
#
#   set 3  lock_backoff.csv  algo,...,max_delay,time_ms,rep
#          ttas_backoff (PAUSE count 64/512/4096) and ttas_backoff_sleep
#          (1000/10000/100000 ns) x threads{1,4,8,cores} x OUTSIDE_WORK{0,4}
#                                                                       240 runs
#
# Values follow HUONG_DAN_ASSIGNMENT1.md sec. 3.5: >=5 reps (median reported by
# scripts/plot_lock.py), algorithms interleaved inside each rep so thermal drift
# hits all of them equally, and one warm-up run discarded per configuration.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PLAT=""
REPS=5
SETS="1 2 3"
THREADS_OVERRIDE=""
WARMUP=1
FORCE=0

usage() {
    sed -n '2,/^set -euo/{/^set -euo/d;s/^# \{0,1\}//;p}' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --reps)      REPS=${2:?--reps needs a value};                 shift 2 ;;
        --threads)   THREADS_OVERRIDE=${2:?--threads needs a value};  shift 2 ;;
        --sets)      SETS=${2:?--sets needs a value};                 shift 2 ;;
        --no-warmup) WARMUP=0; shift ;;
        --force)     FORCE=1;  shift ;;
        -h|--help)   usage; exit 0 ;;
        -*)          echo "unknown option: $1" >&2; usage >&2; exit 1 ;;
        *)           PLAT=$1; shift ;;
    esac
done

if [ -z "$PLAT" ]; then
    echo "error: platform name required (e.g. i7-1265U, lab_pc_ryzen7)" >&2
    usage >&2
    exit 2
fi

# ---------------------------------------------------------------- parameters
BIN=./build/bench_lock
if [ ! -x "$BIN" ]; then
    echo "building $BIN ..." >&2
    make build/bench_lock >&2
fi

CORES=$(nproc)

# sort numerically and drop duplicates (cores=4 -> "1 2 4 8", cores=12 -> "1 2 4 8 12")
uniq_threads() {
    printf '%s\n' "$@" | sort -n -u | paste -sd' ' -
}

THREADS_MAIN=${THREADS_OVERRIDE:-$(uniq_threads 1 2 4 8 "$CORES")}
THREADS_SCAN=${THREADS_OVERRIDE:-$(uniq_threads 1 4 "$CORES")}
THREADS_BACKOFF=${THREADS_OVERRIDE:-$(uniq_threads 1 4 8 "$CORES")}

ALGOS="tas ttas ttas_backoff ttas_backoff_sleep mcs std_mutex pthread omp"
OW_ALL="0 1 4"                 # 100% / 50% / 20% of the work in the CS
OW_BACKOFF="0 4"

N_MAIN=10007
ITERS_MAIN=2000
N_SCAN=100003
ITERS_SCAN=200
DELAYS_PAUSE="64 512 4096"       # PAUSE iterations  (TTASBackoffLock)
DELAYS_NS="1000 10000 100000"    # nanoseconds      (TTASBackoffSleepLock)

OUT="results/$PLAT"
mkdir -p "$OUT"
[ -s "$OUT/sysinfo.txt" ] || bash scripts/sysinfo.sh > "$OUT/sysinfo.txt"

CSV1=$OUT/lock.csv
CSV2=$OUT/lock_nscan.csv
CSV3=$OUT/lock_backoff.csv

if [ "$FORCE" = 1 ]; then
    rm -f "$CSV1" "$CSV2" "$CSV3"
fi

header() { [ -s "$1" ] || echo "$2" > "$1"; }

# ---------------------------------------------------------------- helpers
# bench <algo> <threads> <iters> <ow> <N> <rep> [max_delay]
# Appends one CSV row; max_delay is inserted before time_ms when given.
bench() {
    local a=$1 t=$2 i=$3 ow=$4 n=$5 r=$6 d=${7:-}
    if [ -n "$d" ]; then
        "$BIN" "$a" "$t" "$i" "$ow" "$n" "$d" |
            awk -F, -v d="$d" -v r="$r" -v OFS=, '{print $1,$2,$3,$4,$5,d,$6,r}'
    else
        "$BIN" "$a" "$t" "$i" "$ow" "$n" |
            awk -F, -v r="$r" -v OFS=, '{print $0","r}'
    fi
}

# one discarded warm-up run per algorithm (same configuration)
warmup() {  # <threads> <iters> <ow> <N>
    [ "$WARMUP" = 1 ] || return 0
    local a
    for a in $ALGOS; do "$BIN" "$a" "$@" > /dev/null; done
}

# ---------------------------------------------------------------- set 1
run_set1() {
    header "$CSV1" "algo,threads,iters,outside_work,N,time_ms,rep"
    local ow t r a
    echo "== set 1: main sweep -> $CSV1 ==" >&2
    for ow in $OW_ALL; do
        for t in $THREADS_MAIN; do
            warmup "$t" "$ITERS_MAIN" "$ow" "$N_MAIN"
            for r in $(seq "$REPS"); do
                # interleave algorithms inside a rep -> thermal drift hits all
                for a in $ALGOS; do
                    bench "$a" "$t" "$ITERS_MAIN" "$ow" "$N_MAIN" "$r" >> "$CSV1"
                done
            done
            echo "  [1] ow=$ow threads=$t done" >&2
        done
    done
}

# ---------------------------------------------------------------- set 2
run_set2() {
    header "$CSV2" "algo,threads,iters,outside_work,N,time_ms,rep"
    local ow t r a
    echo "== set 2: N sensitivity (N=$N_SCAN) -> $CSV2 ==" >&2
    for ow in $OW_BACKOFF; do
        for t in $THREADS_SCAN; do
            warmup "$t" "$ITERS_SCAN" "$ow" "$N_SCAN"
            for r in $(seq "$REPS"); do
                for a in $ALGOS; do
                    bench "$a" "$t" "$ITERS_SCAN" "$ow" "$N_SCAN" "$r" >> "$CSV2"
                done
            done
            echo "  [2] N=$N_SCAN ow=$ow threads=$t done" >&2
        done
    done
}

# ---------------------------------------------------------------- set 3
run_set3() {
    header "$CSV3" "algo,threads,iters,outside_work,N,max_delay,time_ms,rep"
    local ow t r d
    echo "== set 3: MAX_DELAY tuning -> $CSV3 ==" >&2
    for t in $THREADS_BACKOFF; do
        for ow in $OW_BACKOFF; do
            if [ "$WARMUP" = 1 ]; then
                "$BIN" ttas_backoff       "$t" "$ITERS_MAIN" "$ow" "$N_MAIN" > /dev/null
                "$BIN" ttas_backoff_sleep "$t" "$ITERS_MAIN" "$ow" "$N_MAIN" > /dev/null
            fi
            for r in $(seq "$REPS"); do
                for d in $DELAYS_PAUSE; do
                    bench ttas_backoff "$t" "$ITERS_MAIN" "$ow" "$N_MAIN" "$r" "$d" >> "$CSV3"
                done
                for d in $DELAYS_NS; do
                    bench ttas_backoff_sleep "$t" "$ITERS_MAIN" "$ow" "$N_MAIN" "$r" "$d" >> "$CSV3"
                done
            done
            echo "  [3] backoff threads=$t ow=$ow done" >&2
        done
    done
}

# ---------------------------------------------------------------- main
echo "platform=$PLAT cores=$CORES reps=$REPS warmup=$WARMUP sets=[$SETS]" >&2
echo "threads: main=[$THREADS_MAIN] scan=[$THREADS_SCAN] backoff=[$THREADS_BACKOFF]" >&2

SECONDS=0
for s in $SETS; do
    case "$s" in
        1) run_set1 ;;
        2) run_set2 ;;
        3) run_set3 ;;
        *) echo "unknown set '$s' (expected 1..3)" >&2; exit 1 ;;
    esac
done

echo "" >&2
for f in "$CSV1" "$CSV2" "$CSV3"; do
    if [ -f "$f" ]; then
        echo "$f: $(( $(wc -l < "$f") - 1 )) runs" >&2
    fi
done
echo "elapsed: ${SECONDS}s" >&2
echo "next: python3 scripts/plot_lock.py $PLAT" >&2
