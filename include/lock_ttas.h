#pragma once
// TTAS spinlock + two exponential-backoff variants (delay doubles up to MAX_DELAY).
// MAX_DELAY is read from the global g_max_delay (0 = default):
//   TTASBackoffLock      : busy-wait of `delay` PAUSE instructions per attempt
//   TTASBackoffSleepLock : std::this_thread::sleep_for(delay ns), as the
//                          assignment suggests (Linux sleep is coarse, ~tens us)

#include <algorithm>
#include <atomic>
#include <chrono>
#include <thread>

#include "common.h"

class TTASLock {
    alignas(CACHELINE) std::atomic<bool> flag{false};

public:
    void acquire() {
        for (;;) {
            while (flag.load(std::memory_order_relaxed))
                cpu_relax();
            if (!flag.exchange(true, std::memory_order_acquire)) return;
        }
    }
    void release() { flag.store(false, std::memory_order_release); }
};

class TTASBackoffLock {
    alignas(CACHELINE) std::atomic<bool> flag{false};
    const long max_delay_ = g_max_delay > 0 ? g_max_delay : 256;

public:
    void acquire() {
        long delay = 1;
        for (;;) {
            while (flag.load(std::memory_order_relaxed))
                cpu_relax();
            if (!flag.exchange(true, std::memory_order_acquire)) return;
            for (long i = 0; i < delay; ++i) cpu_relax();
            delay = std::min(delay * 2, max_delay_);
        }
    }
    void release() { flag.store(false, std::memory_order_release); }
};

class TTASBackoffSleepLock {
    alignas(CACHELINE) std::atomic<bool> flag{false};
    const long max_delay_ns_ = g_max_delay > 0 ? g_max_delay : 100000;

public:
    void acquire() {
        long delay_ns = 1;
        for (;;) {
            while (flag.load(std::memory_order_relaxed)) cpu_relax();
            if (!flag.exchange(true, std::memory_order_acquire)) return;
            std::this_thread::sleep_for(std::chrono::nanoseconds(delay_ns));
            delay_ns = std::min(delay_ns * 2, max_delay_ns_);
        }
    }
    void release() { flag.store(false, std::memory_order_release); }
};
