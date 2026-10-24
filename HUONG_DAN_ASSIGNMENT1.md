# Hướng dẫn thực hiện Assignment 1 – Parallel Computing

> Mục tiêu: bộ khung **tối giản** – đủ để implement, test đúng đắn, đo hiệu năng và viết báo cáo.
> Giả định: Ubuntu / Intel x86-64, đã có `g++` (≥ 11, hỗ trợ C++20), `make`, `python3` + `matplotlib`/`pandas`, OpenMP, (tuỳ chọn) `openmpi` cho phần 4.
> Hạn nộp: **31/10/2026** – zip gồm **report PDF + toàn bộ source C++**. Số platform thí nghiệm ≥ số thành viên nhóm (2–3).

---

## 0. Bản đồ yêu cầu → deliverable

| Phần đề bài | Cần implement | Cần test đúng đắn | Cần đo | Baseline so sánh |
|---|---|---|---|---|
| 1. Mutex locks | TAS, TTAS (± backoff), MCS | mutual exclusion + đếm tổng | **Thời gian chạy cả chương trình**, thay đổi threads / OUTSIDE_WORK | `std::mutex`, `pthread_mutex_t`, `omp_lock_t` |
| 2. Barrier | Sense-Reversing (± backoff) | mọi thread cùng phase sau barrier | **Số barrier episode / giây** (không có work giữa các barrier) | `pthread_barrier_t`, `std::barrier`, `#pragma omp barrier` |
| 3. Counters | mutex-based, CAS (± backoff), fetch-and-add | tổng cuối = T × iters; giá trị trả về không trùng | **Thời gian chạy** | (so sánh giữa các biến thể với nhau) |
| 4. (optional) MPI | Port lock/barrier/counter sang MPI-3 RMA | tương tự | tương tự | – |

---

## 1. Cấu trúc thư mục

```
pc-assignment1/
├── Makefile
├── README.md                 # cách build/chạy (ngắn)
├── include/                  # header-only, mỗi thuật toán 1 file
│   ├── common.h              # cpu_relax, pin_thread, is_prime, do_not_optimize, timer
│   ├── lock_tas.h
│   ├── lock_ttas.h           # TTAS + biến thể backoff
│   ├── lock_mcs.h
│   ├── lock_baseline.h       # wrapper std::mutex / pthread / omp_lock
│   ├── lock.h                # include tất cả lock (khớp với #include "lock.h" của đề)
│   ├── barrier_sense.h       # sense-reversing (± backoff)
│   ├── barrier_baseline.h    # wrapper pthread / std::barrier / omp
│   └── counter.h             # các loại counter
├── src/                      # chương trình benchmark (mỗi phần 1 file)
│   ├── bench_lock.cpp
│   ├── bench_barrier.cpp
│   └── bench_counter.cpp
├── tests/                    # chương trình test đúng đắn (mỗi phần 1 file)
│   ├── test_lock.cpp
│   ├── test_barrier.cpp
│   └── test_counter.cpp
├── scripts/
│   ├── sysinfo.sh            # lưu lscpu, kernel, g++ version
│   ├── run_all.sh            # chạy toàn bộ sweep -> results/<platform>/*.csv
│   └── plot.py               # CSV -> hình PNG/PDF cho report
├── results/
│   └── <platform_name>/      # vd: laptopA_i7-12700H/
│       ├── sysinfo.txt
│       ├── lock.csv
│       ├── barrier.csv
│       └── counter.csv
├── report/
│   ├── figures/
│   └── report.pdf            # báo cáo cuối (soạn bằng Word/LaTeX/Markdown tuỳ nhóm)
└── mpi/                      # (optional) phần 4
```

**Nguyên tắc thiết kế (giữ tối giản):**
- **Header-only + template** theo kiểu lock/barrier/counter → benchmark là hàm template `run<Lock>()`, tránh chi phí virtual call làm sai lệch kết quả đo.
- Tham số `NUM_OF_THREADS`, `NUM_OF_ITERS`, `OUTSIDE_WORK`, `N` nhận qua **argv** (không `#define` cứng) → không phải compile lại mỗi lần sweep. Tên giữ nguyên như đề để dễ đối chiếu.
- Mỗi chương trình benchmark in **1 dòng CSV** cho mỗi lần chạy; script ngoài lo việc lặp & gom.

