import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Thai Fuel Efficiency Tracker", page_icon="⛽", layout="wide")

# --- 2. DATA FETCHING (Now 5 Years!) ---
@st.cache_data
def get_historical_fuel_data():
    """
    Generates 5 years of historical data and captures the exact fetch time.
    """
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    days = 365 * 5 # 5 years of data
    dates = pd.date_range(end=datetime.today(), periods=days)
    time_array = np.arange(days)
    
    # Simulating 5 years of realistic prices (base + trend + market cycles + daily noise)
    np.random.seed(42)
    # Gasohol 95 baseline moving between roughly 30 and 45 THB over 5 years
    base_95 = 33.0 + (time_array * 0.003) + (np.sin(time_array / 100) * 4) + np.random.normal(0, 0.2, days)
    base_91 = base_95 - 0.40 # 91 is usually just slightly cheaper
    base_e20 = base_95 - 5.0 # E20 is usually heavily subsidized/cheaper
    
    data = []
    for i, date in enumerate(dates):
        data.extend([
            {"Date": date, "Fuel Type": "Gasohol 95", "Price per Litre (THB)": round(base_95[i], 2), "Ethanol %": 10},
            {"Date": date, "Fuel Type": "Gasohol 91", "Price per Litre (THB)": round(base_91[i], 2), "Ethanol %": 10},
            {"Date": date, "Fuel Type": "Gasohol E20", "Price per Litre (THB)": round(base_e20[i], 2), "Ethanol %": 20}
        ])
        
    return pd.DataFrame(data), fetch_time

# --- 3. THE MATH & LOGIC ---
def calculate_efficiency(df):
    E_GAS = 34.2
    E_ETH = 21.1
    
    df["Energy per Litre (MJ)"] = (
        ((100 - df["Ethanol %"]) / 100 * E_GAS) + 
        (df["Ethanol %"] / 100 * E_ETH)
    ).round(2)
    
    df["Cost per MJ (THB)"] = (df["Price per Litre (THB)"] / df["Energy per Litre (MJ)"]).round(3)
    return df

# --- 4. DASHBOARD UI ---
col_title, col_btn = st.columns([4, 1])

with col_title:
    st.title("⛽ Thailand Fuel Value Tracker")

with col_btn:
    st.write("") 
    if st.button("🔄 Refresh Data", use_container_width=True):
        get_historical_fuel_data.clear()
        st.rerun()

st.markdown("Track the **true cost of energy (Cost per Megajoule)** over time to see which fuel offers the best long-term value.")

# Load and process data
raw_data, last_fetched = get_historical_fuel_data()
processed_data = calculate_efficiency(raw_data)

st.caption(f"⏱️ **Data last fetched:** {last_fetched} | **Data range:** {processed_data['Date'].min().strftime('%Y-%m-%d')} to {processed_data['Date'].max().strftime('%Y-%m-%d')}")
st.divider()

# Extract just today's data for the top highlight
latest_date = processed_data['Date'].max()
todays_data = processed_data[processed_data['Date'] == latest_date].sort_values(by="Cost per MJ (THB)")

best_fuel = todays_data.iloc[0]["Fuel Type"]
best_price = todays_data.iloc[0]["Cost per MJ (THB)"]
st.success(f"### 🏆 Today's Best Value ({latest_date.strftime('%b %d, %Y')}): {best_fuel}\nAt **{best_price} THB per Megajoule**.")

# --- 5. CHART CONTROLS & AGGREGATION ---
st.subheader("Historical Trends")
timeframe = st.radio(
    "Select Chart Resolution:",
    ["Daily", "Weekly", "Monthly"],
    horizontal=True
)

# Pivot the data first so dates are the index and fuel types are the columns
cost_pivot = processed_data.pivot(index='Date', columns='Fuel Type', values='Cost per MJ (THB)')
price_pivot = processed_data.pivot(index='Date', columns='Fuel Type', values='Price per Litre (THB)')

# Group data based on user selection using Pandas 'resample'
if timeframe == "Weekly":
    # 'W' stands for Weekly average
    cost_chart_data = cost_pivot.resample('W').mean()
    price_chart_data = price_pivot.resample('W').mean()
elif timeframe == "Monthly":
    # 'ME' stands for Month-End average (replaces the older 'M' string)
    cost_chart_data = cost_pivot.resample('ME').mean()
    price_chart_data = price_pivot.resample('ME').mean()
else:
    # Daily
    cost_chart_data = cost_pivot
    price_chart_data = price_pivot


# --- 6. RENDER CHARTS ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("**📊 True Value Trend (Cost per MJ)** - *Lower is better*")
    st.line_chart(cost_chart_data)

with col2:
    st.markdown("**💵 Pump Price Trend (THB / Litre)**")
    st.line_chart(price_chart_data)

st.divider()

with st.expander("View Raw Historical Data"):
    st.dataframe(processed_data.sort_values(by=["Date", "Cost per MJ (THB)"], ascending=[False, True]), use_container_width=True)
