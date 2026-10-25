#include "counter.h"

#include <iostream>
#include <thread>
#include <vector>

using namespace std;

template <typename Counter>
bool test_counter(
    const char* name,
    int num_threads,
    long long increments_per_thread
) {
    Counter counter;
    vector<thread> threads;

    for (int i = 0; i < num_threads; ++i) {
        threads.emplace_back([&counter, increments_per_thread]() {
            for (long long j = 0;
                 j < increments_per_thread; ++j) {
                counter.increment();
            }
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    long long expected =
        static_cast<long long>(num_threads)
        * increments_per_thread;

    long long actual = counter.get();
    bool passed = (actual == expected);

    cout << name
         << " | threads=" << num_threads
         << " | expected=" << expected
         << " | actual=" << actual
         << " | " << (passed ? "PASS" : "FAIL")
         << '\n';

    return passed;
}

int main() {
    bool all_passed = true;

    const int thread_counts[] = {1, 2, 4, 8};
    const long long increments = 100000;

    for (int n : thread_counts) {
        all_passed &= test_counter<MutexCounter>(
            "Mutex", n, increments
        );

        all_passed &= test_counter<CASCounter>(
            "CAS", n, increments
        );

        all_passed &= test_counter<FAACounter>(
            "FAA", n, increments
        );
    }

    if (!all_passed) {
        cerr << "\nSome counter tests FAILED.\n";
        return 1;
    }

    cout << "\nAll counter tests PASSED.\n";
    return 0;
}