---

## 2. Setup tối giản

### 2.1 Makefile

```make
CXX      := g++
CXXFLAGS := -std=c++20 -O2 -Wall -Wextra -pthread -fopenmp -Iinclude
HDRS     := $(wildcard include/*.h)
APPS     := bench_lock bench_barrier bench_counter test_lock test_barrier test_counter

all: $(addprefix build/,$(APPS))

build/bench_%: src/bench_%.cpp $(HDRS) | build
	$(CXX) $(CXXFLAGS) $< -o $@

build/test_%: tests/test_%.cpp $(HDRS) | build
	$(CXX) $(CXXFLAGS) $< -o $@

# Kiểm tra data race / lỗi bộ nhớ (chỉ dùng cho test, không dùng để đo)
tsan: CXXFLAGS := -std=c++20 -O1 -g -pthread -fopenmp -fsanitize=thread -Iinclude
tsan: $(addprefix build/,test_lock test_barrier test_counter)

test: all
	./build/test_lock && ./build/test_barrier && ./build/test_counter

build:
	mkdir -p build

clean:
	rm -rf build
```

> Lưu ý: `tsan` build cần `make clean` trước khi chuyển qua lại với bản `-O2`. Không dùng `-march=native` để binary giống nhau giữa các máy (dễ so sánh, dễ tái lập).

### 2.2 `include/common.h` – các tiện ích dùng chung

```cpp
#pragma once
#include <atomic>
#include <chrono>
#include <thread>
#include <immintrin.h>   // _mm_pause (x86)
#include <pthread.h>
#include <sched.h>

constexpr size_t CACHELINE = 64;

inline void cpu_relax() { _mm_pause(); }

// Ghim thread vào core (tránh OS di chuyển thread làm nhiễu kết quả)
inline void pin_thread(int core) {
    cpu_set_t s; CPU_ZERO(&s); CPU_SET(core, &s);
    pthread_setaffinity_np(pthread_self(), sizeof(s), &s);
}

// is_prime đúng như đề
inline int is_prime(int p) {
    int d;
    for (d = 2; d < p; d = d + 1)
        if (p % d == 0) return 0;
    return 1;
}

// !!! QUAN TRỌNG: ngăn compiler xoá bỏ is_prime(N) vì kết quả không được dùng
template <class T> inline void do_not_optimize(T const& v) {
    asm volatile("" : : "g"(v) : "memory");
}
// Cách dùng trong benchmark:  do_not_optimize(is_prime(N));

inline double now_ms() {
    using namespace std::chrono;
    return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}
```

---

## 3. Phần 1 – Mutex locks

### 3.1 Interface chung

Mọi lock đều có `void acquire(); void release();` (khớp đoạn code mẫu của đề). Để dùng được với baseline, viết wrapper cùng interface.

### 3.2 Code mẫu các lock

**TAS**
```cpp
class TASLock {
    std::atomic<bool> flag{false};
public:
    void acquire() { while (flag.exchange(true, std::memory_order_acquire)) cpu_relax(); }
    void release() { flag.store(false, std::memory_order_release); }
};
```

**TTAS** (spin trên load – chỉ exchange khi thấy flag = false)
```cpp
class TTASLock {
    std::atomic<bool> flag{false};
public:
    void acquire() {
        for (;;) {
            while (flag.load(std::memory_order_relaxed)) cpu_relax();
            if (!flag.exchange(true, std::memory_order_acquire)) return;
        }
    }
    void release() { flag.store(false, std::memory_order_release); }
};
```

**TTAS + exponential backoff** (biến thể): khi `exchange` thất bại thì chờ `delay`, rồi `delay *= 2` tới `MAX_DELAY`.
- Đề gợi ý `std::this_thread::sleep_for(nanoseconds(delay))`. Lưu ý trên Linux `sleep_for` có độ phân giải thô (~vài chục µs) → nên thử **cả hai**: (a) `sleep_for` như đề, (b) busy-wait bằng vòng `cpu_relax()` lặp `delay` lần. Ghi nhận khác biệt vào report.
- `delay` khởi tạo nhỏ (vd 1–10 ns hoặc 16 lần pause), `MAX_DELAY` là tham số để tune.

