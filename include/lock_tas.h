#pragma once
// TAS (Test-And-Set) spinlock: every attempt writes to the shared flag,
// so all waiters keep the cache line in Modified state -> heavy coherence traffic.

#include <atomic>

#include "common.h"

class TASLock {
    alignas(CACHELINE) std::atomic<bool> flag{false};

public:
    void acquire() {
        while (flag.exchange(true, std::memory_order_acquire))
            cpu_relax();
    }
    void release() { flag.store(false, std::memory_order_release); }
};
