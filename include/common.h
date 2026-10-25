#pragma once
// Shared utilities: cpu_relax, pin_thread, is_prime, do_not_optimize, timer.

#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <thread>

#if defined(__linux__)
#include <pthread.h>
#include <sched.h>
#endif

#if defined(__x86_64__) || defined(__i386__)
#include <immintrin.h>
#endif

constexpr size_t CACHELINE = 64;

// Benchmark knob for the backoff locks (0 = each lock's built-in default).
// Units: pause iterations for TTASBackoffLock, nanoseconds for the sleep variant.
inline long g_max_delay = 0;

// Hint the core that we are spinning (x86 PAUSE).
inline void cpu_relax() {
#if defined(__x86_64__) || defined(__i386__)
    _mm_pause();
#elif defined(__aarch64__)
    asm volatile("yield" ::: "memory");
#else
    std::atomic_signal_fence(std::memory_order_seq_cst);
#endif
}

// Pin the calling thread to a logical CPU (avoid migration noise in measurements).
// Returns false if pinning is not permitted (e.g. restricted container); harmless.
inline bool pin_thread(int core) {
    if (core < 0) return false;
#if defined(__linux__)
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(core, &set);
    return pthread_setaffinity_np(pthread_self(), sizeof(set), &set) == 0;
else
    (void)core;
    return false
#endif
}

inline int hw_threads() {
    unsigned n = std::thread::hardware_concurrency();
    return n ? static_cast<int>(n) : 1;
}

// is_prime exactly as given in the assignment.
inline int is_prime(int p) {
    if (p < 2) return 0;
    int d;
    for (d = 2; d < p; d = d + 1)
        if (p % d == 0) return 0;
    return 1;
}

// Prevent the compiler from eliminating a pure computation whose result is unused.
template <class T>
inline void do_not_optimize(T const& v) {
    asm volatile("" : : "g"(v) : "memory");
}

// Wall-clock milliseconds since an arbitrary epoch (steady clock).
inline double now_ms() {
    using namespace std::chrono;
    return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}