**MCS**
```cpp
struct alignas(CACHELINE) MCSNode {
    std::atomic<MCSNode*> next{nullptr};
    std::atomic<bool>     locked{false};
};

class MCSLock {
    std::atomic<MCSNode*> tail{nullptr};
    static MCSNode& my() { static thread_local MCSNode n; return n; } // giữ interface acquire()/release() không tham số
public:
    void acquire() {
        MCSNode& me = my();
        me.next.store(nullptr, std::memory_order_relaxed);
        MCSNode* pred = tail.exchange(&me, std::memory_order_acq_rel);
        if (pred) {
            me.locked.store(true, std::memory_order_relaxed);
            pred->next.store(&me, std::memory_order_release);
            while (me.locked.load(std::memory_order_acquire)) cpu_relax();
        }
    }
    void release() {
        MCSNode& me = my();
        MCSNode* succ = me.next.load(std::memory_order_acquire);
        if (!succ) {
            MCSNode* expected = &me;
            if (tail.compare_exchange_strong(expected, nullptr, std::memory_order_acq_rel))
                return;                                  // không có ai chờ
            while (!(succ = me.next.load(std::memory_order_acquire))) cpu_relax();
        }
        succ->locked.store(false, std::memory_order_release);
    }
};
```
Lưu ý: dùng `thread_local` node chỉ đúng khi **mỗi thread giữ tối đa 1 MCS lock tại một thời điểm** (đúng với bài này). Ghi chú điều này trong report.

**Baseline wrappers** (`lock_baseline.h`): `StdMutexLock` (`std::mutex`), `PthreadMutexLock` (`pthread_mutex_t`), `OmpLock` (`omp_lock_t`; init/destroy trong ctor/dtor). Có thể thêm `pthread_spinlock_t` nếu muốn so sánh thêm.

### 3.3 Chương trình benchmark (`src/bench_lock.cpp`)

Khung theo đúng đoạn code của đề:

```cpp
template <class Lock>
double run(int T, long iters, int outside_work, int N) {
    Lock lock;
    auto body = [&](int tid) {
        pin_thread(tid % std::thread::hardware_concurrency());
        for (long i = 0; i < iters; ++i) {
            lock.acquire();
            do_not_optimize(is_prime(N));              // critical section
            lock.release();
            for (int j = 0; j < outside_work; ++j)
                do_not_optimize(is_prime(N));          // outside work
        }
    };
    double t0 = now_ms();
    std::vector<std::thread> th;
    for (int t = 0; t < T; ++t) th.emplace_back(body, t);
    for (auto& x : th) x.join();
    return now_ms() - t0;                              // thời gian cả chương trình
}
```

- CLI: `./bench_lock <algo> <threads> <iters> <outside_work> <N>` → in CSV: `algo,threads,iters,outside_work,N,time_ms`.
- `<algo>` ∈ `tas | ttas | ttas_backoff | mcs | std_mutex | pthread | omp`; dùng `if/else` hoặc `switch` gọi `run<...>`.
- **Chọn N:** dùng số nguyên tố (để `is_prime` chạy hết vòng lặp), ví dụ `10007`, `100003`, `1000003`. Hãy đo trước 1 lần `is_prime(N)` tốn bao lâu, chọn N sao cho critical section cỡ ~10–100 µs; rồi chọn `iters` sao cho 1 lần chạy ~0.5–5 s.
- **OUTSIDE_WORK = k** ⇒ tỉ lệ work trong CS là 1/(k+1) (0 → 100%, 1 → 50%, 2 → 33%…) – đúng định nghĩa đề.

### 3.4 Test đúng đắn (`tests/test_lock.cpp`)

Chạy cho **mọi** lock, nhiều cấu hình threads (1, 2, 4, 8, 2×cores):

