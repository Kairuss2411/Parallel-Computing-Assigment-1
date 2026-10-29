#!/usr/bin/env python3
"""Part 1 (mutex locks) plots: CSV -> report/figures/<platform>/*.png.

Every platform under results/<platform>/ is plotted separately. Rows are never
merged across machines, because CPU model, core count, clock/turbo behaviour,
compiler and virtualisation differ and would make the comparison unfair.
Each figure is therefore the median over the repetitions of a single machine.

Output layout:

    report/figures/<platform-slug>/lock_time.png
    report/figures/<platform-slug>/lock_perop.png
    report/figures/<platform-slug>/lock_contention_t<T>.png
    report/figures/<platform-slug>/lock_backoff.png
    report/figures/<platform-slug>/lock_backoff_compare.png
    report/figures/<platform-slug>/lock_oversub.png        (if data exists)

Reads (from each selected platform folder):
    lock.csv           main sweep, required
    lock_backoff.csv   MAX_DELAY tuning, optional
    lock_oversub.csv   threads > cores, optional

Usage: python3 scripts/plot_lock.py [platform ...]
       (no argument = plot every platform that has a lock.csv)
"""
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RES_ROOT = "results"
FIG = os.path.join("report", "figures")

ALL_PLATFORMS = sorted(
    os.path.basename(d)
    for d in glob.glob(os.path.join(RES_ROOT, "*"))
    if os.path.isdir(d) and os.path.exists(os.path.join(d, "lock.csv"))
)
if not ALL_PLATFORMS:
    sys.exit(f"error: no platform data under {RES_ROOT}/*/lock.csv\n"
             f"       run scripts/run_lock.sh <platform> first")

if len(sys.argv) > 1:
    PLATFORMS = [p.strip() for p in sys.argv[1:] if p.strip()]
    missing = [p for p in PLATFORMS if p not in ALL_PLATFORMS]
    if missing:
        sys.exit(f"error: no data for platform(s): {', '.join(missing)}\n"
                 f"       available: {', '.join(ALL_PLATFORMS)}")
else:
    PLATFORMS = ALL_PLATFORMS

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


def slug(platform):
    """Folder-safe name for a platform, e.g. 'gold 4 cores' -> 'gold_4_cores'."""
    return platform.lower().replace(" ", "_")


def load(platform, fname):
    """Read one CSV of a single platform; None when the file does not exist."""
    path = os.path.join(RES_ROOT, platform, fname)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["platform"] = platform
    return df


def warn_duplicates(df, platform, fname):
    """Appending sweeps without --force duplicates (algo,threads,ow,rep) rows."""
    keys = [c for c in ("algo", "threads", "outside_work", "max_delay", "rep")
            if c in df.columns]
    dup = int(df.duplicated(keys).sum())
    if dup:
        print(f"warning: {platform}/{fname}: {dup} duplicated row(s) "
              f"(multiple sweeps appended?); medians mix those sessions",
              file=sys.stderr)


