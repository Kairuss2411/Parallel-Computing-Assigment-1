#pragma once

#include <atomic>
#include <barrier>
#include <stdexcept>
#include <thread>

#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
#include <immintrin.h>
#endif

#if !defined(_WIN32) && !defined(__APPLE__)
#include <pthread.h>
#define HAVE_PTHREAD_BARRIER 1
#endif

// CPU pause hint on x86/x64; yield on other architectures.
inline void cpu_relax() noexcept {
#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
    _mm_pause();
#elif (defined(__x86_64__) || defined(__i386__)) && \
      (defined(__GNUC__) || defined(__clang__))
    __builtin_ia32_pause();
#else
    std::this_thread::yield();
#endif
}

// Reusable centralized sense-reversing barrier.
// The exits counter prevents a fast thread from entering the next episode
// before every peer has left the current episode.
class SenseBarrier {
public:
    explicit SenseBarrier(int n)
        : num_threads_(validate_threads(n)),
          count_(0),
          global_sense_(false),
          exits_(0) {}

    // Each worker owns local_sense, initialized to false.
    void arrive(bool& local_sense) noexcept {
        local_sense = !local_sense;

        if (count_.fetch_add(1, std::memory_order_acq_rel)
            == num_threads_ - 1) {
            count_.store(0, std::memory_order_release);
            global_sense_.store(local_sense, std::memory_order_release);

            while (exits_.load(std::memory_order_acquire)
                   != num_threads_ - 1) {
                cpu_relax();
            }
            exits_.store(0, std::memory_order_relaxed);
        } else {
            while (global_sense_.load(std::memory_order_acquire)
                   != local_sense) {
                cpu_relax();
            }
            exits_.fetch_add(1, std::memory_order_release);
        }
    }

private:
    static int validate_threads(int n) {
        if (n <= 0) throw std::invalid_argument("Barrier thread count must be positive");
        return n;
    }

    const int num_threads_;
    std::atomic<int> count_;
    std::atomic<bool> global_sense_;
    std::atomic<int> exits_;
};

// Same algorithm, with a larger exponential backoff cap.
class SenseBarrierBackoff {
public:
    explicit SenseBarrierBackoff(int n)
        : num_threads_(validate_threads(n)),
          count_(0),
          global_sense_(false),
          exits_(0) {}

    void arrive(bool& local_sense) noexcept {
        local_sense = !local_sense;

        if (count_.fetch_add(1, std::memory_order_acq_rel)
            == num_threads_ - 1) {
            count_.store(0, std::memory_order_release);
            global_sense_.store(local_sense, std::memory_order_release);

            unsigned delay = 1;
            constexpr unsigned max_delay = 1024;
            while (exits_.load(std::memory_order_acquire)
                   != num_threads_ - 1) {
                for (unsigned k = 0; k < delay; ++k) cpu_relax();
                if (delay < max_delay) delay *= 2;
            }
            exits_.store(0, std::memory_order_relaxed);
        } else {
            unsigned delay = 1;
            constexpr unsigned max_delay = 1024;
            while (global_sense_.load(std::memory_order_acquire)
                   != local_sense) {
                for (unsigned k = 0; k < delay; ++k) cpu_relax();
                if (delay < max_delay) delay *= 2;
            }
            exits_.fetch_add(1, std::memory_order_release);
        }
    }

private:
    static int validate_threads(int n) {
        if (n <= 0) throw std::invalid_argument("Barrier thread count must be positive");
        return n;
    }

    const int num_threads_;
    std::atomic<int> count_;
    std::atomic<bool> global_sense_;
    std::atomic<int> exits_;
};

// POSIX barrier is available only on supported POSIX systems.
#ifdef HAVE_PTHREAD_BARRIER
class PthreadBarrier {
public:
    explicit PthreadBarrier(int n) {
        if (n <= 0) throw std::invalid_argument("Barrier thread count must be positive");
        const int rc = pthread_barrier_init(&barrier_, nullptr,
                                            static_cast<unsigned int>(n));
        if (rc != 0) throw std::runtime_error("pthread_barrier_init failed");
    }

    ~PthreadBarrier() { pthread_barrier_destroy(&barrier_); }

    PthreadBarrier(const PthreadBarrier&) = delete;
    PthreadBarrier& operator=(const PthreadBarrier&) = delete;

    void arrive() { pthread_barrier_wait(&barrier_); }

private:
    pthread_barrier_t barrier_{};
};
#endif

// Standard C++20 barrier.
class StdBarrier {
public:
    explicit StdBarrier(int n) : barrier_(validate_threads(n)) {}

    void arrive() { barrier_.arrive_and_wait(); }

private:
    static std::ptrdiff_t validate_threads(int n) {
        if (n <= 0) throw std::invalid_argument("Barrier thread count must be positive");
        return static_cast<std::ptrdiff_t>(n);
    }

    std::barrier<> barrier_;
};