1. **Đếm tổng:** biến `long counter` thường (không atomic) tăng trong CS; sau join phải `counter == T * iters`.
2. **Phát hiện vi phạm mutual exclusion trực tiếp:**
   ```cpp
   std::atomic<int> in_cs{0}; std::atomic<long> violations{0};
   // trong CS:
   if (in_cs.fetch_add(1) != 0) violations++;
   /* làm một chút việc / yield */
   in_cs.fetch_sub(1);
   ```
   Kết quả phải `violations == 0`.
3. **Stress:** lặp test 20–100 lần với iters nhỏ (dễ lộ race hơn 1 lần chạy dài).
4. **Sanitizer:** `make clean && make tsan && ./build/test_lock` – không có cảnh báo data race.
5. (Tuỳ chọn) test thủ công đối chứng: một lock “hỏng” cố ý (acquire/release rỗng) phải **bị test bắt được** → chứng minh test có hiệu lực. Đưa vào report.

### 3.5 Thí nghiệm cần chạy

| Tham số | Giá trị gợi ý |
|---|---|
| threads | 1, 2, 4, 8, … đến số logical core, và thêm 2× số core (oversubscription) |
| OUTSIDE_WORK | 0, 1, 4, 16 (từ contention cao → thấp) |
| N | 1–2 giá trị cố định (đã calibrate) |
| MAX_DELAY (backoff) | 3–4 giá trị (vd 1 µs, 10 µs, 100 µs) |
| lặp lại | ≥ 5 lần mỗi cấu hình, lấy **median** (và min/max hoặc stddev) |

Hình cần có: thời gian vs. threads (mỗi đường = 1 thuật toán, mỗi hình ứng với 1 giá trị OUTSIDE_WORK), có cả baseline.

---

## 4. Phần 2 – Sense-Reversing Barrier

### 4.1 Code mẫu

```cpp
class SenseBarrier {
    const int n;
    alignas(CACHELINE) std::atomic<int>  count;
    alignas(CACHELINE) std::atomic<bool> sense{false};
public:
    explicit SenseBarrier(int n) : n(n), count(n) {}
    // local_sense: biến cục bộ của từng thread, khởi tạo false, truyền bằng tham chiếu
    void wait(bool& local_sense) {
        local_sense = !local_sense;
        if (count.fetch_sub(1, std::memory_order_acq_rel) == 1) {   // thread cuối cùng
            count.store(n, std::memory_order_relaxed);
            sense.store(local_sense, std::memory_order_release);    // giải phóng cả nhóm
        } else {
            while (sense.load(std::memory_order_acquire) != local_sense) cpu_relax();
        }
    }
};
```
Biến thể backoff: trong vòng `while`, chờ `delay` rồi nhân đôi tới `MAX_DELAY`.
Baseline wrapper cùng interface `wait(bool&)` (tham số bị bỏ qua): `pthread_barrier_t`, `std::barrier<>`, và `#pragma omp barrier` (bench OpenMP viết riêng trong `omp parallel`).

### 4.2 Test đúng đắn (`tests/test_barrier.cpp`)

- `E` episode (vd 10 000). Trong mỗi episode: mỗi thread `shared.fetch_add(1)`, gọi `wait()`, rồi **kiểm tra** `shared.load() == (e+1) * T` (mọi thread đều đã đến barrier), rồi `wait()` lần nữa trước khi sang episode sau (tránh thread nhanh cộng sớm).
- Cách khác: mảng `phase[T]`; sau barrier mọi `phase[i]` phải bằng episode hiện tại.
- Kiểm thử số thread khác nhau (kể cả T = 1, và T lẻ), chạy với TSan.

### 4.3 Benchmark (`src/bench_barrier.cpp`)

- Mỗi thread chỉ lặp `for e in 0..E: barrier.wait()` – **không có work** giữa các barrier.
- Metric: `episodes_per_sec = E / elapsed_seconds`. Chọn E đủ lớn (vd 10⁵–10⁶) để chạy ≥ 1 s.
- CLI: `./bench_barrier <algo> <threads> <episodes>` → CSV `algo,threads,episodes,time_ms,episodes_per_sec`.
- `<algo>` ∈ `sense | sense_backoff | pthread | std | omp`.
- Sweep: threads như phần 1; lặp ≥ 5 lần lấy median.

