from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "report" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # 1. Tìm chính xác tất cả file counter_results*.csv nằm trong các thư mục máy
    files = list(RESULTS_DIR.rglob("counter_results*.csv"))

    if not files:
        raise FileNotFoundError(
            f"Không tìm thấy file counter_results*.csv nào trong {RESULTS_DIR}"
        )

    frames = []
    for file in files:
        df = pd.read_csv(file)
        df.columns = df.columns.str.strip()

        # Kiểm tra các cột bắt buộc
        required = {"algorithm", "threads", "time_ms", "correctness"}
        if not required.issubset(set(df.columns)):
            continue

        # Chuẩn hóa dữ liệu
        df["algorithm"] = df["algorithm"].str.strip().str.upper()
        df["correctness"] = df["correctness"].astype(str).str.strip().str.upper()
        df["threads"] = pd.to_numeric(df["threads"]).astype(int)
        df["time_ms"] = pd.to_numeric(df["time_ms"])

        frames.append(df)

    if not frames:
        raise ValueError("Không tìm thấy dữ liệu counter hợp lệ.")

    data = pd.concat(frames, ignore_index=True)

    data = data[data["correctness"] == "PASS"].copy()

    if data.empty:
        raise ValueError("Không có kết quả PASS nào.")

    # 2. Tính thời gian trung bình (ms) của tất cả lần chạy trên cả 3 máy
    avg = (
        data.groupby(["algorithm", "threads"])["time_ms"]
        .mean()
        .unstack("algorithm")
        .sort_index()
    )

    print("\n================ THỜI GIAN TRUNG BÌNH 3 MÁY (ms) ================")
    print(avg.round(2))

    # 3. Tính Speedup: Speedup = T1 / Tp
    if 1 not in avg.index:
        raise ValueError("Cần có kết quả ở 1 thread để tính Speedup.")

    t1_times = avg.loc[1]  # Thời gian chạy 1 thread của từng thuật toán
    speedup = avg.rdiv(t1_times, axis=1)

    print("\n================ SPEEDUP TRUNG BÌNH 3 MÁY ================")
    print(speedup.round(4))

    thread_ticks = avg.index.tolist()

    # --- BIỂU ĐỒ 1: Execution Time ---
    fig, ax = plt.subplots(figsize=(8, 5))
    for col in avg.columns:
        ax.plot(avg.index, avg[col], marker="o", linewidth=1.8, label=col)

    ax.set_title("Concurrent Counters - Average Execution Time", fontsize=12, fontweight="bold")
    ax.set_xlabel("Number of Threads", fontsize=10)
    ax.set_ylabel("Average Execution Time (ms)", fontsize=10)
    ax.set_xticks(thread_ticks)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(title="Algorithm")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "counter_time.png", dpi=300)
    plt.close()

    # --- BIỂU ĐỒ 2: Speedup ---
    fig, ax = plt.subplots(figsize=(8, 5))
    for col in speedup.columns:
        ax.plot(speedup.index, speedup[col], marker="o", linewidth=1.8, label=col)

    # Đường cơ sở Baseline (Speedup = 1)
    ax.axhline(1, color="red", linestyle="--", alpha=0.7, label="Baseline (Speedup = 1)")

    ax.set_title("Concurrent Counters - Average Speedup", fontsize=12, fontweight="bold")
    ax.set_xlabel("Number of Threads", fontsize=10)
    ax.set_ylabel("Speedup (T1 / Tp)", fontsize=10)
    ax.set_xticks(thread_ticks)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.legend(title="Algorithm")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "counter_speedup.png", dpi=300)
    plt.close()

    print("\nĐã vẽ thành công 2 biểu đồ tại:")
    print(f" 1. {FIGURES_DIR / 'counter_time.png'}")
    print(f" 2. {FIGURES_DIR / 'counter_speedup.png'}")


if __name__ == "__main__":
    main()