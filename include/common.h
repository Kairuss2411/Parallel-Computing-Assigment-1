#pragma once

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include <type_traits>

#if defined(_MSC_VER) && (defined(_M_X64) || defined(_M_IX86))
#include <immintrin.h>
#elif defined(__linux__)
#include <pthread.h>
#include <sched.h>
#include <unistd.h>
#endif

#ifndef CACHELINE
#define CACHELINE 64
#endif

// Used by the TTAS backoff benchmark variants; 0 means use each class's default.
inline long g_max_delay = 0;

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
#define CPU_RELAX_DEFINED

inline unsigned hw_threads() noexcept {
    const unsigned n = std::thread::hardware_concurrency();
    return n == 0 ? 1u : n;
}

inline double now_ms() noexcept {
    using clock = std::chrono::steady_clock;
    return std::chrono::duration<double, std::milli>(
        clock::now().time_since_epoch()).count();
}

// Best-effort CPU affinity. Failure is intentionally ignored.
inline void pin_thread(unsigned cpu) noexcept {
#if defined(__linux__)
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(cpu % hw_threads(), &cpuset);
    (void)pthread_setaffinity_np(pthread_self(), sizeof(cpuset), &cpuset);
#elif defined(_WIN32)
    // Native Windows affinity support can be added here; do not fail the run.
    (void)cpu;
#else
    (void)cpu;
#endif
}

inline int is_prime(int p) noexcept {
    if (p < 2) return 0;
    if (p == 2) return 1;
    if (p % 2 == 0) return 0;
    for (int d = 3; d <= p / d; d += 2) {
        if (p % d == 0) return 0;
    }
    return 1;
}

template <class T>
inline void do_not_optimize(const T& value) noexcept {
#if defined(__GNUC__) || defined(__clang__)
    asm volatile("" : : "g"(value) : "memory");
#else
    volatile const T* sink = &value;
    (void)sink;
#endif
}

// Parse command-line arguments in --key=value form.
inline std::string get_str_arg(int argc, char** argv,
                               const std::string& key,
                               const std::string& default_value) {
    const std::string prefix = "--" + key + "=";
    for (int i = 1; i < argc; ++i) {
        const std::string arg(argv[i]);
        if (arg.rfind(prefix, 0) == 0) return arg.substr(prefix.size());
    }
    return default_value;
}

inline int get_int_arg(int argc, char** argv,
                       const std::string& key,
                       int default_value) {
    const std::string value = get_str_arg(argc, argv, key, "");
    if (value.empty()) return default_value;

    char* end = nullptr;
    const long parsed = std::strtol(value.c_str(), &end, 10);
    if (end == value.c_str() || *end != '\0' ||
        parsed < -2147483647L - 1L || parsed > 2147483647L) {
        std::cerr << "Invalid integer for --" << key << ": " << value << '\n';
        std::exit(2);
    }
    return static_cast<int>(parsed);
}

// CSV columns: platform,task,algorithm,threads,outside_work,metric,value,rep
inline void csv_row(const std::string& platform, int task,
                    const std::string& algorithm, int threads,
                    int outside_work, const std::string& metric,
                    double value, int rep) {
    std::cout << platform << ','
              << task << ','
              << algorithm << ','
              << threads << ','
              << outside_work << ','
              << metric << ','
              << value << ','
              << rep << '\n';
}