def save(fig, outdir, name):
    path = os.path.join(outdir, name)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def main_sweep(platform, outdir):
    """time vs threads (+ per-op cost) for every OUTSIDE_WORK value."""
    df = load(platform, "lock.csv")
    if df is None:
        return
    warn_duplicates(df, platform, "lock.csv")
    df = df[df.outside_work.isin(OW_KEEP)].copy()
    if df.empty:
        return
    df["per_op_us"] = df.time_ms * 1000.0 / (df.threads * df.iters)
    g = (df.groupby(["algo", "threads", "outside_work"])
           .agg(time_ms=("time_ms", "median"),
                per_op_us=("per_op_us", "median"))
           .reset_index())
    iters = int(df.iters.max())
    nprime = int(df.N.max())
    ows = sorted(df.outside_work.unique())

    def panel_grid(metric, ylabel, title):
        fig, axes = plt.subplots(1, len(ows), figsize=(5.4 * len(ows), 4.5),
                                 squeeze=False)
        axes = axes[0]
        for ax, ow in zip(axes, ows):
            sub = g[g.outside_work == ow]
            for algo in ORDER:
                d = sub[sub.algo == algo].sort_values("threads")
                if d.empty:
                    continue
                ax.plot(d.threads, d[metric], linewidth=1.8, markersize=5,
                        label=algo, **STYLE[algo])
            ax.set_xlabel("Số thread")
            ax.set_ylabel(ylabel)
            ax.set_title(f"OUTSIDE_WORK = {ow}")
            ax.set_xticks(sorted(sub.threads.unique()))
            ax.grid(True, alpha=0.3)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.suptitle(title)
        fig.tight_layout(rect=(0, 0.11, 1, 0.93))
        fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
                   frameon=False)
        return fig

    save(panel_grid(
        "time_ms", "Thời gian chạy cả chương trình (ms)",
        f"Part 1 – Lock ({platform}): thời gian chạy "
        f"(iters={iters}, N={nprime})"),
        outdir, "lock_time.png")

    save(panel_grid(
        "per_op_us", "Thời gian trung bình mỗi thao tác CS (µs)",
        f"Part 1 – Lock ({platform}): chi phí mỗi thao tác "
        f"(iters={iters}, N={nprime})"),
        outdir, "lock_perop.png")

    # Summary figure: largest thread count, all OUTSIDE_WORK values
    tmax = int(df.threads.max())
    sub = g[(g.threads == tmax) & (g.algo.isin(ORDER))]
    pivot = sub.pivot(index="algo", columns="outside_work", values="time_ms")
    pivot = pivot.reindex([a for a in ORDER if a in pivot.index])
    ax = pivot.plot(kind="bar", figsize=(9, 4.5), width=0.8)
    ax.set_xlabel("Thuật toán")
    ax.set_ylabel("Thời gian (ms, median)")
    ax.set_title(f"Part 1 – Ảnh hưởng của contention "
                 f"({platform}, T={tmax} thread, N={nprime})")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(title="OUTSIDE_WORK", fontsize=8)
    plt.xticks(rotation=25, ha="right")
    save(ax.figure, outdir, f"lock_contention_t{tmax}.png")


def backoff_sweep(platform, outdir):
    """MAX_DELAY curves for both backoff variants, OUTSIDE_WORK = 0 only."""
    df = load(platform, "lock_backoff.csv")
    if df is None:
        return
    warn_duplicates(df, platform, "lock_backoff.csv")
    df = df[(df.outside_work == 0)
            & (df.algo.isin(["ttas_backoff", "ttas_backoff_sleep"]))]
    if df.empty:
        return
    g = (df.groupby(["algo", "threads", "max_delay"])["time_ms"]
           .median().reset_index())

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.5), squeeze=False)
    axes = axes[0]
    for ax, (algo, unit) in zip(
            axes, (("ttas_backoff", "pause count"),
                   ("ttas_backoff_sleep", "ns"))):
        d = g[g.algo == algo]
        if d.empty:
            ax.set_visible(False)
            continue
        for t, dd in d.groupby("threads"):
            dd = dd.sort_values("max_delay")
            ax.plot(dd.max_delay, dd.time_ms, marker="o", linewidth=1.8,
                    label=f"T={t}")
        ax.set_xscale("log", base=2)
        ax.set_xlabel(f"MAX_DELAY ({unit}, log scale)")
        ax.set_ylabel("Thời gian (ms, median)")
        ax.set_title(algo)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, title="threads")
    fig.suptitle(f"Part 1 – Tinh chỉnh backoff ({platform}), "
                 f"OUTSIDE_WORK = 0")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, outdir, "lock_backoff.png")


