"""Interactive Rapid KL ridership explorer.

Usage:  streamlit run app.py
"""
import altair as alt
import pandas as pd
import streamlit as st

from analysis import COLORS, LEGACY, LINES, findings, load

NAVY, AMBER, MUTED = "#1E40AF", "#D97706", "#475569"
REPO = "https://github.com/szal31/RAPIDKL-Ridership-Analysis"

st.set_page_config(page_title="Rapid KL Ridership", page_icon=":material/train:", layout="wide")


@st.cache_data
def data():
    df = load()
    return df, findings(df)


df, f = data()
all_lines = list(LINES.values())
last = df.index.max()

# ---------- header + headline findings (fixed, whole dataset) ----------
st.title("Rapid KL rail ridership")
st.markdown(f"How Klang Valley rail recovered from COVID, which lines carry the city, and how weekends and "
            f"public holidays change demand. Daily data, Jan 2019 to {last:%d %b %Y}.")

st.subheader("Key findings, 2019 to today", divider="gray")
k1, k2, k3 = st.columns(3)
k1.metric("2025 riders vs 2019", f"{f['legacy_2025'] / f['legacy_2019']:.0%}",
          f"back above 2019 since {f['recovered_month']:%b %Y}", delta_color="off", delta_arrow="off", border=True,
          help="Average daily riders on the 4 lines open since 2019.")
k2.metric("Busiest line in 2025", f["busiest_2025"], "overtook LRT Kelana Jaya", delta_color="off", delta_arrow="off", border=True)
hol = f["holiday_effect"]
k3.metric("Weekday public holiday", f"{hol.median():+.0%} riders",
          f"range {hol.min():+.0%} to {hol.max():+.0%}", delta_color="off", delta_arrow="off", border=True,
          help="Compared with a normal weekday in the same month, 2023 onwards.")

# ---------- filters: one row above the charts ----------
st.subheader("Explore", divider="gray")
lines = st.multiselect("Lines", all_lines, default=all_lines)
fc2, fc3 = st.columns([1.2, 1])
period = fc2.segmented_control("Period", ["Last 12 months", "Since 2023", "All", "Custom"], default="Since 2023")
grain = fc3.segmented_control("Show as", ["Daily", "Weekly", "Monthly"], default="Monthly")

starts = {"Last 12 months": last - pd.DateOffset(years=1), "Since 2023": pd.Timestamp("2023-01-01"),
          "All": df.index.min()}
if period == "Custom":
    picked = st.date_input("Date range", (pd.Timestamp("2023-01-01"), last),
                           min_value=df.index.min(), max_value=last)
    start, end = (picked[0], picked[-1]) if picked else (df.index.min(), last)
else:
    start, end = starts.get(period, starts["Since 2023"]), last

if not lines:
    st.warning("Pick at least one line to see the charts.")
    st.stop()

view = df.loc[str(start):str(end)]
total = view[lines].sum(axis=1, min_count=1)

m1, m2, m3 = st.columns(3)
m1.metric("Avg daily riders (selection)", f"{total.mean():,.0f}", border=True,
          chart_data=total.resample("MS").mean().dropna(), chart_type="area")
m2.metric("Busiest day", f"{total.max():,.0f}", f"{total.idxmax():%a %d %b %Y}", delta_color="off", delta_arrow="off", border=True)
legacy = [l for l in lines if l in LEGACY]
if legacy:
    base = df.loc["2019", legacy].sum(axis=1).mean()
    m3.metric("Original lines vs 2019", f"{view[legacy].sum(axis=1).mean() / base:.0%}", border=True,
              help="Average daily riders on the selected pre-2020 lines, compared with their 2019 average.")
else:
    m3.metric("Original lines vs 2019", "n/a", border=True, help="Select a line that ran in 2019.")

rule = {"Daily": None, "Weekly": "W", "Monthly": "MS"}.get(grain)
series = view[lines] if rule is None else view[lines].resample(rule).mean()
series.index.name = "date"

trend, dow_tab, hol_tab, table_tab = st.tabs(["Trend", "Day of week", "Public holidays", "Data table"])

