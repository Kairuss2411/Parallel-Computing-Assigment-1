CXX      := g++
CXXFLAGS := -std=c++20 -O2 -Wall -Wextra -pthread -fopenmp -Iinclude
HDRS     := $(wildcard include/*.h)
APPS     := bench_lock test_lock

all: $(addprefix build/,$(APPS))

build/bench_%: src/bench_%.cpp $(HDRS) | build
	$(CXX) $(CXXFLAGS) $< -o $@

build/test_%: tests/test_%.cpp $(HDRS) | build
	$(CXX) $(CXXFLAGS) $< -o $@

test: all
	./build/test_lock

build:
	mkdir -p build

clean:
	rm -rf build

.PHONY: all test clean
