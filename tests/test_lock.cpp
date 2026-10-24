// Correctness tests for all locks: no lost updates + mutual exclusion.
// Usage: ./build/test_lock [iters] [reps]

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <utility>
#include <vector>

#include "lock.h"

namespace {

struct BrokenLock {  // intentionally incorrect, for validating the test itself
    void acquire() {}
    void release() {}
};

struct Result {
    long counter = 0;
    long violations = 0;
};

template <class Lock>
Result run_once(int T, long iters) {
    Lock lock;
    long counter = 0;                 // plain long on purpose: lost updates show up
    std::atomic<int> in_cs{0};
    std::atomic<long> violations{0};
    std::atomic<bool> start{false};

    auto body = [&](int tid) {
        pin_thread(tid % hw_threads());
        while (!start.load(std::memory_order_acquire)) cpu_relax();
        for (long i = 0; i < iters; ++i) {
            lock.acquire();
            if (in_cs.fetch_add(1, std::memory_order_acq_rel) != 0)
                violations.fetch_add(1, std::memory_order_relaxed);
            counter = counter + 1;
            do_not_optimize(counter);  // small amount of work inside the CS
            in_cs.fetch_sub(1, std::memory_order_acq_rel);
            lock.release();
        }
    };

    std::vector<std::thread> th;
    th.reserve(static_cast<size_t>(T));
    for (int t = 0; t < T; ++t) th.emplace_back(body, t);
    start.store(true, std::memory_order_release);
    for (auto& x : th) x.join();

    return Result{counter, violations.load(std::memory_order_relaxed)};
}

std::vector<int> thread_counts() {
    return {1, 2, 4, 8, hw_threads()};
}

template <class Lock>
bool test_lock(const char* name, const std::vector<int>& counts, long iters,
               int reps) {
    bool ok = true;
    for (int T : counts) {
        const long expected = static_cast<long>(T) * iters;
        for (int r = 0; r < reps; ++r) {
            Result res = run_once<Lock>(T, iters);
            if (res.counter != expected || res.violations != 0) {
                ok = false;
                std::printf("    T=%d counter=%ld (expected %ld) violations=%ld\n",
                            T, res.counter, expected, res.violations);
            }
        }
    }
    std::printf("[%s] %s\n", ok ? "PASS" : "FAIL", name);
    return ok;
}

// The test must catch a lock that does not actually exclude.
bool verify_test_detects_breakage(long iters) {
    Result res = run_once<BrokenLock>(4, iters);
    const long expected = 4L * iters;
    const bool detected = (res.counter != expected) || (res.violations > 0);
    std::printf("[%s] broken-lock check: counter=%ld (expected %ld) "
                "violations=%ld -> %s\n",
                detected ? "PASS" : "FAIL", res.counter, expected,
                res.violations, detected ? "breakage detected" : "NOT detected");
    return detected;
}

}  // namespace

int main(int argc, char** argv) {
    long iters = 2000;
    int reps = 20;
    if (argc > 1) iters = std::atol(argv[1]);
    if (argc > 2) reps = std::atoi(argv[2]);

    const std::vector<int> counts = thread_counts();
    std::printf("cores=%d iters=%ld reps=%d threads:", hw_threads(), iters, reps);
    for (int T : counts) std::printf(" %d", T);
    std::printf("\n");

    using Fn = bool (*)(const char*, const std::vector<int>&, long, int);
    const std::pair<const char*, Fn> cases[] = {
        {"tas", &test_lock<TASLock>},
        {"ttas", &test_lock<TTASLock>},
        {"ttas_backoff", &test_lock<TTASBackoffLock>},
        {"ttas_backoff_sleep", &test_lock<TTASBackoffSleepLock>},
        {"mcs", &test_lock<MCSLock>},
        {"std_mutex", &test_lock<StdMutexLock>},
        {"pthread", &test_lock<PthreadMutexLock>},
        {"omp", &test_lock<OmpLock>},
    };

    bool ok = true;
    for (const auto& [name, fn] : cases) ok &= fn(name, counts, iters, reps);

    ok &= verify_test_detects_breakage(std::max<long>(iters, 100000));

    std::printf("\n%s\n", ok ? "ALL LOCK TESTS PASSED" : "LOCK TESTS FAILED");
    return ok ? 0 : 1;
}