with trend:
    long = series.reset_index().melt("date", var_name="Line", value_name="Riders")
    color = alt.Color("Line:N", scale=alt.Scale(domain=lines, range=[COLORS[l] for l in lines]),
                      legend=alt.Legend(orient="top", title=None, columns=3, labelFontSize=12))
    hover = alt.selection_point(fields=["date"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    line_layer = alt.Chart(long).mark_line(strokeWidth=2).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("Riders:Q", title="Riders per day", axis=alt.Axis(format="~s")), color=color)
    crosshair = alt.Chart(series.reset_index()).mark_rule(color="#94A3B8").encode(
        x="date:T", opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("date:T", title="Date", format="%d %b %Y")]
        + [alt.Tooltip(f"{l}:Q", format=",.0f") for l in lines]).add_params(hover)
    st.altair_chart((line_layer + crosshair).properties(height=380), use_container_width=True)
    st.caption("Hover for exact values. Average riders per day for the chosen grain.")

with dow_tab:
    normal = view[view["holiday"].isna()]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = (normal[lines].groupby(normal.index.day_name()).mean().reindex(days).sum(axis=1)
           .rename("Riders").rename_axis("Day").reset_index())
    dow["Type"] = ["Weekday"] * 5 + ["Weekend"] * 2
    bars = alt.Chart(dow).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Day:N", sort=None, title=None),
        x=alt.X("Riders:Q", title="Average riders per day", axis=alt.Axis(format="~s")),
        color=alt.Color("Type:N", scale=alt.Scale(domain=["Weekday", "Weekend"], range=[NAVY, AMBER]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["Day", alt.Tooltip("Riders:Q", format=",.0f")])
    labels = bars.mark_text(align="left", dx=4, color=MUTED).encode(text=alt.Text("Riders:Q", format=",.0f"))
    st.altair_chart((bars + labels).properties(height=300), use_container_width=True)
    wkend = dow.loc[dow.Type == "Weekend", "Riders"].mean() / dow.loc[dow.Type == "Weekday", "Riders"].mean()
    st.caption(f"Weekends carry {wkend:.0%} of weekday riders for the selected lines (public holidays excluded).")

with hol_tab:
    wk = view[~view["weekend"]]
    plain = wk[wk["holiday"].isna()]
    usual = plain.groupby(plain.index.to_period("M"))[lines].mean().sum(axis=1)
    hd = wk[wk["holiday"].notna()]
    if hd.empty:
        st.info("No weekday public holidays in this date range. Try a longer period.")
    else:
        change = hd[lines].sum(axis=1).values / usual.reindex(hd.index.to_period("M")).values - 1
        effect = (pd.DataFrame({"Holiday": hd["holiday"].values, "Change": change})
                  .groupby("Holiday", as_index=False)["Change"].mean().sort_values("Change"))
        effect["Drop"] = -effect["Change"]  # bars grow rightwards so labels never hit the axis
        hbars = alt.Chart(effect).mark_bar(color=NAVY, cornerRadiusEnd=4).encode(
            y=alt.Y("Holiday:N", sort=None, title=None, axis=alt.Axis(labelLimit=240)),
            x=alt.X("Drop:Q", title="Fewer riders than a normal weekday", axis=alt.Axis(format="%")),
            tooltip=["Holiday", alt.Tooltip("Change:Q", title="Change", format="+.0%")])
        hlabels = hbars.mark_text(align="left", dx=4, color=MUTED).encode(text=alt.Text("Change:Q", format="+.0%"))
        st.altair_chart((hbars + hlabels).properties(height=28 * len(effect) + 40), use_container_width=True)
        st.caption("Each weekday holiday compared with the average normal weekday in the same month.")

with table_tab:
    st.dataframe(series.round(0), use_container_width=True,
                 column_config={l: st.column_config.NumberColumn(format="localized") for l in lines})
    st.download_button("Download CSV", series.round(0).to_csv().encode(), "rapidkl_ridership.csv",
                       "text/csv", icon=":material/download:")

st.divider()
st.caption(f"Source: [data.gov.my](https://data.gov.my/data-catalogue/ridership_headline) (Prasarana) · "
           f"Holidays: Kuala Lumpur calendar · [Code and method on GitHub]({REPO})")
