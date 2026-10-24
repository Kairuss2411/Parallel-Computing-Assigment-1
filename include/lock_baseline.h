#pragma once
// Baseline locks with the same acquire()/release() interface as the spinlocks
// so they can be benchmarked by the same template code.

#include <mutex>

#include <omp.h>
#include <pthread.h>

#include "common.h"

class StdMutexLock {
    std::mutex m_;

public:
    void acquire() { m_.lock(); }
    void release() { m_.unlock(); }
};

class PthreadMutexLock {
    pthread_mutex_t m_;

public:
    PthreadMutexLock() { pthread_mutex_init(&m_, nullptr); }
    ~PthreadMutexLock() { pthread_mutex_destroy(&m_); }
    PthreadMutexLock(const PthreadMutexLock&) = delete;
    PthreadMutexLock& operator=(const PthreadMutexLock&) = delete;

    void acquire() { pthread_mutex_lock(&m_); }
    void release() { pthread_mutex_unlock(&m_); }
};

class OmpLock {
    omp_lock_t l_;

public:
    OmpLock() { omp_init_lock(&l_); }
    ~OmpLock() { omp_destroy_lock(&l_); }
    OmpLock(const OmpLock&) = delete;
    OmpLock& operator=(const OmpLock&) = delete;

    void acquire() { omp_set_lock(&l_); }
    void release() { omp_unset_lock(&l_); }
};
