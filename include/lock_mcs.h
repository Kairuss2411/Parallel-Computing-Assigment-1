#pragma once
// MCS lock: FIFO queue of waiters, each spinning on its own node
// (one cache line per waiter) -> no single hot line under contention.
//
// Caveat: `acquire()`/`release()` take no arguments, so the node is
// thread_local. This is correct only if a thread holds AT MOST ONE MCS lock
// at a time (true for all benchmarks/tests here). Documented in the report.

#include <atomic>

#include "common.h"

struct alignas(CACHELINE) MCSNode {
    std::atomic<MCSNode*> next{nullptr};
    std::atomic<bool> locked{false};
};

class MCSLock {
    alignas(CACHELINE) std::atomic<MCSNode*> tail{nullptr};

    static MCSNode& my_node() {
        static thread_local MCSNode node;
        return node;
    }

public:
    void acquire() {
        MCSNode& me = my_node();
        me.next.store(nullptr, std::memory_order_relaxed);
        MCSNode* pred = tail.exchange(&me, std::memory_order_acq_rel);
        if (pred) {
            me.locked.store(true, std::memory_order_relaxed);
            pred->next.store(&me, std::memory_order_release);
            while (me.locked.load(std::memory_order_acquire))
                cpu_relax();
        }
    }

    void release() {
        MCSNode& me = my_node();
        MCSNode* succ = me.next.load(std::memory_order_acquire);
        if (!succ) {
            MCSNode* expected = &me;
            if (tail.compare_exchange_strong(expected, nullptr,
                                             std::memory_order_acq_rel))
                return;  // no waiter
            while (!(succ = me.next.load(std::memory_order_acquire)))
                cpu_relax();
        }
        succ->locked.store(false, std::memory_order_release);
    }
};
