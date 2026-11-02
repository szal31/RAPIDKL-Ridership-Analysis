"""Interactive Rapid KL ridership explorer.

Usage:  streamlit run app.py
"""
import altair as alt
import pandas as pd
import streamlit as st

from analysis import LEGACY, LINES, load

st.set_page_config(page_title="Rapid KL Ridership", layout="wide")


@st.cache_data
def data():
    return load()


df = data()
all_lines = list(LINES.values())

st.title("Rapid KL rail ridership")
st.caption(f"Daily riders per line, {df.index.min():%b %Y} to {df.index.max():%d %b %Y}. "
           "Source: data.gov.my (Prasarana).")

with st.sidebar:
    lines = st.multiselect("Lines", all_lines, default=all_lines)
    start, end = st.date_input(
        "Date range", (pd.Timestamp("2023-01-01"), df.index.max()),
        min_value=df.index.min(), max_value=df.index.max())
    grain = st.radio("Show as", ["Daily", "Weekly avg", "Monthly avg"], index=2)

if not lines:
    st.warning("Pick at least one line.")
    st.stop()

view = df.loc[str(start):str(end)]
total = view[lines].sum(axis=1, min_count=1)

c1, c2, c3 = st.columns(3)
c1.metric("Avg daily riders", f"{total.mean():,.0f}")
c2.metric("Busiest day", f"{total.max():,.0f}", f"{total.idxmax():%a %d %b %Y}", delta_color="off")
legacy = [l for l in lines if l in LEGACY]
if legacy:
    base = df.loc["2019", legacy].sum(axis=1).mean()
    c3.metric("Original lines vs 2019", f"{view[legacy].sum(axis=1).mean() / base:.0%}",
              help="Average daily riders on the selected pre-2020 lines, compared with their 2019 average.")

st.subheader("Ridership over time")
rule = {"Daily": None, "Weekly avg": "W", "Monthly avg": "MS"}[grain]
series = view[lines] if rule is None else view[lines].resample(rule).mean()
st.line_chart(series, y_label="Riders per day")

left, right = st.columns(2)
with left:
    st.subheader("Average by day of week")
    normal = view[view["holiday"].isna()]
    by_dow = normal[lines].groupby(normal.index.day_name()).mean() \
        .reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
    dow = by_dow.sum(axis=1).rename("Riders per day").rename_axis("Day").reset_index()
    st.altair_chart(alt.Chart(dow).mark_bar().encode(
        y=alt.Y("Day", sort=None, title=None), x=alt.X("Riders per day", axis=alt.Axis(format=",.0f")),
        tooltip=["Day", alt.Tooltip("Riders per day", format=",.0f")]), use_container_width=True)
with right:
    st.subheader("Public holidays vs normal weekday")
    wk = view[~view["weekend"]]
    usual = wk[wk["holiday"].isna()].groupby(wk[wk["holiday"].isna()].index.to_period("M"))[lines].mean().sum(axis=1)
    hol = wk[wk["holiday"].notna()]
    if hol.empty:
        st.info("No weekday public holidays in this range.")
    else:
        change = hol[lines].sum(axis=1).values / usual.reindex(hol.index.to_period("M")).values - 1
        table = pd.DataFrame({"Holiday": hol["holiday"], "Change": change}).groupby("Holiday")["Change"].mean()
        st.dataframe(table.sort_values().map("{:+.0%}".format), use_container_width=True)

with st.expander("Data table"):
    st.dataframe(series.round(0), use_container_width=True)
