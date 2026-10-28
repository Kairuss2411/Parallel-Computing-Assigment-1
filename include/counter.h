#pragma once

#include <atomic>
#include <mutex>
#include <thread>
#include <chrono>

// 1. Mutex Counter
class MutexCounter {
private:
    long long value = 0;
    std::mutex mtx;

public:
    void increment() {
        std::lock_guard<std::mutex> lock(mtx);
        ++value;
    }

    long long get() {
        std::lock_guard<std::mutex> lock(mtx);
        return value;
    }
};

// 2. CAS Counter (Compare-And-Swap)
class CASCounter {
private:
    std::atomic<long long> value{0};

public:
    void increment() {
        long long expected = value.load();

        while (!value.compare_exchange_weak(
            expected, expected + 1
        )) {
            // CAS thất bại: expected được cập nhật
            // và vòng lặp tiếp tục thử lại.
        }
    }

    long long get() {
        return value.load();
    }
};

// 3. FAA Counter (Fetch-And-Add)
class FAACounter {
private:
    std::atomic<long long> value{0};

public:
    void increment() {
        value.fetch_add(1);
    }

    long long get() {
        return value.load();
    }
};

// 4. CAS Counter with Exponential Backoff
class CASBackoffCounter {
private:
    std::atomic<long long> value{0};

public:
    void increment() {
        long long expected = value.load(
            std::memory_order_relaxed
        );

        // Thời gian chờ ban đầu và giới hạn tối đa (microseconds)
        int delay_us = 1;
        const int max_delay_us = 1024;

        while (!value.compare_exchange_weak(
            expected,
            expected + 1,
            std::memory_order_relaxed,
            std::memory_order_relaxed
        )) {
            // CAS thất bại: chờ trước khi thử lại
            std::this_thread::sleep_for(
                std::chrono::microseconds(delay_us)
            );

            // Tăng thời gian chờ theo cấp số nhân
            if (delay_us < max_delay_us) {
                delay_us = (delay_us * 2 > max_delay_us)
                    ? max_delay_us
                    : delay_us * 2;
            }
        }
    }

    long long get() {
        return value.load(std::memory_order_relaxed);
    }
};