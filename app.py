import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Thai Fuel Tracker",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .stMetric { background: #f8f9fa; border-radius: 10px; padding: 10px; }
    .best-badge { background: #d4edda; color: #155724; padding: 4px 10px;
                  border-radius: 20px; font-weight: 600; font-size: 0.8rem; }
    .warning-box { background: #fff3cd; border-left: 4px solid #ffc107;
                   padding: 12px 16px; border-radius: 4px; margin: 8px 0; }
    .info-box { background: #d1ecf1; border-left: 4px solid #17a2b8;
                padding: 12px 16px; border-radius: 4px; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)


# --- 2. SIMULATED DATA (replace with a real API for production) ---
@st.cache_data(show_spinner="Loading price history…")
def get_historical_fuel_data():
    """
    ⚠️  SIMULATED DATA — replace with a real Thai EPPO/PTT API call in production.
    Five years of plausible Thai retail pump prices (THB/litre).
    """
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    days = 365 * 5
    dates = pd.date_range(end=datetime.today(), periods=days)
    t = np.arange(days)

    # Use a random seed based on today's date so the data is stable within
    # a single day but "feels fresh" each new day.
    seed = int(datetime.today().strftime("%Y%m%d"))
    rng = np.random.default_rng(seed)

    # Simulate realistic price paths (trend + macro cycle + daily noise)
    g95 = 33.0 + t * 0.003 + np.sin(t / 120) * 4.5 + rng.normal(0, 0.25, days)
    g91 = g95 - 0.40                    # 91 is slightly cheaper than 95
    e20 = g95 - 5.0                     # E20 government-subsidised band
    e85 = g95 - 14.5                    # E85 heavily subsidised (~17-22 THB)

    # Clip to plausible floor prices
    g95 = np.clip(g95, 28, 50)
    g91 = np.clip(g91, 27, 49)
    e20 = np.clip(e20, 22, 42)
    e85 = np.clip(e85, 15, 26)

    fuels = [
        ("Gasohol 95",  g95, 10),
        ("Gasohol 91",  g91, 10),
        ("Gasohol E20", e20, 20),
        ("Gasohol E85", e85, 85),
    ]

    rows = []
    for name, prices, eth_pct in fuels:
        for i, date in enumerate(dates):
            rows.append({
                "Date": date,
                "Fuel Type": name,
                "Price (THB/L)": round(float(prices[i]), 2),
                "Ethanol %": eth_pct,
            })

    return pd.DataFrame(rows), fetch_time


# --- 3. PHYSICS & ENERGY MATH ---
E_GAS = 34.2   # MJ per litre of pure gasoline
E_ETH = 21.1   # MJ per litre of pure ethanol

def add_energy_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    eth = df["Ethanol %"] / 100
    df["Energy (MJ/L)"] = ((1 - eth) * E_GAS + eth * E_ETH).round(2)
    df["Cost/MJ (THB)"]  = (df["Price (THB/L)"] / df["Energy (MJ/L)"]).round(4)
    # Effective cost per km: assumes a reference car doing 12 km/L on G95
    # E-fuels have lower energy density → real-world km/L drops proportionally
    REF_EFF_KML = 12.0   # km/L on Gasohol 95
    REF_MJ_PER_KM = (E_GAS * 0.90) / REF_EFF_KML   # ~10% richer mixture typical
    df["Cost/km (THB)"]  = (df["Cost/MJ (THB)"] * REF_MJ_PER_KM).round(3)
    return df


# --- 4. LOAD & PROCESS ---
raw_df, last_fetched = get_historical_fuel_data()
df = add_energy_columns(raw_df)

latest_date = df["Date"].max()
today_df = (
    df[df["Date"] == latest_date]
    .sort_values("Cost/MJ (THB)")
    .reset_index(drop=True)
)
best_fuel = today_df.iloc[0]["Fuel Type"]


