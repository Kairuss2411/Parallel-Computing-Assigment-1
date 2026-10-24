#!/usr/bin/env python3
"""Part 1 (mutex locks) plots: CSV -> report/figures/*.png.

Usage: python3 scripts/plot_lock.py <platform>
Reads  results/<platform>/lock.csv (main sweep, median over reps)
       results/<platform>/lock_nscan.csv (N=100003 sensitivity, optional)
       results/<platform>/lock_backoff.csv (MAX_DELAY tuning, optional)
       results/<platform>/lock_oversub.csv (threads > cores, optional)
"""
import os
import sys

USAGE = "usage: python3 scripts/plot_lock.py <platform>   (e.g. i7-1265U)"

# The platform name is mandatory: never plot an implicit/default machine.
if len(sys.argv) < 2 or not sys.argv[1].strip():
    sys.exit(f"error: platform name required\n{USAGE}")

PLAT = sys.argv[1].strip()
RES = os.path.join("results", PLAT)
if not os.path.isdir(RES):
    sys.exit(f"error: no data folder for platform '{PLAT}': {RES}\n"
             f"{USAGE}\n       run scripts/run_lock.sh {PLAT} first")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

FIG = os.path.join("report", "figures")
os.makedirs(FIG, exist_ok=True)

ORDER = ["tas", "ttas", "ttas_backoff", "ttas_backoff_sleep", "mcs",
         "std_mutex", "pthread", "omp"]
# OUTSIDE_WORK values of the current sweep; the old 16 (measured before the
# sweep was trimmed to 0/1/4) is ignored, never plotted.
OW_KEEP = (0, 1, 4)
STYLE = {
    "tas":                 dict(color="#d62728", marker="o"),
    "ttas":                dict(color="#ff7f0e", marker="s"),
    "ttas_backoff":        dict(color="#2ca02c", marker="^"),
    "ttas_backoff_sleep":  dict(color="#8c564b", marker="v"),
    "mcs":                 dict(color="#1f77b4", marker="D"),
    "std_mutex":           dict(color="#9467bd", marker="x", linestyle="--"),
    "pthread":             dict(color="#7f7f7f", marker="+", linestyle="--"),
    "omp":                 dict(color="#e377c2", marker="*", linestyle="--"),
}


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def main_sweep(fname="lock.csv", tag=""):
    """time vs threads (+ per-op cost) for every OUTSIDE_WORK value in `fname`."""
    path = os.path.join(RES, fname)
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    df = df[df.outside_work.isin(OW_KEEP)]
    if df.empty:
        return
    g = (df.groupby(["algo", "threads", "iters", "outside_work"])["time_ms"]
           .median().reset_index())
    iters = int(df.iters.max())
    nprime = int(df.N.max())
    for ow in sorted(df.outside_work.unique()):
        sub = g[g.outside_work == ow]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for algo in ORDER:
            d = sub[sub.algo == algo].sort_values("threads")
            if d.empty:
                continue
            ax.plot(d.threads, d.time_ms, linewidth=1.8, markersize=5,
                    label=algo, **STYLE[algo])
        ax.set_xlabel("Số thread")
        ax.set_ylabel("Thời gian chạy cả chương trình (ms)")
        ax.set_title(f"Part 1 – Lock: OUTSIDE_WORK = {ow} "
                     f"(iters={iters}, N={nprime}, median)")
        ax.set_xticks(sorted(sub.threads.unique()))
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        save(fig, f"lock_time{tag}_ow{ow}.png")

        # Normalised: time per critical-section op (us) = time_ms*1000/(T*iters)
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for algo in ORDER:
            d = sub[sub.algo == algo].sort_values("threads")
            if d.empty:
                continue
            per_op = d.time_ms * 1000.0 / (d.threads * d.iters)
            ax.plot(d.threads, per_op, linewidth=1.8, markersize=5,
                    label=algo, **STYLE[algo])
        ax.set_xlabel("Số thread")
        ax.set_ylabel("Thời gian trung bình mỗi thao tác CS (µs)")
        ax.set_title(f"Part 1 – Lock: chi phí mỗi thao tác, OUTSIDE_WORK = {ow}"
                     f" (N={nprime})")
        ax.set_xticks(sorted(sub.threads.unique()))
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        save(fig, f"lock_perop{tag}_ow{ow}.png")

    # Summary figure: largest thread count, all OUTSIDE_WORK values
    tmax = int(df.threads.max())
    sub = g[(g.threads == tmax) & (g.algo.isin(ORDER))]
    pivot = sub.pivot(index="algo", columns="outside_work", values="time_ms")
    pivot = pivot.reindex([a for a in ORDER if a in pivot.index])
    ax = pivot.plot(kind="bar", figsize=(9, 4.5), width=0.8)
    ax.set_xlabel("Thuật toán")
    ax.set_ylabel("Thời gian (ms, median)")
    ax.set_title(f"Part 1 – Ảnh hưởng của contention (T={tmax} thread, "
                 f"N={nprime})")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(title="OUTSIDE_WORK", fontsize=8)
    plt.xticks(rotation=25, ha="right")
    save(ax.figure, f"lock_contention{tag}_t{tmax}.png")


