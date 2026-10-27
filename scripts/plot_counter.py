from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "report" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def main():
    files = list(RESULTS_DIR.glob("*/counter_results.csv"))

    if not files:
        raise FileNotFoundError(
            f"Khong tim thay counter.csv trong {RESULTS_DIR}"
        )

    frames = []

    for file in files:
        df = pd.read_csv(file)
        df.columns = df.columns.str.strip()

        required = {"algorithm", "threads", "time_ms", "correctness"}
        missing = required - set(df.columns)

        if missing:
            raise ValueError(f"{file} thieu cot: {missing}")

        df["algorithm"] = df["algorithm"].str.strip().str.upper()
        df["correctness"] = (
            df["correctness"].astype(str).str.strip().str.upper()
        )
        df["threads"] = pd.to_numeric(df["threads"])
        df["time_ms"] = pd.to_numeric(df["time_ms"])

        frames.append(df)

    data = pd.concat(frames, ignore_index=True)

    # Chi su dung cac lan chay dung
    data = data[data["correctness"] == "PASS"].copy()

    if data.empty:
        raise ValueError("Khong co ket qua PASS.")

    # Trung binh cong cac lan chay va cac may
    avg = (
        data.groupby(["algorithm", "threads"])["time_ms"]
        .mean()
        .unstack("algorithm")
        .sort_index()
    )

    print("\nThoi gian trung binh (ms):")
    print(avg.round(2))

    # Bieu do 1: Execution Time
    ax = avg.plot(marker="o", figsize=(8, 5))
    ax.set_title("Concurrent Counters - Execution Time")
    ax.set_xlabel("Number of Threads")
    ax.set_ylabel("Average Execution Time (ms)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(title="Algorithm")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "counter_time.png", dpi=300)
    plt.close()

    # Bieu do 2: Speedup so voi cau hinh 1 thread
    if 1 not in avg.index:
        raise ValueError("Can co ket qua voi 1 thread.")

    speedup = avg.loc[1] / avg

    ax = speedup.plot(marker="o", figsize=(8, 5))
    ax.set_title("Concurrent Counters - Speedup")
    ax.set_xlabel("Number of Threads")
    ax.set_ylabel("Speedup")
    ax.axhline(1, linestyle="--", alpha=0.5)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(title="Algorithm")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "counter_speedup.png", dpi=300)
    plt.close()

    print("\nDa tao:")
    print(FIGURES_DIR / "counter_time.png")
    print(FIGURES_DIR / "counter_speedup.png")


if __name__ == "__main__":
    main()
