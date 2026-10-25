#include "counter.h"

#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

using namespace std;
using namespace std::chrono;

// Benchmark one counter implementation.
template <typename Counter>
void run_benchmark(
    const string& name,
    int num_threads,
    long long increments_per_thread,
    int repetitions,
    ofstream& csv
) {
    for (int run = 1; run <= repetitions; ++run) {
        Counter counter;
        vector<thread> threads;

        // Start timing before creating threads.
        auto start = steady_clock::now();

        for (int i = 0; i < num_threads; ++i) {
            threads.emplace_back([&counter, increments_per_thread]() {
                for (long long j = 0;
                     j < increments_per_thread; ++j) {
                    counter.increment();
                }
            });
        }

        // Wait until every thread finishes.
        for (auto& t : threads) {
            t.join();
        }

        auto end = steady_clock::now();

        double elapsed_ms =
            duration<double, milli>(end - start).count();

        long long expected =
            static_cast<long long>(num_threads)
            * increments_per_thread;

        long long actual = counter.get();
        bool correct = (actual == expected);

        cout << name
             << " | threads=" << num_threads
             << " | run=" << run
             << " | expected=" << expected
             << " | actual=" << actual
             << " | time_ms=" << elapsed_ms
             << " | " << (correct ? "PASS" : "FAIL")
             << '\n';

        csv << name << ','
            << num_threads << ','
            << increments_per_thread << ','
            << run << ','
            << expected << ','
            << actual << ','
            << elapsed_ms << ','
            << (correct ? "PASS" : "FAIL")
            << '\n';

        if (!correct) {
            cerr << "ERROR: Counter result is incorrect!\n";
        }
    }
}

int main() {
    const vector<int> thread_counts = {1, 2, 4, 8};
    const long long increments_per_thread = 200000;
    const int repetitions = 5;

    ofstream csv("counter_results.csv");

    if (!csv.is_open()) {
        cerr << "Cannot create counter_results.csv\n";
        return 1;
    }

    csv << "algorithm,threads,increments_per_thread,run,"
        << "expected,actual,time_ms,correctness\n";

    for (int n : thread_counts) {
        run_benchmark<MutexCounter>(
            "Mutex", n, increments_per_thread, repetitions, csv
        );

        run_benchmark<CASCounter>(
            "CAS", n, increments_per_thread, repetitions, csv
        );

        run_benchmark<FAACounter>(
            "FAA", n, increments_per_thread, repetitions, csv
        );
    }

    csv.close();

    cout << "\nBenchmark finished.\n";
    cout << "Results saved to counter_results.csv\n";

    return 0;
}
