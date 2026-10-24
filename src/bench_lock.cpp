// Lock benchmark.
//
// Usage: ./build/bench_lock <algo> <threads> <iters> <outside_work> <N> [max_delay]
// Prints one CSV line:  algo,threads,iters,outside_work,N,time_ms
//
// OUTSIDE_WORK = k  =>  critical section holds 1/(k+1) of the work.
// max_delay (optional) tunes the backoff variants' MAX_DELAY
// (pause-count for ttas_backoff, nanoseconds for ttas_backoff_sleep).

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "lock.h"

namespace {

template <class Lock>
double run(int T, long iters, int outside_work, int N) {
    Lock lock;

    auto body = [&](int tid) {
        pin_thread(tid % hw_threads());
        for (long i = 0; i < iters; ++i) {
            lock.acquire();
            do_not_optimize(is_prime(N));  // critical section
            lock.release();
            for (int j = 0; j < outside_work; ++j)
                do_not_optimize(is_prime(N));  // outside work
        }
    };

    double t0 = now_ms();
    std::vector<std::thread> th;
    th.reserve(static_cast<size_t>(T));
    for (int t = 0; t < T; ++t) th.emplace_back(body, t);
    for (auto& x : th) x.join();
    return now_ms() - t0;  // whole-program time
}

using BenchFn = double (*)(int, long, int, int);

struct Entry {
    const char* name;
    BenchFn fn;
};

const Entry kEntries[] = {
    {"tas", &run<TASLock>},
    {"ttas", &run<TTASLock>},
    {"ttas_backoff", &run<TTASBackoffLock>},
    {"ttas_backoff_sleep", &run<TTASBackoffSleepLock>},
    {"mcs", &run<MCSLock>},
    {"std_mutex", &run<StdMutexLock>},
    {"pthread", &run<PthreadMutexLock>},
    {"omp", &run<OmpLock>},
};

void usage(const char* prog) {
    std::fprintf(stderr,
                 "usage: %s <algo> <threads> <iters> <outside_work> <N> "
                 "[max_delay]\n  algo:", prog);
    for (const auto& e : kEntries) std::fprintf(stderr, " %s", e.name);
    std::fprintf(stderr,
                 "\n  max_delay: pause count for ttas_backoff, ns for "
                 "ttas_backoff_sleep (0 = default)\n");
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 6) {
        usage(argv[0]);
        return 1;
    }

    const std::string algo = argv[1];
    const int threads = std::atoi(argv[2]);
    const long iters = std::atol(argv[3]);
    const int outside_work = std::atoi(argv[4]);
    const int N = std::atoi(argv[5]);
    const long max_delay = (argc > 6) ? std::atol(argv[6]) : 0;
    g_max_delay = max_delay;  // backoff knob used by the ttas_backoff locks

    if (threads < 1 || iters < 1 || outside_work < 0 || N < 1) {
        std::fprintf(stderr, "error: invalid arguments\n");
        return 1;
    }

    BenchFn fn = nullptr;
    for (const auto& e : kEntries) {
        if (algo == e.name) {
            fn = e.fn;
            break;
        }
    }
    if (!fn) {
        std::fprintf(stderr, "error: unknown algo '%s'\n", algo.c_str());
        usage(argv[0]);
        return 1;
    }

    const double time_ms = fn(threads, iters, outside_work, N);

    std::printf("%s,%d,%ld,%d,%d,%.3f\n", algo.c_str(), threads, iters,
                outside_work, N, time_ms);
    return 0;
}
