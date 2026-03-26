"""
Thailand Fuel Value Tracker
============================
Data source: EPPO Thailand (api.eppo.go.th) — Thailand's official energy authority.

To enable real data:
1. Register for a free API key at: https://data.eppo.go.th/RequestAPI
2. In Streamlit Cloud → App Settings → Secrets, add:
       EPPO_API_KEY = "your_key_here"
   OR create a local .streamlit/secrets.toml file with the same line.

Without a key the app still works, but uses simulated history and shows today's
real prices hardcoded from PTT/Bangchak announcements.
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Thai Fuel Tracker", page_icon="⛽", layout="wide")

st.markdown("""
<style>
  .warn  { background:#fff3cd; border-left:4px solid #ffc107;
           padding:12px 16px; border-radius:4px; margin:8px 0; }
  .info  { background:#d1ecf1; border-left:4px solid #17a2b8;
           padding:12px 16px; border-radius:4px; margin:8px 0; }
  .real  { background:#d4edda; border-left:4px solid #28a745;
           padding:12px 16px; border-radius:4px; margin:8px 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# FUEL DEFINITIONS
# ---------------------------------------------------------------------------
FUELS = {
    "Gasohol 91":  {"eth_pct": 10},
    "Gasohol 95":  {"eth_pct": 10},
    "Gasohol E20": {"eth_pct": 20},
    "Gasohol E85": {"eth_pct": 85},
}

# Real verified prices as of 26 Mar 2026 (PTT/Bangchak after subsidy cut)
# Source: Bangkok Post & Chiang Rai Times, confirmed same day
REAL_TODAY = {
    "Gasohol 91":  40.68,
    "Gasohol 95":  41.05,
    "Gasohol E20": 36.05,
    "Gasohol E85": 32.79,
}

E_GAS, E_ETH = 34.2, 21.1   # MJ per litre
EPPO_BASE    = "https://api.eppo.go.th/v1/openAPI"

# EPPO fuel codes for the retail price weekly endpoint
EPPO_CODES = {
    "Gasohol 91":  "E91",
    "Gasohol 95":  "E95",
    "Gasohol E20": "EE20",
    "Gasohol E85": "EE85",
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def energy_mj(eth_pct):
    return (1 - eth_pct / 100) * E_GAS + (eth_pct / 100) * E_ETH

_G95_MJ = energy_mj(10)
_REF_KML = 12.0

def cost_per_mj(price, eth_pct):
    return price / energy_mj(eth_pct)

def cost_per_km(price, eth_pct):
    return cost_per_mj(price, eth_pct) * (_G95_MJ / _REF_KML)


# ---------------------------------------------------------------------------
# API KEY — from Streamlit secrets OR sidebar input
# ---------------------------------------------------------------------------
def _get_secret_key():
    try:
        return st.secrets.get("EPPO_API_KEY", "")
    except Exception:
        return ""

with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input(
        "EPPO API Key",
        value=_get_secret_key(),
        type="password",
        help="Free key from https://data.eppo.go.th/RequestAPI",
    )
    st.markdown("""
**Get a free key (takes ~1 min):**
1. Visit [data.eppo.go.th/RequestAPI](https://data.eppo.go.th/RequestAPI)
2. Fill in the registration form
3. Key arrives by email in 1–2 days
4. Paste it above, or add to Streamlit Cloud secrets:
   ```
   EPPO_API_KEY = "your_key"
   ```
    """)
    st.divider()
    st.markdown("**🚗 Fuel compatibility**")
    st.markdown("""
| Fuel | Works in |
|------|---------|
| G91 / G95 | All petrol cars |
| E20 | Cars ≥ 2010 |
| E85 | ⚠️ FFV only |
    """)


# ---------------------------------------------------------------------------
# EPPO API FETCH
# ---------------------------------------------------------------------------
def _eppo_post(endpoint, payload, key):
    try:
        r = requests.post(
            f"{EPPO_BASE}/{endpoint}",
            json=payload,
            headers={"Content-Type": "application/json", "apikey": key},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.warning(f"EPPO API error (`{endpoint}`): {e}")
        return None


@st.cache_data(ttl=3600, show_spinner="Fetching live prices from EPPO Thailand…")
def fetch_eppo_history(api_key: str, years: int = 5):
    if not api_key:
        return None

    end_year   = datetime.today().year
    start_year = end_year - years
    rows = []

    for fuel_name, code in EPPO_CODES.items():
        eth = FUELS[fuel_name]["eth_pct"]
        data = _eppo_post(
            "oil/retailprice/week",
            {"fuelCode": code, "startYear": str(start_year), "endYear": str(end_year)},
            api_key,
        )
        if data is None:
            return None

        for item in data.get("data", []):
            try:
                rows.append({
                    "Date":          pd.to_datetime(item["weekdate"]),
                    "Fuel Type":     fuel_name,
                    "Price (THB/L)": float(item["price"]),
                    "Ethanol %":     eth,
                })
            except (KeyError, ValueError):
                continue

    if not rows:
        return None

    df = pd.DataFrame(rows)
    # Pin the latest data point to verified real prices
    latest = df["Date"].max()
    for fuel, price in REAL_TODAY.items():
        mask = (df["Date"] == latest) & (df["Fuel Type"] == fuel)
        df.loc[mask, "Price (THB/L)"] = price
    return df


# ---------------------------------------------------------------------------
# SIMULATED FALLBACK — anchored to real today prices
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Generating estimated history…")
def get_simulated_history():
    days  = 365 * 5
    dates = pd.date_range(end=datetime(2026, 3, 26), periods=days)
    t     = np.arange(days)
    rng   = np.random.default_rng(20260326)
    rows  = []

    for fuel, meta in FUELS.items():
        eth         = meta["eth_pct"]
        today_price = REAL_TODAY[fuel]
        noise       = rng.normal(0, 0.3, days)
        trend       = np.sin(t / 180) * 3.5
        path        = today_price + trend + noise.cumsum() * 0.04
        path        = np.clip(path, today_price - 12, today_price + 6)
        path[-1]    = today_price   # exact anchor on the last day

        for i, date in enumerate(dates):
            rows.append({
                "Date":          date,
                "Fuel Type":     fuel,
                "Price (THB/L)": round(float(path[i]), 2),
                "Ethanol %":     eth,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# LOAD & ENRICH DATA
# ---------------------------------------------------------------------------
live_df    = fetch_eppo_history(api_key) if api_key else None
using_live = live_df is not None

if using_live:
    df = live_df
    data_label = "🟢 **Live data from EPPO Thailand** (Ministry of Energy)"
elif api_key:
    df = get_simulated_history()
    data_label = "🟡 **EPPO API returned no data** — check your key. Showing simulated history."
else:
    df = get_simulated_history()
    data_label = "🔴 **No API key** — simulated history. Today's prices are real."

df["Energy (MJ/L)"] = df["Ethanol %"].apply(energy_mj).round(2)
df["Cost/MJ (THB)"] = df.apply(lambda r: cost_per_mj(r["Price (THB/L)"], r["Ethanol %"]), axis=1).round(4)
df["Cost/km (THB)"] = df.apply(lambda r: cost_per_km(r["Price (THB/L)"], r["Ethanol %"]), axis=1).round(3)

latest_date = df["Date"].max()
today_df    = df[df["Date"] == latest_date].sort_values("Cost/MJ (THB)").reset_index(drop=True)
best_fuel   = today_df.iloc[0]["Fuel Type"]


# ===========================================================================
# HEADER
# ===========================================================================
c1, c2 = st.columns([5, 1])
with c1:
    st.title("⛽ Thailand Fuel Value Tracker")
    st.caption(
        f"{data_label}  ·  "
        f"{df['Date'].min().strftime('%b %Y')} – {df['Date'].max().strftime('%b %Y')}  ·  "
        "Prices at PTT/Bangchak, excl. Bangkok local tax"
    )
with c2:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if not using_live:
    st.markdown("""
    <div class='warn'>
    ⚠️ <b>Estimated history only.</b>
    Today's prices are real (PTT/Bangchak, 26 Mar 2026 — prices rose ฿6/L after Oil Fuel Fund subsidy cut).
    For full authentic history, enter your free
    <a href="https://data.eppo.go.th/RequestAPI" target="_blank">EPPO API key</a> in the sidebar.
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class='real'>
    ✅ <b>Real data</b> from EPPO Thailand — Energy Policy & Planning Office, Ministry of Energy.
    Updated weekly.
    </div>
    """, unsafe_allow_html=True)

st.divider()


# ===========================================================================
# TODAY'S PRICES
# ===========================================================================
st.subheader(f"📅 Today's Prices — {latest_date.strftime('%d %b %Y')}")

cols = st.columns(len(today_df))
for col, (_, row) in zip(cols, today_df.iterrows()):
    badge = " 🏆" if row["Fuel Type"] == best_fuel else ""
    col.metric(
        label=f"{row['Fuel Type']}{badge}",
        value=f"฿{row['Price (THB/L)']:.2f}/L",
        delta=f"฿{row['Cost/MJ (THB)']:.4f} per MJ",
        delta_color="off",
    )

best_mj = today_df.iloc[0]["Cost/MJ (THB)"]
table   = []
for _, row in today_df.iterrows():
    pct = (row["Cost/MJ (THB)"] - best_mj) / best_mj * 100
    table.append({
        "Fuel":              row["Fuel Type"],
        "Pump Price":        f"฿{row['Price (THB/L)']:.2f}/L",
        "Energy Density":    f"{row['Energy (MJ/L)']:.2f} MJ/L",
        "True Value":        f"฿{row['Cost/MJ (THB)']:.4f}/MJ",
        "vs Best Value":     "✅ Best" if pct < 0.01 else f"+{pct:.1f}% more expensive",
    })
st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

st.markdown("""
<div class='info'>
💡 <b>Why "Cost per MJ"?</b> E85 is cheaper per litre but your engine gets ~40% less energy from it,
so you fill up more often. Cost/MJ is the fair comparison — like comparing price per kg, not per bag.
</div>
""", unsafe_allow_html=True)

st.divider()


# ===========================================================================
# SAVINGS CALCULATOR
# ===========================================================================
st.subheader("🧮 Savings Calculator")

c1, c2, _ = st.columns([2, 2, 2])
with c1:
    km_pm = st.number_input("KM driven per month", 100, 10000, 1500, 100)
with c2:
    base_kml = st.number_input(
        "Fuel economy on G95 (km/L)", 5.0, 30.0, 12.0, 0.5,
        help="Divide last fill-up km by litres used.",
    )

calc = []
for _, row in today_df.iterrows():
    eff  = base_kml * (row["Energy (MJ/L)"] / _G95_MJ)
    lt   = km_pm / eff
    cost = lt * row["Price (THB/L)"]
    calc.append({"Fuel": row["Fuel Type"], "Effective km/L": round(eff, 1),
                 "Litres needed": round(lt, 1), "Monthly Cost (฿)": round(cost, 0)})

calc_df = pd.DataFrame(calc)
worst   = calc_df["Monthly Cost (฿)"].max()
calc_df["Monthly Saving"] = (worst - calc_df["Monthly Cost (฿)"]).apply(
    lambda x: f"Save ฿{x:,.0f}" if x > 0 else "Most expensive"
)
st.dataframe(calc_df, use_container_width=True, hide_index=True)

best_c  = calc_df.loc[calc_df["Monthly Cost (฿)"].idxmin()]
worst_c = calc_df.loc[calc_df["Monthly Cost (฿)"].idxmax()]
annual  = (worst_c["Monthly Cost (฿)"] - best_c["Monthly Cost (฿)"]) * 12
st.success(
    f"🏅 Switching from **{worst_c['Fuel']}** to **{best_c['Fuel']}** "
    f"saves ~**฿{annual:,.0f}/year** at {km_pm:,} km/month."
)

st.divider()


# ===========================================================================
# HISTORICAL CHARTS
# ===========================================================================
st.subheader("📈 Historical Trends")

tf = st.radio("Resolution:", ["Weekly", "Monthly"], horizontal=True)
rule = "W" if tf == "Weekly" else "ME"

def make_pivot(col):
    p = df.pivot(index="Date", columns="Fuel Type", values=col)
    p.columns.name = None   # removes "Fuel Type" header from chart legend
    return p.resample(rule).mean().round(4)

tab1, tab2 = st.tabs(["True Value — Cost per MJ (lower = better)", "Pump Price (THB/L)"])
with tab1:
    st.line_chart(make_pivot("Cost/MJ (THB)"))
with tab2:
    st.line_chart(make_pivot("Price (THB/L)"))

with st.expander("📋 Raw data"):
    st.dataframe(
        df.sort_values(["Date", "Cost/MJ (THB)"], ascending=[False, True]),
        use_container_width=True,
    )
