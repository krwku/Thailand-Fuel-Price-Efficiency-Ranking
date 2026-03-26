import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Thai Fuel Efficiency Tracker", page_icon="⛽", layout="wide")

# --- 2. DATA FETCHING ---
@st.cache_data
def get_historical_fuel_data():
    """
    Generates historical data and captures the exact time the function ran.
    """
    # Capture the fetch time
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dates = pd.date_range(end=datetime.today(), periods=30)
    
    np.random.seed(42) 
    base_95 = 41.05 + np.random.normal(0, 0.15, 30).cumsum()
    base_91 = 40.68 + np.random.normal(0, 0.15, 30).cumsum()
    base_e20 = 36.05 + np.random.normal(0, 0.15, 30).cumsum()
    
    data = []
    for i, date in enumerate(dates):
        data.extend([
            {"Date": date, "Fuel Type": "Gasohol 95", "Price per Litre (THB)": round(base_95[i], 2), "Ethanol %": 10},
            {"Date": date, "Fuel Type": "Gasohol 91", "Price per Litre (THB)": round(base_91[i], 2), "Ethanol %": 10},
            {"Date": date, "Fuel Type": "Gasohol E20", "Price per Litre (THB)": round(base_e20[i], 2), "Ethanol %": 20}
        ])
        
    # Now returning TWO things: the dataframe and the timestamp
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
# Use columns to put the title on the left and the refresh button on the right
col_title, col_btn = st.columns([4, 1])

with col_title:
    st.title("⛽ Thailand Fuel Value Tracker")

with col_btn:
    st.write("") # Spacer to align the button
    if st.button("🔄 Refresh Data", use_container_width=True):
        # This clears the cache so the function runs again
        get_historical_fuel_data.clear()
        # This reloads the page
        st.rerun()

st.markdown("Track the **true cost of energy (Cost per Megajoule)** over time to see which fuel offers the best long-term value.")

# Load and process data
raw_data, last_fetched = get_historical_fuel_data()
processed_data = calculate_efficiency(raw_data)

# Show the timestamp right below the intro text
st.caption(f"⏱️ **Data last fetched:** {last_fetched}")
st.divider()

# Extract just today's data for the top highlight
latest_date = processed_data['Date'].max()
todays_data = processed_data[processed_data['Date'] == latest_date].sort_values(by="Cost per MJ (THB)")

best_fuel = todays_data.iloc[0]["Fuel Type"]
best_price = todays_data.iloc[0]["Cost per MJ (THB)"]
st.success(f"### 🏆 Today's Best Value ({latest_date.strftime('%b %d, %Y')}): {best_fuel}\nAt **{best_price} THB per Megajoule**.")

# --- 5. HISTORICAL CHARTS ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 True Value Trend (Cost per MJ)")
    st.markdown("*(Lower is better)*")
    value_chart_data = processed_data.pivot(index='Date', columns='Fuel Type', values='Cost per MJ (THB)')
    st.line_chart(value_chart_data)

with col2:
    st.subheader("💵 Pump Price Trend (THB / Litre)")
    st.markdown("*(The standard pump price)*")
    price_chart_data = processed_data.pivot(index='Date', columns='Fuel Type', values='Price per Litre (THB)')
    st.line_chart(price_chart_data)

st.divider()

with st.expander("View Raw Historical Data"):
    st.dataframe(processed_data.sort_values(by=["Date", "Cost per MJ (THB)"], ascending=[False, True]), use_container_width=True)