---

## 5. Phần 3 – Concurrent Counters

### 5.1 Các biến thể cần có (`include/counter.h`)

Mọi counter có `long increment()` (trả về giá trị **trước** khi tăng) và `long get()`.

| Tên | Cách làm |
|---|---|
| `MutexCounter` | `std::mutex` bảo vệ `long` |
| `TASCounter` / `TTASCounter` / `MCSCounter` | tái sử dụng lock ở phần 1 (template theo Lock) |
| `CASCounter` | vòng lặp `compare_exchange_weak` |
| `CASBackoffCounter` | như trên + exponential backoff khi CAS thất bại |
| `FetchAddCounter` | `fetch_add(1)` |

```cpp
long CASCounter::increment() {
    long old = v.load(std::memory_order_relaxed);
    while (!v.compare_exchange_weak(old, old + 1, std::memory_order_acq_rel)) { /* old được cập nhật */ }
    return old;
}
```

### 5.2 Test đúng đắn (`tests/test_counter.cpp`)

1. Sau khi T thread, mỗi thread tăng `iters` lần: `get() == T * iters`.
2. **Giá trị trả về phải duy nhất:** mỗi thread ghi các giá trị `increment()` trả về vào bitmap/mảng `seen[T*iters]` (atomic hoặc từng thread vector riêng rồi gộp); không giá trị nào xuất hiện 2 lần, và đủ phủ `[0, T*iters)`.
3. Chạy với TSan.

### 5.3 Benchmark (`src/bench_counter.cpp`)

- Mỗi thread gọi `increment()` `iters` lần (vd 10⁶–10⁷), đo thời gian cả chương trình như phần 1.
- CLI: `./bench_counter <algo> <threads> <iters>` → CSV `algo,threads,iters,time_ms`.
- Sweep threads giống phần 1; tune `MAX_DELAY` cho các bản backoff.

---

## 6. Phần 4 (optional) – MPI-3 One-Sided

Chỉ làm khi 3 phần trên đã xong. Đặt trong `mpi/`, build bằng `mpicxx -O2`, chạy `mpirun -np P`.

- Dùng `MPI_Win_allocate` + `MPI_Win_lock_all` / `MPI_Win_flush`.
- Counter: `MPI_Fetch_and_op(MPI_SUM)` ↔ fetch-and-add; `MPI_Compare_and_swap` ↔ CAS.
- Lock: TAS/TTAS bằng `MPI_Compare_and_swap` trên 1 ô nhớ ở rank 0; MCS bằng `MPI_Fetch_and_op(MPI_REPLACE)` cho `tail` + `MPI_Put` ghi `next`/`locked`.
- Barrier sense-reversing: counter bằng `MPI_Fetch_and_op`, cờ `sense` đọc bằng `MPI_Get` + flush (hoặc so sánh với `MPI_Barrier` làm baseline).
- Chạy thử trên 1 máy (nhiều process) để chứng minh đúng; ghi rõ giới hạn trong report.

---

## 7. Phương pháp đo (áp dụng cho cả 3 phần)

1. **Build bản đo bằng `-O2`**, không sanitizer. Bản test/TSan tách riêng.
2. **Ghim thread** vào core (`pin_thread`). Với CPU Intel lai (P-core/E-core), ghim vào P-core hoặc ghi rõ trong report.
3. **Ổn định máy:** cắm sạc, đóng ứng dụng nền, nếu được: `sudo cpupower frequency-set -g performance`. Ghi nhận máy laptop có thể throttle nhiệt → chạy xen kẽ các thuật toán thay vì chạy hết thuật toán này rồi mới tới thuật toán khác.
4. **Warm-up:** 1 lần chạy bỏ đi trước khi đo. **Lặp ≥ 5 lần**, báo cáo median + độ phân tán.
5. **Oversubscription** (threads > cores): spinlock/barrier thường tệ hẳn → đây là điểm đáng phân tích (vì sao TAS/TTAS/sense-barrier chậm, MCS xếp hàng FIFO nhưng vẫn chịu preemption).
6. **Ghi thông tin máy:** `scripts/sysinfo.sh` lưu `lscpu`, `uname -a`, `g++ --version`, số core vật lý/logic, cache sizes vào `results/<platform>/sysinfo.txt`.
7. Mỗi platform chạy **cùng** `scripts/run_all.sh` → CSV trong `results/<platform>/`.

