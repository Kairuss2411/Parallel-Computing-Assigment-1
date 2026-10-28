CXX      := g++
CXXFLAGS := -std=c++20 -O2 -Wall -Wextra -pthread -fopenmp -Iinclude
HDRS     := $(wildcard include/*.h)
APPS     := bench_lock test_lock bench_barrier test_barrier

all: $(addprefix build/,$(APPS))

build/bench_%: src/bench_%.cpp $(HDRS) | build
	$(CXX) $(CXXFLAGS) $< -o $@

build/test_%: tests/test_%.cpp $(HDRS) | build
	$(CXX) $(CXXFLAGS) $< -o $@

test: all
	./build/test_lock
	./build/test_barrier

build:
	mkdir -p build

clean:
	rm -rf build

.PHONY: all test clean

barrier: build/test_barrier build/bench_barrier
	@echo "--- CHAY KIEM THU BARRIER ---"
	./build/test_barrier
	@echo "--- CHAY BENCHMARK BARRIER ---"
	mkdir -p results
	./build/bench_barrier > results/barrier.csv
	@echo "--- HOAN THANH: results/barrier.csv ---"

.PHONY: barrier