# ============================================================
# HEADER
# ============================================================
col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.title("⛽ Thailand Fuel Value Tracker")
    st.markdown(
        f"*Simulated data for demonstration · last generated **{last_fetched}** · "
        f"covers **{df['Date'].min().strftime('%b %Y')} – {df['Date'].max().strftime('%b %Y')}***"
    )
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        get_historical_fuel_data.clear()
        st.rerun()

st.divider()


# ============================================================
# SECTION 1 — TODAY'S SNAPSHOT
# ============================================================
st.subheader(f"📅 Today's Prices  —  {latest_date.strftime('%d %b %Y')}")

cols = st.columns(len(today_df))
for col, (_, row) in zip(cols, today_df.iterrows()):
    label = "🏆 Best Value" if row["Fuel Type"] == best_fuel else ""
    col.metric(
        label=f"{row['Fuel Type']}  {label}",
        value=f"฿{row['Price (THB/L)']:.2f} / L",
        delta=f"฿{row['Cost/MJ (THB)']:.4f} per MJ",
        delta_color="off",
    )

# Show % more expensive than best
best_mj = today_df.iloc[0]["Cost/MJ (THB)"]
comparison_rows = []
for _, row in today_df.iterrows():
    pct_more = (row["Cost/MJ (THB)"] - best_mj) / best_mj * 100
    comparison_rows.append({
        "Fuel": row["Fuel Type"],
        "Pump Price (THB/L)": f"฿{row['Price (THB/L)']:.2f}",
        "Energy (MJ/L)": f"{row['Energy (MJ/L)']:.2f}",
        "Cost per MJ": f"฿{row['Cost/MJ (THB)']:.4f}",
        "vs Best Value": "✅ Best" if pct_more < 0.01 else f"+{pct_more:.1f}% more",
    })

st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)

st.divider()


# ============================================================
# SECTION 2 — PRACTICAL SAVINGS CALCULATOR
# ============================================================
st.subheader("🧮 Monthly Savings Calculator")
st.markdown("Enter your driving habits to see **real-money savings** across fuel types.")

c1, c2, c3 = st.columns(3)
with c1:
    km_per_month = st.number_input("KM driven per month", min_value=100, max_value=10000,
                                    value=1500, step=100)
with c2:
    base_kml = st.number_input("Your car's fuel economy on G95 (km/L)",
                                min_value=5.0, max_value=30.0, value=12.0, step=0.5,
                                help="Check your car manual or use your average fill-up data.")
with c3:
    st.markdown("""
    <div class='info-box'>
    💡 <b>Tip:</b> Check your trip computer or divide km driven by litres filled last time.
    </div>
    """, unsafe_allow_html=True)

# For each fuel, adjust effective km/L by energy density relative to G95
g95_mj_per_l = (0.90 * E_GAS + 0.10 * E_ETH)   # Gasohol 95 energy

calc_rows = []
for _, row in today_df.iterrows():
    fuel_mj_per_l = row["Energy (MJ/L)"]
    # Effective km/L scales linearly with energy content
    eff_kml = base_kml * (fuel_mj_per_l / g95_mj_per_l)
    litres_needed = km_per_month / eff_kml
    monthly_cost = litres_needed * row["Price (THB/L)"]
    calc_rows.append({
        "Fuel": row["Fuel Type"],
        "Effective km/L": round(eff_kml, 1),
        "Litres Needed": round(litres_needed, 1),
        "Monthly Cost (฿)": round(monthly_cost, 0),
    })

calc_df = pd.DataFrame(calc_rows)
cheapest_monthly = calc_df["Monthly Cost (฿)"].min()
calc_df["Monthly Saving vs Most Expensive"] = (
    calc_df["Monthly Cost (฿)"].max() - calc_df["Monthly Cost (฿)"]
).apply(lambda x: f"Save ฿{x:.0f}" if x > 0 else "Most expensive")

st.dataframe(calc_df, use_container_width=True, hide_index=True)

