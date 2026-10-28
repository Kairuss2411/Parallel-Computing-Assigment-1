// Task 2 benchmark: barrier episodes per second, with no useful work between barriers.
// Build as C++20. On Windows, pthread_barrier is unavailable and is not offered.
//
// Usage:
// bench_barrier.exe --algorithm=srb --threads=4 --episodes=100000 --reps=3 --platform=windows
// Algorithms: srb, srb_backoff, std_barrier
// On supported POSIX systems, pthread_barrier may also be available.

#include "common.h"
#include "barrier.h"

#include <chrono>
#include <cstdio>
#include <exception>
#include <string>
#include <thread>
#include <vector>

using Clock = std::chrono::steady_clock;

template <typename Barrier>
double run_sense_barrier(Barrier& barrier, int threads, int episodes) {
    std::vector<std::thread> workers;
    workers.reserve(static_cast<std::size_t>(threads));

    const auto start = Clock::now();
    for (int i = 0; i < threads; ++i) {
        workers.emplace_back([&barrier, episodes]() {
            bool local_sense = false;
            for (int e = 0; e < episodes; ++e) {
                barrier.arrive(local_sense);
            }
        });
    }

    for (auto& worker : workers) worker.join();
    return std::chrono::duration<double>(Clock::now() - start).count();
}

template <typename Barrier>
double run_zero_arg_barrier(Barrier& barrier, int threads, int episodes) {
    std::vector<std::thread> workers;
    workers.reserve(static_cast<std::size_t>(threads));

    const auto start = Clock::now();
    for (int i = 0; i < threads; ++i) {
        workers.emplace_back([&barrier, episodes]() {
            for (int e = 0; e < episodes; ++e) barrier.arrive();
        });
    }

    for (auto& worker : workers) worker.join();
    return std::chrono::duration<double>(Clock::now() - start).count();
}

int main(int argc, char** argv) {
    const std::string algorithm = get_str_arg(argc, argv, "algorithm", "srb");
    const int threads = get_int_arg(argc, argv, "threads", 4);
    const int episodes = get_int_arg(argc, argv, "episodes", 100000);
    const int reps = get_int_arg(argc, argv, "reps", 1);
#if defined(_WIN32)
    const std::string default_platform = "windows";
#elif defined(__APPLE__)
    const std::string default_platform = "macos";
#else
    const std::string default_platform = "linux";
#endif
    const std::string platform = get_str_arg(argc, argv, "platform", default_platform);

    if (threads <= 0 || episodes <= 0 || reps <= 0) {
        std::fprintf(stderr, "Error: threads, episodes, and reps must be positive.\n");
        return 2;
    }

    try {
        for (int rep = 0; rep < reps; ++rep) {
            double seconds = 0.0;

            if (algorithm == "srb") {
                SenseBarrier barrier(threads);
                seconds = run_sense_barrier(barrier, threads, episodes);
            } else if (algorithm == "srb_backoff") {
                SenseBarrierBackoff barrier(threads);
                seconds = run_sense_barrier(barrier, threads, episodes);
            } else if (algorithm == "std_barrier") {
                StdBarrier barrier(threads);
                seconds = run_zero_arg_barrier(barrier, threads, episodes);
            }
#ifdef HAVE_PTHREAD_BARRIER
            else if (algorithm == "pthread_barrier") {
                PthreadBarrier barrier(threads);
                seconds = run_zero_arg_barrier(barrier, threads, episodes);
            }
#endif
            else {
                std::fprintf(stderr, "Unknown or unsupported algorithm: %s\n",
                             algorithm.c_str());
                return 2;
            }

            if (seconds <= 0.0) {
                std::fprintf(stderr, "Error: invalid benchmark duration.\n");
                return 3;
            }

            csv_row(platform, 2, algorithm, threads, 0,
                    "episodes_per_sec", static_cast<double>(episodes) / seconds, rep);
            csv_row(platform, 2, algorithm, threads, 0,
                    "episodes_done", static_cast<double>(episodes), rep);
            csv_row(platform, 2, algorithm, threads, 0,
                    "wall_seconds", seconds, rep);
        }
    } catch (const std::exception& ex) {
        std::fprintf(stderr, "Error: %s\n", ex.what());
        return 1;
    }

    return 0;
}
