#pragma once

#include <atomic>
#include <mutex>

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
            // Nếu CAS thất bại, expected được cập nhật
            // theo giá trị hiện tại; vòng lặp sẽ thử lại.
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