# Highlight annual saving
best_calc  = calc_df.loc[calc_df["Monthly Cost (฿)"].idxmin()]
worst_calc = calc_df.loc[calc_df["Monthly Cost (฿)"].idxmax()]
annual_saving = (worst_calc["Monthly Cost (฿)"] - best_calc["Monthly Cost (฿)"]) * 12
st.success(
    f"🏅 Switching from **{worst_calc['Fuel']}** to **{best_calc['Fuel']}** "
    f"could save you approximately **฿{annual_saving:,.0f} per year** "
    f"at {km_per_month:,} km/month."
)

st.divider()


# ============================================================
# SECTION 3 — WHICH FUEL IS RIGHT FOR MY CAR?
# ============================================================
st.subheader("🚗 Which Fuel Is Right for My Car?")
st.markdown("""
<div class='warning-box'>
⚠️ <b>Important:</b> Using the wrong fuel can damage or void the warranty of your engine.
Always check your owner's manual before switching.
</div>
""", unsafe_allow_html=True)

compat = pd.DataFrame([
    {
        "Fuel":         "Gasohol 91",
        "Ethanol %":    "10%",
        "Compatible with":  "Most petrol cars made after 2001",
        "Not recommended":  "High-performance or older carburettor engines",
        "Typical price":    "Cheapest standard option",
    },
    {
        "Fuel":         "Gasohol 95",
        "Ethanol %":    "10%",
        "Compatible with":  "All modern petrol cars, high-performance engines",
        "Not recommended":  "—",
        "Typical price":    "Slightly more than G91",
    },
    {
        "Fuel":         "Gasohol E20",
        "Ethanol %":    "20%",
        "Compatible with":  "Flex-fuel vehicles (FFV) & most cars made after ~2010",
        "Not recommended":  "Pre-2010 cars without E20 certification",
        "Typical price":    "Mid-range",
    },
    {
        "Fuel":         "Gasohol E85",
        "Ethanol %":    "85%",
        "Compatible with":  "Flex-Fuel Vehicles (FFV) ONLY — e.g. Honda, Toyota FFV models",
        "Not recommended":  "⛔ ALL non-FFV vehicles — causes serious engine damage",
        "Typical price":    "Lowest cost per litre but lower energy content",
    },
])

st.dataframe(compat, use_container_width=True, hide_index=True)
st.caption("Sources: EPPO Thailand, PTT Public Company Limited fuel guidelines.")

st.divider()


# ============================================================
# SECTION 4 — HISTORICAL TRENDS
# ============================================================
st.subheader("📈 Historical Price Trends")

tab1, tab2 = st.tabs(["Cost per MJ (True Value)", "Pump Price (THB/L)"])

timeframe = st.radio(
    "Chart resolution:",
    ["Daily", "Weekly", "Monthly"],
    horizontal=True,
    key="tf_radio",
)

resample_map = {"Daily": None, "Weekly": "W", "Monthly": "ME"}
rule = resample_map[timeframe]

def make_pivot(metric: str) -> pd.DataFrame:
    pivot = df.pivot(index="Date", columns="Fuel Type", values=metric)
    pivot.columns.name = None   # ← FIX: removes the "Fuel Type" label from legend
    if rule:
        pivot = pivot.resample(rule).mean()
    return pivot.round(4)

cost_pivot  = make_pivot("Cost/MJ (THB)")
price_pivot = make_pivot("Price (THB/L)")

with tab1:
    st.markdown("**Lower = better value per unit of energy delivered to your engine.**")
    st.line_chart(cost_pivot)

with tab2:
    st.markdown("**Raw pump price — does NOT account for energy content differences.**")
    st.line_chart(price_pivot)

with st.expander("📋 View raw data table"):
    st.dataframe(
        df.sort_values(["Date", "Cost/MJ (THB)"], ascending=[False, True]),
        use_container_width=True,
    )
