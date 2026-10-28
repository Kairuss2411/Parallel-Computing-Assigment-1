# Assignment 1 – Parallel Computing

Reference implementation of the spinlocks / barriers / counters assignment.

Status: **Lock + Barrier implemented.**

Report: `report/report_part1.md` (printable HTML: `report/report_part1.html`,
figures in `report/figures/`). Measurements are stored in
`results/laptop_i7-1265U/`.

## Build

```bash
make            # builds lock + barrier binaries in build/
make test       # runs lock and barrier correctness tests
make barrier    # runs barrier test + writes results/barrier.csv
```

## Layout

```text
include/  common.h, lock_tas.h, lock_ttas.h, lock_mcs.h, lock_baseline.h, lock.h, barrier_sense.h
src/      bench_lock.cpp, bench_barrier.cpp
tests/    test_lock.cpp, test_barrier.cpp
scripts/  sysinfo.sh
```

## Barrier benchmark (Part 2)

Build the project first with `make`. Run the correctness test:

```bash
./build/test_barrier
```

Run one algorithm at a time (the current program does not implement `--mode=all`):

```bash
./build/bench_barrier --algorithm=srb --threads=4 --episodes=500000 --reps=5 --platform=my-machine
./build/bench_barrier --algorithm=srb_backoff --threads=4 --episodes=500000 --reps=5 --platform=my-machine
./build/bench_barrier --algorithm=std_barrier --threads=4 --episodes=500000 --reps=5 --platform=my-machine
```

On supported POSIX systems, `pthread_barrier` is also available:

```bash
./build/bench_barrier --algorithm=pthread_barrier --threads=4 --episodes=500000 --reps=5 --platform=my-machine
```

CSV columns are `platform,task,algorithm,threads,outside_work,metric,value,rep`.
The current implementation benchmarks `srb`, `srb_backoff`, `std_barrier`, and
optionally `pthread_barrier`; it does not currently implement `omp_barrier`.

**Scope note:** the uploaded source tree contains lock and barrier code, but no
Concurrent Counters (Task 3) implementation or benchmark yet. See `REVIEW_NOTES.txt`.

## Benchmark

```bash
./build/bench_lock <algo> <threads> <iters> <outside_work> <N> [max_delay]
```

* `algo`: `tas | ttas | ttas_backoff | ttas_backoff_sleep | mcs | std_mutex | pthread | omp`
* `OUTSIDE_WORK = k` means the critical section holds `1/(k+1)` of the work.
* `N` should be a prime (so `is_prime(N)` runs its whole loop); calibrate so one
  CS is ~10–100 µs and a whole run takes ~0.5–5 s.
* `max_delay` (optional) tunes backoff: **pause count** for `ttas_backoff`,
  **nanoseconds** for `ttas_backoff_sleep` (`0` or omitted = default).
* Output is one CSV line: `algo,threads,iters,outside_work,N,time_ms`.

Example (Intel i7-12700H, 12 logical cores):

```bash
./build/bench_lock ttas_backoff 8 20000 4 100003
./build/bench_lock mcs           8 20000 4 100003 1024
```

## Correctness tests

```bash
./build/test_lock [iters] [reps]
```

For every lock and thread counts `1,2,4,8,…,hw,2*hw`: checks a plain `long`
counter ends at `T*iters` and that an in-CS overlap detector reports zero
violations, repeated `reps` times. A deliberately broken lock is also run to
prove the test detects failures (skipped under TSan).

## Notes

* `MCSLock` stores its node in `thread_local` storage → a thread must hold at
  most one MCS lock at a time (satisfied by every benchmark/test here).
* `pin_thread()` failure is ignored (restricted containers); without pinning
  results are noisier.
* Do not use `-march=native`: binaries must stay comparable across machines.
* **Oversubscription warning:** with `threads > cores` and a non-trivial critical
  section, MCS degenerates (FIFO convoy: every handoff goes to a thread the OS
  may have just preempted). Measured on a 12-thread WSL2 box with `N=10007`:
  `mcs 24 threads` takes ~92 s for `iters=2000` vs ~1.4 s for TAS/TTAS.
  For the `2×cores` sweep point use a much smaller `ITERS` for `mcs`.