def backoff_sweep():
    path = os.path.join(RES, "lock_backoff.csv")
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    g = (df.groupby(["algo", "threads", "outside_work", "max_delay"])["time_ms"]
           .median().reset_index())
    for algo, unit in (("ttas_backoff", "pause count"),
                       ("ttas_backoff_sleep", "ns")):
        d = g[g.algo == algo]
        if d.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, 4.3))
        for (t, ow), dd in d.groupby(["threads", "outside_work"]):
            dd = dd.sort_values("max_delay")
            ax.plot(dd.max_delay, dd.time_ms, marker="o", linewidth=1.8,
                    label=f"T={t}, OW={ow}")
            ax.set_xscale("log", base=2)
        ax.set_xlabel(f"MAX_DELAY ({unit}, log scale)")
        ax.set_ylabel("Thời gian (ms, median)")
        ax.set_title(f"Part 1 – Tinh chỉnh backoff: {algo}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        save(fig, f"lock_backoff_{algo}.png")


def backoff_compare(ow=0):
    """TTAS vs TTAS+backoff(pause) vs TTAS+backoff(sleep) at one OUTSIDE_WORK.

    'ttas' baseline comes from lock.csv (built-in settings); the two backoff
    variants come from lock_backoff.csv (one line per MAX_DELAY value).
    """
    main_path = os.path.join(RES, "lock.csv")
    bf_path = os.path.join(RES, "lock_backoff.csv")
    if not (os.path.exists(main_path) and os.path.exists(bf_path)):
        return
    main = pd.read_csv(main_path)
    main = main[main.outside_work.isin(OW_KEEP)]
    base = (main[(main.algo == "ttas") & (main.outside_work == ow)]
            .groupby("threads")["time_ms"].median().reset_index())
    if base.empty:
        return
    nprime = int(main.N.max())

    bf = pd.read_csv(bf_path)
    bf = bf[(bf.outside_work == ow)
            & (bf.algo.isin(["ttas_backoff", "ttas_backoff_sleep"]))]
    if bf.empty:
        return
    med = (bf.groupby(["algo", "threads", "max_delay"])["time_ms"]
             .median().reset_index())
    iters = int(main.iters.max())

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8))

    def draw(a, scale_per_op):
        """scale_per_op=False -> ms cả chương trình; True -> µs mỗi thao tác."""
        def y_of(d):
            if scale_per_op:
                return d.time_ms * 1000.0 / (d.threads * iters)
            return d.time_ms

        a.plot(base.threads, y_of(base), color="black", linewidth=2.6,
               marker="s", markersize=6, label="ttas (không backoff)")
        for algo, color, ls, unit in (
                ("ttas_backoff", "#2ca02c", "-", "pause"),
                ("ttas_backoff_sleep", "#8c564b", "--", "ns")):
            d = med[med.algo == algo]
            delays = sorted(d.max_delay.unique())
            for i, delay in enumerate(delays):
                dd = d[d.max_delay == delay].sort_values("threads")
                if dd.empty:
                    continue
                a.plot(dd.threads, y_of(dd), color=color, linestyle=ls,
                       marker="o", markersize=5, linewidth=1.5,
                       alpha=0.45 + 0.55 * (i / max(1, len(delays) - 1)),
                       label=f"{algo} (MAX_DELAY={delay} {unit})")

    draw(ax, False)
    ax.set_xlabel("Số thread")
    ax.set_ylabel("Thời gian chạy cả chương trình (ms, median)")
    ax.set_title(f"OUTSIDE_WORK = {ow}: thời gian tổng")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(sorted(base.threads.unique()))

    draw(ax2, True)
    ax2.set_xlabel("Số thread")
    ax2.set_ylabel("Thời gian mỗi thao tác CS (µs, median)")
    ax2.set_title(f"OUTSIDE_WORK = {ow}: chi phí mỗi thao tác "
                  f"(iters={iters})")
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(sorted(base.threads.unique()))

    fig.suptitle(f"Part 1 – TTAS vs TTAS+backoff vs TTAS+backoff(sleep), "
                 f"N={nprime}")
    handles, labels = ax.get_legend_handles_labels()
    fig.subplots_adjust(top=0.80, bottom=0.28, wspace=0.22)
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.01))
    save(fig, f"lock_backoff_compare_ow{ow}.png")


def oversub():
    path = os.path.join(RES, "lock_oversub.csv")
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    g = df.copy()
    g["ops_per_sec"] = g.threads * g.iters * 1000.0 / g.time_ms
    med = g.groupby(["algo", "threads", "outside_work"])["ops_per_sec"].median().reset_index()
    for ow in sorted(med.outside_work.unique()):
        sub = med[med.outside_work == ow]
        fig, ax = plt.subplots(figsize=(7, 4.3))
        xs = [a for a in ORDER if a in set(sub.algo)]
        vals = [sub[sub.algo == a].ops_per_sec.iloc[0] if not sub[sub.algo == a].empty else 0
                for a in xs]
        ax.bar(xs, vals, color=[STYLE[a]["color"] for a in xs])
        ax.set_ylabel("Thông lượng (CS ops/giây)")
        ax.set_title(f"Part 1 – Oversubscription (T=24, 12 core), OW={ow}")
        ax.grid(True, axis="y", alpha=0.3)
        plt.xticks(rotation=25, ha="right")
        save(fig, f"lock_oversub_ow{ow}.png")


if __name__ == "__main__":
    main_sweep()                            # lock.csv           (N = 10007)
    main_sweep("lock_nscan.csv", "_n100003")  # N sensitivity    (N = 100003)
    backoff_sweep()                         # per-algorithm MAX_DELAY curves
    backoff_compare(0)                      # ttas vs both backoff variants, OW=0
    oversub()
