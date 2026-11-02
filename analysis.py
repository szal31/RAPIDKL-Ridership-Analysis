"""Rapid KL ridership analysis: COVID recovery, line growth, weekday vs weekend, public holidays.

Data: data.gov.my daily ridership (https://storage.data.gov.my/transportation/ridership_headline.csv)
Usage:  python analysis.py      -> prints findings, writes charts to output/
"""
from pathlib import Path

import holidays
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "ridership_headline.csv"
OUT = ROOT / "output"

# Rapid KL rail lines only (KTM Komuter/ETS are a different operator)
LINES = {
    "rail_lrt_kj": "LRT Kelana Jaya",
    "rail_mrt_kajang": "MRT Kajang",
    "rail_lrt_ampang": "LRT Ampang/Sri Petaling",
    "rail_mrt_pjy": "MRT Putrajaya",
    "rail_monorail": "Monorail",
    "rail_lrt_shah_alam": "LRT Shah Alam",
}
LEGACY = ["LRT Kelana Jaya", "MRT Kajang", "LRT Ampang/Sri Petaling", "Monorail"]  # open since 2019
COLORS = dict(zip(LINES.values(), ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]))
INK, MUTED, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"
RECOVERED_FROM = "2023-01-01"  # post-pandemic period used for "normal" patterns


def clean_holiday(name):
    """'Cuti Tahun Baharu Cina (Hari Kedua)' -> 'Tahun Baharu Cina': group replacement and second days."""
    if not name:
        return None
    name = name.split(";")[0].removeprefix("Cuti ").split(" (")[0].strip()
    return HOLIDAY_EN.get(name, name)


HOLIDAY_EN = {
    "Tahun Baharu": "New Year", "Tahun Baharu Cina": "Chinese New Year", "Hari Thaipusam": "Thaipusam",
    "Hari Wilayah Persekutuan": "Federal Territory Day", "Hari Nuzul Al-Quran": "Nuzul Al-Quran",
    "Hari Raya Puasa": "Hari Raya Aidilfitri", "Hari Pekerja": "Labour Day", "Hari Wesak": "Wesak Day",
    "Hari Keputeraan Rasmi Seri Paduka Baginda Yang di-Pertuan Agong": "Agong's Birthday",
    "Hari Raya Qurban": "Hari Raya Haji", "Awal Muharam": "Awal Muharram",
    "Hari Kebangsaan": "National Day", "Hari Malaysia": "Malaysia Day",
    "Hari Keputeraan Nabi Muhammad S.A.W.": "Prophet Muhammad's Birthday",
    "Hari Deepavali": "Deepavali", "Hari Krismas": "Christmas", "Peristiwa": "Special holiday",
}


def load():
    """Daily ridership per Rapid KL rail line, with calendar flags."""
    raw = pd.read_csv(DATA, parse_dates=["date"]).set_index("date")
    df = raw[list(LINES)].rename(columns=LINES)
    # zeros before a line opens are "not running", not "nobody rode"
    for col in df:
        first = df[col][df[col] > 0].first_valid_index()
        df.loc[df.index < first, col] = None
    df["Total rail"] = df[list(LINES.values())].sum(axis=1, min_count=1)
    ph = holidays.country_holidays("MY", subdiv="KUL", years=range(df.index.year.min(), df.index.year.max() + 1))
    df["holiday"] = [clean_holiday(ph.get(d)) for d in df.index.date]
    df["weekend"] = df.index.day_of_week >= 5
    return df


def findings(df):
    f = {}
    yearly = df.groupby(df.index.year)[LEGACY + ["Total rail"]].mean()
    legacy = yearly[LEGACY].sum(axis=1)
    f["legacy_2019"], f["legacy_2021"], f["legacy_2025"] = legacy[2019], legacy[2021], legacy[2025]
    f["total_2025"] = yearly.loc[2025, "Total rail"]

    monthly = df[LEGACY].resample("MS").mean().sum(axis=1)
    f["recovered_month"] = monthly[(monthly.index >= "2021-01-01") & (monthly >= legacy[2019])].index.min()
    f["low_month"] = monthly.idxmin()
    f["low_vs_2019"] = monthly.min() / legacy[2019]

    recent = df[df.index >= RECOVERED_FROM]
    normal = recent[recent["holiday"].isna()]
    lines = [c for c in LINES.values() if c != "LRT Shah Alam"]  # too new for stable patterns
    wkday = normal[~normal["weekend"]][lines].mean()
    wkend = normal[normal["weekend"]][lines].mean()
    f["weekend_ratio"] = (wkend / wkday).sort_values()

    # holiday effect: weekday holidays vs normal weekdays in the same month
    wk = recent[~recent["weekend"]]
    base = wk[wk["holiday"].isna()].groupby(wk[wk["holiday"].isna()].index.to_period("M"))["Total rail"].mean()
    hol = wk[wk["holiday"].notna()].copy()
    hol["vs_normal"] = hol["Total rail"].values / base.reindex(hol.index.to_period("M")).values - 1
    f["holiday_effect"] = hol.groupby("holiday")["vs_normal"].mean().sort_values()

    peak = df["Total rail"].idxmax()
    f["peak_day"], f["peak_value"] = peak, df.loc[peak, "Total rail"]
    f["busiest_2025"] = yearly.loc[2025, LEGACY].idxmax()
    f["mrt_pjy_2025"] = df[df.index.year == 2025]["MRT Putrajaya"].mean()
    return f


def style(ax, title):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def new_fig(w=9, h=4.2):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, facecolor=SURFACE)
    plt.close(fig)


def thousands(ax):
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k"))


