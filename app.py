import streamlit as st
import pandas as pd

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Thai Fuel Efficiency Tracker", page_icon="⛽", layout="centered")

# --- 2. DATA FETCHING ---
@st.cache_data
def get_fuel_data():
    """
    Fetches the latest oil prices. 
    Note: For this example, we use the current baseline prices. 
    To make this 100% live later, you can replace this dictionary with a 
    'requests.get()' call to a public Thai oil API (like Bangchak's XML feed).
    """
    data = {
        "Fuel Type": ["Gasohol 95", "Gasohol 91", "Gasohol E20"],
        "Price per Litre (THB)": [41.05, 40.68, 36.05], # Current Thai Pump Prices
        "Ethanol %": [10, 10, 20]
    }
    return pd.DataFrame(data)

# --- 3. THE MATH & LOGIC ---
def calculate_efficiency(df):
    # Energy constants (Megajoules per Litre)
    E_GAS = 34.2
    E_ETH = 21.1
    
    # Calculate energy per litre based on ethanol blend percentage
    # Formula: (Gasoline Proportion * Gasoline Energy) + (Ethanol Proportion * Ethanol Energy)
    df["Energy per Litre (MJ)"] = (
        ((100 - df["Ethanol %"]) / 100 * E_GAS) + 
        (df["Ethanol %"] / 100 * E_ETH)
    ).round(2)
    
    # Calculate Cost per Unit of Energy (THB / MJ)
    df["Cost per MJ (THB)"] = (df["Price per Litre (THB)"] / df["Energy per Litre (MJ)"]).round(3)
    
    # Rank them (1 is best/lowest cost per MJ)
    df = df.sort_values(by="Cost per MJ (THB)")
    df["Value Rank"] = range(1, len(df) + 1)
    
    return df

# --- 4. DASHBOARD UI ---
st.title("⛽ Thailand Fuel Value Tracker")
st.markdown("""
Pump prices don't tell the whole story. Because Ethanol contains less energy than pure gasoline, 
fuels with higher ethanol content (like E20) burn faster. 
This dashboard calculates the **true cost per unit of energy (Megajoule)** so you know which fuel is actually the best deal.
""")

st.divider()

# Load and process data
raw_data = get_fuel_data()
processed_data = calculate_efficiency(raw_data)

# Display Top Pick
best_fuel = processed_data.iloc[0]["Fuel Type"]
best_price = processed_data.iloc[0]["Cost per MJ (THB)"]
st.success(f"### 🏆 Today's Best Value: {best_fuel}\nAt **{best_price} THB per Megajoule**, this gives you the most distance for your money right now.")

# Show the Data Table
st.subheader("Data & Rankings")
# Reorder columns for a cleaner display
display_df = processed_data[["Value Rank", "Fuel Type", "Price per Litre (THB)", "Energy per Litre (MJ)", "Cost per MJ (THB)"]]
st.dataframe(display_df.set_index("Value Rank"), use_container_width=True)

# Visualize the Cost per MJ
st.subheader("Cost Comparison (Lower is Better)")
chart_data = processed_data.set_index("Fuel Type")[["Cost per MJ (THB)"]]
st.bar_chart(chart_data)

st.caption("Energy baseline metrics: Pure Gasoline = ~34.2 MJ/L | Pure Ethanol = ~21.1 MJ/L")