def backoff_compare(platform, outdir, ow=0):
    """TTAS vs TTAS+backoff(pause) vs TTAS+backoff(sleep) at OUTSIDE_WORK=0.

    'ttas' baseline comes from lock.csv (built-in settings); the two backoff
    variants come from lock_backoff.csv (one line per MAX_DELAY value).
    """
    main = load(platform, "lock.csv")
    bf = load(platform, "lock_backoff.csv")
    if main is None or bf is None:
        return
    main = main[main.outside_work == ow].copy()
    base = (main[main.algo == "ttas"]
            .groupby("threads")["time_ms"].median().reset_index())
    if base.empty:
        return
    nprime = int(main.N.max())

    bf = bf[(bf.outside_work == ow)
            & (bf.algo.isin(["ttas_backoff", "ttas_backoff_sleep"]))].copy()
    if bf.empty:
        return
    bf["per_op_us"] = bf.time_ms * 1000.0 / (bf.threads * bf.iters)
    med = (bf.groupby(["algo", "threads", "max_delay"])
             .agg(time_ms=("time_ms", "median"),
                  per_op_us=("per_op_us", "median"))
             .reset_index())
    iters = int(main.iters.max())

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8))

    def draw(a, metric):
        """metric='time_ms' -> ms cả chương trình; 'per_op_us' -> µs mỗi thao tác."""
        a.plot(base.threads, base.time_ms if metric == "time_ms"
               else base.time_ms * 1000.0 / (base.threads * iters),
               color="black", linewidth=2.6, marker="s", markersize=6,
               label="ttas (không backoff)")
        for algo, color, ls, unit in (
                ("ttas_backoff", "#2ca02c", "-", "pause"),
                ("ttas_backoff_sleep", "#8c564b", "--", "ns")):
            d = med[med.algo == algo]
            delays = sorted(d.max_delay.unique())
            for i, delay in enumerate(delays):
                dd = d[d.max_delay == delay].sort_values("threads")
                if dd.empty:
                    continue
                a.plot(dd.threads, dd[metric], color=color, linestyle=ls,
                       marker="o", markersize=5, linewidth=1.5,
                       alpha=0.45 + 0.55 * (i / max(1, len(delays) - 1)),
                       label=f"{algo} (MAX_DELAY={delay} {unit})")

    draw(ax, "time_ms")
    ax.set_xlabel("Số thread")
    ax.set_ylabel("Thời gian chạy cả chương trình (ms, median)")
    ax.set_title(f"OUTSIDE_WORK = {ow}: thời gian tổng")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(sorted(base.threads.unique()))

    draw(ax2, "per_op_us")
    ax2.set_xlabel("Số thread")
    ax2.set_ylabel("Thời gian mỗi thao tác CS (µs, median)")
    ax2.set_title(f"OUTSIDE_WORK = {ow}: chi phí mỗi thao tác "
                  f"(iters={iters})")
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(sorted(base.threads.unique()))

    fig.suptitle(f"Part 1 – TTAS vs TTAS+backoff vs TTAS+backoff(sleep) "
                 f"({platform}), N={nprime}")
    handles, labels = ax.get_legend_handles_labels()
    fig.subplots_adjust(top=0.80, bottom=0.28, wspace=0.22)
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.01))
    save(fig, outdir, "lock_backoff_compare.png")


def oversub(platform, outdir):
    df = load(platform, "lock_oversub.csv")
    if df is None:
        return
    df = df[df.outside_work.isin(OW_KEEP)].copy()
    if df.empty:
        return
    df["ops_per_sec"] = df.threads * df.iters * 1000.0 / df.time_ms
    med = (df.groupby(["algo", "threads", "outside_work"])["ops_per_sec"]
             .median().reset_index())
    tmax = int(med.threads.max())
    ows = sorted(med.outside_work.unique())

    fig, axes = plt.subplots(1, len(ows), figsize=(5.6 * len(ows), 4.3),
                             squeeze=False)
    axes = axes[0]
    for ax, ow in zip(axes, ows):
        sub = med[(med.outside_work == ow) & (med.threads == tmax)]
        xs = [a for a in ORDER if a in set(sub.algo)]
        vals = [sub[sub.algo == a].ops_per_sec.iloc[0]
                if not sub[sub.algo == a].empty else 0 for a in xs]
        ax.bar(xs, vals, color=[STYLE[a]["color"] for a in xs])
        ax.set_ylabel("Thông lượng (CS ops/giây)")
        ax.set_title(f"OUTSIDE_WORK = {ow}")
        ax.grid(True, axis="y", alpha=0.3)
        ax.tick_params(axis="x", rotation=25)
    fig.suptitle(f"Part 1 – Oversubscription ({platform}, T={tmax})")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, outdir, "lock_oversub.png")


if __name__ == "__main__":
    for platform in PLATFORMS:
        outdir = os.path.join(FIG, slug(platform))
        os.makedirs(outdir, exist_ok=True)
        print(f"== {platform} -> {outdir}")
        main_sweep(platform, outdir)      # lock.csv: time + per-op
        backoff_sweep(platform, outdir)   # MAX_DELAY tuning, OW=0 only
        backoff_compare(platform, outdir)  # ttas vs both backoff variants
        oversub(platform, outdir)         # optional