def charts(df, f):
    OUT.mkdir(exist_ok=True)

    # 1. recovery: legacy lines vs 2019 level
    m = df[LEGACY].resample("MS").mean().sum(axis=1)
    fig, ax = new_fig()
    style(ax, "Rapid KL rail recovered past 2019 levels (4 original lines, avg daily riders)")
    ax.plot(m.index, m.values, color=COLORS["LRT Kelana Jaya"], linewidth=2)
    ax.axhline(f["legacy_2019"], color=MUTED, linewidth=1, linestyle="--")
    ax.text(m.index[-1], f["legacy_2019"] * 0.95, "2019 average", color=MUTED, fontsize=8, ha="right", va="top")
    ax.annotate(f"Lockdown low: {f['low_vs_2019']:.0%} of 2019 ({f['low_month']:%b %Y})", (f["low_month"], m.min()),
                xytext=(f["low_month"] + pd.Timedelta(days=60), 12000), fontsize=8, color=INK, va="center",
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    thousands(ax)
    save(fig, "1_recovery.png")

    # 2. each line, monthly avg daily riders, direct-labelled
    lm = df[list(LINES.values())].resample("MS").mean()
    fig, ax = new_fig(9, 4.8)
    style(ax, "MRT Kajang is now the busiest line; MRT Putrajaya grew fastest")
    for line in LINES.values():
        s = lm[line].dropna()
        ax.plot(s.index, s.values, color=COLORS[line], linewidth=2)
    ends = sorted(((lm[l].dropna().iloc[-1], l) for l in LINES.values()), reverse=True)
    last_y = None
    for y, line in ends:  # nudge labels apart so they never overlap
        y_txt = y if last_y is None else min(y, last_y - 14000)
        ax.text(lm.index[-1] + pd.Timedelta(days=20), y_txt, line, color=INK, fontsize=8, va="center")
        ax.plot([lm.index[-1] + pd.Timedelta(days=5)], [y], "o", color=COLORS[line], markersize=4)
        last_y = y_txt
    ax.set_xlim(lm.index[0], lm.index[-1] + pd.Timedelta(days=600))
    ax.set_xticks([pd.Timestamp(f"{y}-01-01") for y in range(lm.index[0].year, lm.index[-1].year + 1)])
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%Y"))
    ax.spines["bottom"].set_bounds(*plt.matplotlib.dates.date2num([lm.index[0], lm.index[-1]]))
    thousands(ax)
    save(fig, "2_lines.png")

    # 3. weekend riders as % of weekday
    r = f["weekend_ratio"]
    fig, ax = new_fig(8, 3.6)
    style(ax, "Weekend ridership as % of a normal weekday (2023 onwards)")
    bars = ax.barh(r.index, r.values * 100, color=COLORS["LRT Kelana Jaya"], height=0.6)
    for b, v in zip(bars, r.values):
        ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2, f"{v:.0%}", va="center", fontsize=8, color=MUTED)
    ax.grid(False)
    ax.xaxis.set_visible(False)
    save(fig, "3_weekend.png")

    # 4. public holiday effect on total rail
    h = f["holiday_effect"]
    fig, ax = new_fig(8, 0.35 * len(h) + 1.2)
    style(ax, "Rail riders on weekday public holidays vs a normal weekday (2023+)")
    bars = ax.barh(h.index, h.values * 100, color=COLORS["LRT Kelana Jaya"], height=0.6)
    for b, v in zip(bars, h.values):
        x = b.get_width()
        ax.text(x + (1 if x >= 0 else -1), b.get_y() + b.get_height() / 2, f"{v:+.0%}",
                va="center", ha="left" if x >= 0 else "right", fontsize=8, color=MUTED)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.set_xlim(min(h.min() * 100 * 1.25, -5), max(h.max() * 100 * 1.4, 10))
    ax.grid(False)
    ax.xaxis.set_visible(False)
    save(fig, "4_holidays.png")


def main():
    df = load()
    f = findings(df)

    # Self-checks: expected date coverage, totals equal sum of lines, ratios are sensible.
    assert df.index.is_unique and df.index.to_series().diff().max() == pd.Timedelta(days=1)
    assert (df["Total rail"] - df[list(LINES.values())].sum(axis=1)).abs().max() < 1
    assert f["weekend_ratio"].between(0.2, 1.5).all()
    assert f["low_vs_2019"] < 0.5  # 2021 lockdown must show as a deep trough

    charts(df, f)
    print(f"Data: {df.index.min():%d %b %Y} to {df.index.max():%d %b %Y}\n")
    print(f"4 original lines, avg daily riders: 2019 {f['legacy_2019']:,.0f} | 2021 {f['legacy_2021']:,.0f} "
          f"| 2025 {f['legacy_2025']:,.0f} ({f['legacy_2025'] / f['legacy_2019']:.0%} of 2019)")
    print(f"Lowest month: {f['low_month']:%b %Y} at {f['low_vs_2019']:.0%} of 2019")
    print(f"First month back above 2019 average: {f['recovered_month']:%b %Y}")
    print(f"All Rapid KL rail, 2025 avg daily: {f['total_2025']:,.0f}")
    print(f"MRT Putrajaya 2025 avg daily: {f['mrt_pjy_2025']:,.0f}")
    print(f"Busiest original line in 2025: {f['busiest_2025']}")
    print(f"Record day: {f['peak_day']:%a %d %b %Y} with {f['peak_value']:,.0f} rail riders\n")
    print("Weekend as % of weekday:")
    print(f["weekend_ratio"].map("{:.0%}".format).to_string(), "\n")
    print("Weekday holiday vs normal weekday:")
    print(f["holiday_effect"].map("{:+.0%}".format).to_string())


if __name__ == "__main__":
    main()
