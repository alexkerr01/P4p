"""Experiment Six ocean trial: summary statistics and figures.

Usage:
    python ocean_plots.py ACTIVE.xlsx PASSIVE.xlsx OUT_DIR

ACTIVE.xlsx is read from its first sheet, PASSIVE.xlsx from its first sheet
(the sensor-log sheet). Invalid altitude samples are left as gaps in the
plots rather than drawn at 0 mm.
"""
import math
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import openpyxl

TARGET_MM = 1000
BAND_MM = 500
ATTITUDE_SPEC_DEG = 10

# Towed sections used for attitude statistics (s from log start); they exclude
# the launch and recovery at either end of each log.
TOWED = {"active": (15, 150), "passive": (20, 260)}

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
BAND = "#e8e7e3"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": BAND,
    "grid.linewidth": 0.6,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "legend.frameon": False,
    "savefig.dpi": 300,
})


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def load(path):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    hdr = next(rows)
    out = []
    for r in rows:
        if all(v is None for v in r):
            continue
        d = {}
        for k, v in zip(hdr, r):
            if k is not None and k not in d:
                d[k] = v
        out.append(d)
    t0 = out[0]["device_timestamp_ms"]
    for d in out:
        d["t"] = (d["device_timestamp_ms"] - t0) / 1000
    return out


def series(rows, key, t1=-math.inf, t2=math.inf):
    pts = [(r["t"], num(r.get(key))) for r in rows if t1 <= r["t"] < t2]
    return [t for t, v in pts if v is not None], [v for t, v in pts if v is not None]


def rms(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs))


def report(name, rows):
    n = len(rows)
    err = [r["height_mm"] - TARGET_MM for r in rows
           if r["height_valid"] is True and num(r["height_mm"])]
    inb = [e for e in err if abs(e) <= BAND_MM]
    print(f"== {name}: {n} samples, {rows[-1]['t']:.1f} s")
    print(f"  valid altitude        {len(err) / n * 100:.1f}% of all samples")
    print(f"  in band               {len(inb) / len(err) * 100:.1f}% of valid")
    print(f"  valid and in band     {len(inb) / n * 100:.1f}% of all samples")
    print(f"  RMS error in band     {rms(inb):.1f} mm (mean {st.mean(inb):+.1f}, sd {st.pstdev(inb):.1f})")
    print(f"  RMS error all valid   {rms(err):.1f} mm")
    t1, t2 = TOWED[name]
    for key in ("pitch_deg", "roll_deg"):
        _, xs = series(rows, key, t1, t2)
        print(f"  {key:9s} {t1}-{t2} s  mean {st.mean(xs):+.1f}  sd {st.pstdev(xs):.1f}  RMS {rms(xs):.1f}")


def altitude_with_gaps(rows):
    t, h = [], []
    for r in rows:
        t.append(r["t"])
        ok = r["height_valid"] is True and num(r["height_mm"])
        h.append(r["height_mm"] if ok else math.nan)
    return t, h


def plot_altitude(rows, path, tmax):
    fig, ax = plt.subplots(figsize=(3.4, 2.3), layout="constrained")
    ax.axhspan(TARGET_MM - BAND_MM, TARGET_MM + BAND_MM, color=BAND, lw=0, zorder=0)
    ax.axhline(TARGET_MM, color=MUTED, lw=1, ls="--", zorder=1)
    t, h = altitude_with_gaps(rows)
    ax.plot(t, h, color=BLUE, lw=0.8, zorder=2)
    ax.set_xlim(0, tmax)
    ax.set_ylim(0, 2500)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Estimated altitude (mm)")
    fig.savefig(path)
    plt.close(fig)


def plot_attitude(rows, path, tmax, with_target):
    fig, (ax_p, ax_r) = plt.subplots(2, 1, figsize=(3.4, 3.2), sharex=True,
                                     layout="constrained")
    for ax in (ax_p, ax_r):
        ax.axhspan(-ATTITUDE_SPEC_DEG, ATTITUDE_SPEC_DEG, color=BAND, lw=0, zorder=0)
        ax.axhline(0, color=MUTED, lw=0.6, zorder=1)
        ax.set_ylim(-50, 50)
        ax.set_yticks([-40, -20, 0, 20, 40])
    t, p = series(rows, "pitch_deg")
    ax_p.plot(t, p, color=BLUE, lw=0.8, zorder=2, label="Measured")
    if with_target:
        t, p = series(rows, "target_pitch_deg")
        ax_p.plot(t, p, color=ORANGE, lw=0.8, zorder=3, label="Reference")
        ax_p.legend(loc="upper left", fontsize=7, ncols=2, handlelength=1.5)
    t, r = series(rows, "roll_deg")
    ax_r.plot(t, r, color=BLUE, lw=0.8, zorder=2)
    ax_p.set_ylabel("Pitch (°)")
    ax_r.set_ylabel("Roll (°)")
    ax_r.set_xlabel("Time (s)")
    ax_r.set_xlim(0, tmax)
    fig.savefig(path)
    plt.close(fig)


def main(active_path, passive_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs = {"active": load(active_path), "passive": load(passive_path)}
    for name, rows in runs.items():
        report(name, rows)
        stem = "P4pActive" if name == "active" else "P4pPassive"
        tmax = math.ceil(rows[-1]["t"] / 10) * 10
        plot_altitude(rows, out / f"{stem}Height.png", tmax)
        plot_attitude(rows, out / f"{stem}Pitch.png", tmax, name == "active")


if __name__ == "__main__":
    main(*sys.argv[1:4])