### Gợi ý `scripts/run_all.sh`

```bash
#!/usr/bin/env bash
set -e
PLAT=${1:?usage: run_all.sh <platform_name>}
OUT=results/$PLAT; mkdir -p $OUT
bash scripts/sysinfo.sh > $OUT/sysinfo.txt
CORES=$(nproc); THREADS="1 2 4 8 $CORES $((2*CORES))"
REPS=5; N=100003; ITERS=20000

echo "algo,threads,iters,outside_work,N,time_ms" > $OUT/lock.csv
for ow in 0 1 4 16; do for t in $THREADS; do
  for a in tas ttas ttas_backoff mcs std_mutex pthread omp; do
    for r in $(seq $REPS); do
      ./build/bench_lock $a $t $ITERS $ow $N >> $OUT/lock.csv
    done; done; done; done
# tương tự cho barrier.csv và counter.csv
```
(Dedupe danh sách thread bằng `sort -nu` nếu `CORES` trùng 8.)

### `scripts/plot.py`
Đọc CSV bằng `pandas`, `groupby(['algo','threads', ...]).median()`, vẽ `matplotlib`, lưu vào `report/figures/`. Mỗi platform một bộ hình.

---

## 8. Cấu trúc báo cáo (PDF)

1. **Giới thiệu & môi trường thí nghiệm** – bảng platform (CPU, số core/thread, cache, RAM, OS, compiler, flags). *Số platform ≥ số thành viên.*
2. **Thiết kế & cài đặt** – mô tả ngắn từng thuật toán, memory order đã chọn và lý do, cache-line alignment, backoff.
3. **Kiểm thử đúng đắn** – các test ở mục 3.4, 4.2, 5.2, kết quả TSan.
4. **Kết quả hiệu năng** – hình + nhận xét cho từng phần, so với baseline (OpenMP / Pthreads / C++).
5. **Phân tích** – ảnh hưởng của contention (OUTSIDE_WORK), số thread, backoff, oversubscription, khác biệt giữa các platform.
6. **Kết luận & phân công công việc** (và phần 4 nếu có).

---

## 9. Thứ tự làm việc đề xuất

1. `common.h` + Makefile + `sysinfo.sh` (nền tảng chung).
2. Lock: TAS → TTAS → test → MCS → backoff → baseline → bench (mục tiêu: chạy được end-to-end sớm).
3. Counter (tái dùng lock, thêm CAS/FAA) – nhanh nhất.
4. Barrier sense-reversing + baseline.
5. `run_all.sh` + `plot.py`; chạy thử trên 1 máy để chỉnh tham số (N, iters, MAX_DELAY).
6. Chạy chính thức trên tất cả platform.
7. (Optional) MPI.
8. Viết report, đóng gói zip.

**Chia việc (2–3 người):** mỗi người một phần chính (lock / barrier / counter), cùng chịu trách nhiệm chạy benchmark trên máy của mình (đây cũng chính là platform của người đó).

---

## 10. Checklist trước khi nộp

- [ ] `make && make test` chạy sạch; `make tsan` không báo race.
- [ ] `is_prime` được bọc `do_not_optimize` (kiểm tra thời gian > 0 và tăng theo N).
- [ ] Mỗi cấu hình đo ≥ 5 lần, dùng median.
- [ ] Có baseline (std/pthread/OpenMP) trong mọi hình so sánh.
- [ ] Số platform ≥ số thành viên; mỗi platform có `sysinfo.txt` + CSV.
- [ ] Report PDF có đủ: môi trường, thiết kế, test, hình, phân tích.
- [ ] Zip chứa: `report.pdf`, `include/`, `src/`, `tests/`, `scripts/`, `Makefile`, `README.md` (+ `results/` CSV nếu dung lượng nhỏ, + `mpi/` nếu làm).
- [ ] Nộp trước **31/10/2026**.
