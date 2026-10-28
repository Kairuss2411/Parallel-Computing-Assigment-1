// Correctness test for reusable barriers.
// Checks that all threads have reached each episode before any thread proceeds.

#include "barrier.h"

#include <atomic>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

template <typename Barrier>
bool test_barrier(const std::string& name, int threads, int episodes) {
    Barrier barrier(threads);
    std::vector<std::atomic<int>> arrived(static_cast<std::size_t>(episodes));
    for (auto& value : arrived) value.store(0, std::memory_order_relaxed);

    std::atomic<bool> passed{true};
    std::vector<std::thread> workers;
    workers.reserve(static_cast<std::size_t>(threads));

    for (int t = 0; t < threads; ++t) {
        workers.emplace_back([&]() {
            bool local_sense = false;
            for (int e = 0; e < episodes; ++e) {
                arrived[static_cast<std::size_t>(e)].fetch_add(
                    1, std::memory_order_relaxed);

                barrier.arrive(local_sense);

                if (arrived[static_cast<std::size_t>(e)].load(
                        std::memory_order_relaxed) != threads) {
                    passed.store(false, std::memory_order_relaxed);
                }
            }
        });
    }

    for (auto& worker : workers) worker.join();

    const bool ok = passed.load(std::memory_order_relaxed);
    std::cout << name << ", threads=" << threads
              << ", episodes=" << episodes
              << ": " << (ok ? "PASS" : "FAIL") << '\n';
    return ok;
}

template <typename Barrier>
bool test_zero_arg_barrier(const std::string& name, int threads, int episodes) {
    Barrier barrier(threads);
    std::vector<std::atomic<int>> arrived(static_cast<std::size_t>(episodes));
    for (auto& value : arrived) value.store(0, std::memory_order_relaxed);

    std::atomic<bool> passed{true};
    std::vector<std::thread> workers;
    workers.reserve(static_cast<std::size_t>(threads));

    for (int t = 0; t < threads; ++t) {
        workers.emplace_back([&]() {
            for (int e = 0; e < episodes; ++e) {
                arrived[static_cast<std::size_t>(e)].fetch_add(
                    1, std::memory_order_relaxed);

                barrier.arrive();

                if (arrived[static_cast<std::size_t>(e)].load(
                        std::memory_order_relaxed) != threads) {
                    passed.store(false, std::memory_order_relaxed);
                }
            }
        });
    }

    for (auto& worker : workers) worker.join();

    const bool ok = passed.load(std::memory_order_relaxed);
    std::cout << name << ", threads=" << threads
              << ", episodes=" << episodes
              << ": " << (ok ? "PASS" : "FAIL") << '\n';
    return ok;
}

int main() {
    constexpr int episodes = 200;
    const int thread_counts[] = {1, 2, 4, 8};
    bool all_passed = true;

    for (int n : thread_counts) {
        all_passed &= test_barrier<SenseBarrier>("srb", n, episodes);
        all_passed &= test_barrier<SenseBarrierBackoff>("srb_backoff", n, episodes);
        all_passed &= test_zero_arg_barrier<StdBarrier>("std_barrier", n, episodes);
#ifdef HAVE_PTHREAD_BARRIER
        all_passed &= test_zero_arg_barrier<PthreadBarrier>("pthread_barrier", n, episodes);
#endif
    }

    return all_passed ? 0 : 1;
}
