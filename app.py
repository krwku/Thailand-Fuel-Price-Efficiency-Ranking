"""
Thailand Fuel Value Tracker
============================
Primary data source: ราคาน้ำมัน.com (scraped on page load, cached 6 hrs)
Fallback: 209 real price-change events embedded directly from the site (Jan 2023–Mar 2026)

Prices only change when announced — the app forward-fills between events so
you get a complete daily series with no gaps.
"""

import io
import requests
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
from bs4 import BeautifulSoup

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Thai Fuel Tracker", page_icon="⛽", layout="wide")
st.markdown("""
<style>
  .warn { background:#fff3cd; border-left:4px solid #ffc107;
          padding:12px 16px; border-radius:4px; margin:8px 0; }
  .info { background:#d1ecf1; border-left:4px solid #17a2b8;
          padding:12px 16px; border-radius:4px; margin:8px 0; }
  .good { background:#d4edda; border-left:4px solid #28a745;
          padding:12px 16px; border-radius:4px; margin:8px 0; }
</style>
""", unsafe_allow_html=True)

# ── energy physics ────────────────────────────────────────────────────────────
E_GAS, E_ETH = 34.2, 21.1          # MJ / litre
FUELS = {"Gasohol 91": 10, "Gasohol 95": 10, "Gasohol E20": 20, "Gasohol E85": 85}

def energy_mj(eth):   return (1 - eth/100)*E_GAS + (eth/100)*E_ETH
_G95_MJ  = energy_mj(10)
_REF_KML = 12.0

# ── embedded historical data (real data from ราคาน้ำมัน.com, Jan 2023–Mar 2026) ──
# Format: date, G95, G91, E20, E85  — newest first, then reversed for forward-fill
EMBEDDED_CSV = """date,g95,g91,e20,e85
2026-03-26,41.05,40.68,36.05,32.79
2026-03-24,35.05,34.68,30.05,26.79
2026-03-21,33.05,32.68,28.05,24.79
2026-03-18,32.05,31.68,27.05,23.79
2026-03-10,31.05,30.68,27.84,25.79
2026-02-18,30.55,30.18,28.34,26.29
2026-01-09,30.85,30.48,28.64,26.59
2025-12-24,31.35,30.98,29.14,27.09
2025-10-21,31.85,31.48,29.64,27.59
2025-10-04,32.15,31.78,29.94,27.89
2025-09-24,32.65,32.28,30.44,28.69
2025-08-22,32.95,32.58,30.74,28.69
2025-08-09,32.55,32.18,30.34,28.69
2025-08-06,32.85,32.48,30.64,28.99
2025-08-05,33.25,32.88,31.04,29.39
2025-08-01,32.85,32.48,30.64,28.99
2025-07-24,32.45,32.08,30.24,28.59
2025-07-02,32.85,32.48,30.64,28.99
2025-06-26,33.15,32.78,30.94,29.29
2025-06-24,33.65,33.28,31.44,29.79
2025-06-20,33.25,32.88,31.04,29.39
2025-06-13,32.95,32.58,30.74,29.09
2025-05-22,32.55,32.18,30.34,28.69
2025-04-12,32.85,32.48,30.64,28.99
2025-04-09,33.15,32.78,30.94,29.29
2025-04-04,33.65,33.28,31.44,29.79
2025-03-28,34.15,33.78,31.94,30.29
2025-03-11,34.65,34.28,32.44,30.79
2025-03-06,34.95,34.58,32.74,31.19
2025-02-28,35.35,34.98,33.14,31.69
2025-02-25,35.65,35.28,33.44,32.09
2025-02-06,35.35,34.98,33.14,32.09
2025-01-23,35.75,35.38,33.54,32.59
2025-01-15,36.15,35.78,33.94,33.09
2025-01-11,35.65,35.28,33.44,33.09
2025-01-03,35.95,35.58,33.84,33.59
2024-12-20,36.25,35.88,34.14,33.89
2024-12-17,36.55,36.18,34.44,34.19
2024-12-13,36.15,35.78,34.04,33.79
2024-12-10,35.75,35.38,33.64,33.39
2024-12-03,36.05,35.68,33.94,33.69
2024-11-26,36.35,35.98,34.24,33.99
2024-11-20,35.95,35.58,33.84,33.59
2024-11-14,35.65,35.28,33.54,33.29
2024-11-07,35.95,35.58,33.84,33.59
2024-11-05,35.55,35.18,33.44,33.19
2024-10-31,35.25,34.88,33.14,32.89
2024-10-26,35.75,35.38,33.64,33.39
2024-10-17,35.45,35.08,33.34,33.09
2024-10-12,35.95,35.58,33.84,33.59
2024-10-08,35.65,35.28,33.54,33.29
2024-10-05,35.25,34.88,33.14,32.89
2024-10-01,34.95,34.58,32.84,32.59
2024-09-28,35.25,34.88,33.14,32.89
2024-09-20,35.75,35.38,33.64,33.39
2024-09-10,35.35,34.98,33.24,32.99
2024-09-06,35.85,35.48,33.74,33.49
2024-08-23,36.35,35.98,34.24,33.99
2024-08-20,36.65,36.28,34.54,34.29
2024-08-09,37.05,36.68,34.94,34.69
2024-08-06,37.35,36.98,35.24,34.99
2024-08-03,37.75,37.38,35.64,35.39
2024-08-01,38.05,37.68,35.94,35.69
2024-07-25,38.35,37.98,36.24,35.99
2024-07-10,38.85,38.48,36.74,36.49
2024-07-04,39.15,38.78,37.04,36.79
2024-06-29,38.75,38.38,36.64,36.39
2024-06-22,38.45,38.08,36.34,36.09
2024-06-20,38.05,37.68,35.94,35.69
2024-06-12,37.75,37.38,35.64,35.39
2024-06-06,37.85,37.48,35.74,35.49
2024-06-01,38.15,37.78,36.04,35.79
2024-05-31,38.15,37.78,36.04,35.79
2024-05-25,38.55,38.18,36.44,36.19
2024-05-17,38.95,38.58,36.84,36.59
2024-05-10,39.35,38.78,37.24,36.99
2024-05-08,39.85,39.28,37.74,37.49
2024-05-04,40.35,39.28,38.24,37.99
2024-04-27,39.95,38.88,37.84,37.59
2024-04-23,40.35,38.88,38.24,37.99
2024-04-20,40.35,38.88,38.24,37.99
2024-04-18,39.95,38.48,37.84,37.59
2024-04-06,39.95,38.48,37.84,37.59
2024-04-04,39.55,38.08,37.44,37.19
2024-04-03,39.15,37.68,37.04,36.79
2024-03-26,38.65,37.18,36.54,36.29
2024-03-20,38.25,36.78,36.14,35.89
2024-03-19,37.85,36.38,35.74,35.49
2024-03-07,38.15,36.38,36.04,35.79
2024-03-05,38.45,36.68,36.34,36.09
2024-02-29,38.05,36.28,35.94,35.69
2024-02-20,38.35,36.58,36.24,35.99
2024-02-16,37.95,36.18,35.84,35.99
2024-02-13,37.55,35.78,35.44,35.59
2024-01-31,37.25,35.48,35.14,35.29
2024-01-27,36.85,35.08,34.74,34.89
2024-01-25,36.35,34.58,34.24,34.39
2024-01-23,35.85,34.08,33.74,33.89
2024-01-20,35.55,33.78,33.44,33.59
2024-01-18,35.25,33.48,33.14,33.29
2024-01-16,34.75,32.98,32.64,32.79
2024-01-05,35.25,33.48,33.14,33.29
2023-12-29,35.55,33.78,33.44,33.59
2023-12-22,35.15,33.38,33.04,33.19
2023-12-19,34.75,32.98,32.64,32.79
2023-12-09,35.15,33.38,33.04,33.19
2023-12-07,35.65,33.88,33.54,33.69
2023-12-05,36.05,34.28,33.94,34.09
2023-11-22,36.45,34.68,34.34,34.49
2023-11-18,37.05,35.28,34.94,35.09
2023-11-16,36.65,34.88,34.54,34.69
2023-11-15,36.25,34.48,34.14,34.29
2023-11-10,36.65,34.88,34.54,34.69
2023-11-09,37.25,35.48,35.14,35.29
2023-11-07,38.25,37.98,35.94,36.09
2023-11-01,38.55,38.28,36.24,36.39
2023-10-31,38.25,37.98,35.94,36.09
2023-10-21,37.85,37.58,35.54,35.69
2023-10-17,38.15,37.88,35.84,35.99
2023-10-11,37.75,37.48,35.44,35.59
2023-10-07,38.25,37.98,35.94,35.59
2023-10-06,38.75,38.48,36.44,36.09
2023-10-04,39.15,38.88,36.84,36.49
2023-10-03,39.45,39.18,37.14,36.79
2023-09-27,39.95,39.68,37.64,37.29
2023-09-23,40.45,40.18,38.14,37.79
2023-09-20,40.45,40.18,38.14,37.79
2023-09-16,40.05,39.78,37.74,37.79
2023-09-15,39.65,39.38,37.34,37.79
2023-09-12,39.35,39.08,37.04,37.49
2023-09-02,39.65,39.38,37.34,37.79
2023-09-01,40.05,39.78,37.74,38.19
2023-08-29,39.55,39.28,37.24,37.69
2023-08-12,38.85,38.58,36.54,36.99
2023-08-09,38.55,38.28,36.24,36.69
2023-08-05,38.95,38.68,36.64,37.09
2023-08-03,38.35,38.08,36.04,36.49
2023-07-26,37.95,37.68,35.64,36.29
2023-07-25,37.55,37.28,35.24,35.69
2023-07-22,37.25,36.98,34.94,35.39
2023-07-20,36.95,36.68,34.64,35.09
2023-07-19,37.25,36.98,34.94,35.39
2023-07-18,36.95,36.68,34.64,35.09
2023-07-15,36.65,36.38,34.34,34.79
2023-07-14,36.35,36.08,34.04,34.49
2023-07-13,36.05,35.78,33.74,34.19
2023-07-11,35.55,35.28,33.24,33.69
2023-07-08,35.15,34.88,32.84,33.29
2023-07-06,35.65,35.38,33.34,33.79
2023-07-04,35.15,34.88,32.84,33.29
2023-07-02,35.15,34.88,32.84,33.29
2023-06-27,35.45,35.18,33.14,33.59
2023-06-20,34.95,34.68,32.64,33.09
2023-06-17,35.25,34.98,32.94,33.39
2023-06-14,35.75,35.48,33.44,33.89
2023-06-10,35.25,34.98,32.94,33.39
2023-06-07,34.65,34.38,32.34,32.79
2023-06-02,35.15,34.88,32.84,33.29
2023-05-30,35.45,35.18,33.14,33.59
2023-05-26,35.05,34.78,32.74,33.19
2023-05-23,34.75,34.48,32.44,32.89
2023-05-16,35.15,34.88,32.84,33.29
2023-05-15,35.45,35.18,33.14,33.59
2023-05-13,35.65,35.38,33.34,33.79
2023-05-11,35.35,35.08,33.04,33.49
2023-05-09,34.85,34.58,32.54,32.99
2023-05-04,35.45,35.18,33.14,33.59
2023-04-29,35.85,35.58,33.74,34.19
2023-04-28,36.35,36.08,34.04,34.49
2023-04-27,36.25,35.98,33.94,34.39
2023-04-26,36.25,35.98,33.94,34.39
2023-04-22,35.85,35.58,33.94,34.39
2023-04-21,35.35,35.08,33.44,33.89
2023-04-07,35.65,35.38,33.74,34.19
2023-04-06,35.95,35.68,34.04,34.49
2023-04-05,36.25,35.98,34.34,34.79
2023-04-04,36.65,36.38,34.74,35.19
2023-03-30,37.05,36.78,35.14,35.59
2023-03-25,36.75,36.48,34.84,35.29
2023-03-24,36.15,35.88,34.24,34.69
2023-03-22,35.55,35.28,33.64,34.09
2023-03-18,34.95,34.68,33.04,33.59 
2023-03-14,34.75,34.48,32.84,33.29
2023-03-10,34.75,34.48,32.84,32.99
2023-03-08,34.45,34.18,32.54,32.99
2023-02-28,35.05,34.78,33.14,33.29
2023-02-25,35.25,34.98,33.34,33.29
2023-02-23,35.55,35.28,33.64,33.59
2023-02-22,35.05,34.78,33.14,33.19
2023-02-21,35.35,35.08,33.44,33.49
2023-02-18,35.65,35.38,33.84,33.79
2023-02-16,36.05,35.78,34.24,34.19
2023-02-15,35.55,35.28,33.74,33.69
2023-02-10,35.05,34.78,33.24,33.19
2023-02-09,34.75,34.48,32.94,32.89
2023-02-08,34.45,34.18,32.64,32.59
2023-02-04,42.16,34.75,32.84,32.99
2023-02-02,42.46,35.05,33.14,33.29
2023-02-01,41.86,34.45,32.54,32.99
2023-01-26,42.16,34.75,32.84,32.99
2023-01-24,42.46,35.05,33.14,33.29
2023-01-21,42.96,35.55,33.64,34.09
2023-01-20,43.56,36.15,34.24,34.69
2023-01-17,43.16,35.75,33.84,34.29
2023-01-14,43.46,36.05,34.14,34.59
2023-01-13,43.76,36.35,34.44,34.89
2023-01-07,44.06,36.65,34.74,35.19
2023-01-06,44.06,36.65,34.74,35.19
2023-01-05,44.06,36.65,34.74,35.19
"""

# ── Thai date parser (used by the web scraper) ────────────────────────────────
THAI_MONTHS = {
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4,
    "พ.ค.": 5, "มิ.ย.": 6, "ก.ค.": 7, "ส.ค.": 8,
    "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
}

def parse_thai_date(text: str, be_year: int) -> date | None:
    """Parse '26 มี.ค.' with a known Buddhist Era year into a Python date."""
    text = text.strip()
    for abbr, month in THAI_MONTHS.items():
        if abbr in text:
            try:
                day = int(text.replace(abbr, "").strip())
                return date(be_year - 543, month, day)
            except ValueError:
                return None
    return None


# ── web scraper ───────────────────────────────────────────────────────────────
SCRAPE_URL = (
    "https://xn--42cah7d0cxcvbbb9x.com/"
    "%E0%B8%A3%E0%B8%B2%E0%B8%84%E0%B8%B2%E0%B8%99%E0%B9%89%E0%B8%B3"
    "%E0%B8%A1%E0%B8%B1%E0%B8%99%E0%B8%A2%E0%B9%89%E0%B8%AD%E0%B8%99"
    "%E0%B8%AB%E0%B8%A5%E0%B8%B1%E0%B8%87/"
)

@st.cache_data(ttl=6 * 3600, show_spinner="Fetching latest prices from ราคาน้ำมัน.com…")
def scrape_live() -> pd.DataFrame | None:
    """
    Scrape the price-change table from ราคาน้ำมัน.com.
    Returns a DataFrame with columns: date, g95, g91, e20, e85
    — or None if the fetch fails.
    """
    try:
        resp = requests.get(
            SCRAPE_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FuelTracker/1.0)"},
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # The page has one main table; columns (0-indexed):
    # 0=date  1=Benz95  2=G95  3=G91  4=E20  5=E85  6=DPrem  7=Diesel  8=B20  9=B7  10=NGV
    rows_out = []
    current_be_year = None

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not cells:
                continue

            # Detect year-header rows (contain a 4-digit Buddhist Era year like 2566–2570)
            row_text = " ".join(cells)
            for yr in range(2560, 2580):
                if str(yr) in row_text and len(cells) <= 3:
                    current_be_year = yr
                    break

            # Data row: needs ≥6 numeric-ish cells and a valid Thai date in cell[0]
            if current_be_year and len(cells) >= 6:
                parsed_date = parse_thai_date(cells[0], current_be_year)
                if parsed_date is None:
                    continue
                try:
                    g95  = float(cells[2].replace(",", ""))
                    g91  = float(cells[3].replace(",", ""))
                    e20  = float(cells[4].replace(",", ""))
                    e85  = float(cells[5].replace(",", ""))
                    rows_out.append({"date": parsed_date, "g95": g95,
                                     "g91": g91, "e20": e20, "e85": e85})
                except (ValueError, IndexError):
                    continue

    if not rows_out:
        return None

    df = pd.DataFrame(rows_out).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df


# ── load embedded fallback ────────────────────────────────────────────────────
def load_embedded() -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(EMBEDDED_CSV.strip()))
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date").reset_index(drop=True)


# ── merge live + embedded (live wins for any overlapping dates) ───────────────
def get_price_changes() -> tuple[pd.DataFrame, str]:
    live = scrape_live()
    embedded = load_embedded()

    if live is not None and len(live) > 0:
        # Keep all live rows; only add embedded rows for dates not in live
        combined = pd.concat([live, embedded[~embedded["date"].isin(live["date"])]])
        combined = combined.sort_values("date").reset_index(drop=True)
        source = f"🟢 **Live** from ราคาน้ำมัน.com ({len(live)} events) + embedded history"
    else:
        combined = embedded
        source = "🟡 **Embedded** data (ราคาน้ำมัน.com scrape unavailable)"

    return combined, source


# ── forward-fill to a complete daily series ───────────────────────────────────
def build_daily(changes: pd.DataFrame) -> pd.DataFrame:
    """
    Prices stay constant between announcements.
    Create one row per calendar day from the first change to today.
    """
    start = changes["date"].min()
    end   = date.today()
    all_dates = pd.date_range(start, end, freq="D")

    # Reindex to daily and forward-fill
    ch = changes.set_index("date")
    ch.index = pd.DatetimeIndex(ch.index)
    daily = ch.reindex(all_dates).ffill().reset_index()
    daily.columns = ["Date"] + list(ch.columns)

    rows = []
    for _, row in daily.iterrows():
        for fuel, eth in FUELS.items():
            col = {"Gasohol 91": "g91", "Gasohol 95": "g95",
                   "Gasohol E20": "e20", "Gasohol E85": "e85"}[fuel]
            price = row[col]
            if pd.isna(price):
                continue
            mj  = energy_mj(eth)
            rows.append({
                "Date":          row["Date"],
                "Fuel Type":     fuel,
                "Price (THB/L)": price,
                "Ethanol %":     eth,
                "Energy (MJ/L)": round(mj, 2),
                "Cost/MJ (THB)": round(price / mj, 4),
                "Cost/km (THB)": round((price / mj) * (_G95_MJ / _REF_KML), 3),
            })

    return pd.DataFrame(rows)


# ── load everything ───────────────────────────────────────────────────────────
changes, data_source = get_price_changes()
df = build_daily(changes)

latest_date = df["Date"].max()
today_df    = df[df["Date"] == latest_date].sort_values("Cost/MJ (THB)").reset_index(drop=True)
best_fuel   = today_df.iloc[0]["Fuel Type"]


# ═══════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════
c1, c2 = st.columns([5, 1])
with c1:
    st.title("⛽ Thailand Fuel Value Tracker")
    st.caption(
        f"{data_source}  ·  "
        f"{df['Date'].min().strftime('%b %Y')} – {df['Date'].max().strftime('%b %Y')}  ·  "
        "PTT / Bangchak retail (excl. Bangkok local tax)"
    )
with c2:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()


# ═══════════════════════════════════════════════════════════════════
# TODAY'S PRICES
# ═══════════════════════════════════════════════════════════════════
st.subheader(f"📅 Today's Prices — {latest_date.strftime('%d %b %Y')}")

cols = st.columns(len(today_df))
for col, (_, row) in zip(cols, today_df.iterrows()):
    badge = " 🏆" if row["Fuel Type"] == best_fuel else ""
    col.metric(
        label=f"{row['Fuel Type']}{badge}",
        value=f"฿{row['Price (THB/L)']:.2f}/L",
        delta=f"฿{row['Cost/MJ (THB)']:.4f}/MJ  ·  ฿{row['Cost/km (THB)']:.3f}/km",
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
        "True Value (฿/MJ)": f"฿{row['Cost/MJ (THB)']:.4f}",
        "vs Best":           "✅ Best" if pct < 0.01 else f"+{pct:.1f}% more",
    })
st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

st.markdown("""
<div class='info'>
💡 <b>Why "Cost per MJ"?</b>  E85 is cheap per litre but your engine gets ~40% less energy from it,
so you fill up more often. Cost per Megajoule is the fair apples-to-apples comparison.
</div>
""", unsafe_allow_html=True)

st.divider()


# ═══════════════════════════════════════════════════════════════════
# SAVINGS CALCULATOR
# ═══════════════════════════════════════════════════════════════════
st.subheader("🧮 Savings Calculator")

c1, c2, _ = st.columns([2, 2, 2])
with c1:
    km_pm = st.number_input("KM driven per month", 100, 10000, 1500, 100)
with c2:
    base_kml = st.number_input(
        "Fuel economy on G95 (km/L)", 5.0, 30.0, 12.0, 0.5,
        help="Divide last fill-up km by litres used, or check your trip computer.",
    )

calc = []
for _, row in today_df.iterrows():
    eff  = base_kml * (row["Energy (MJ/L)"] / _G95_MJ)
    lt   = km_pm / eff
    cost = lt * row["Price (THB/L)"]
    calc.append({"Fuel": row["Fuel Type"], "Effective km/L": round(eff, 1),
                 "Litres/month": round(lt, 1), "Monthly Cost (฿)": round(cost, 0)})

calc_df = pd.DataFrame(calc)
worst   = calc_df["Monthly Cost (฿)"].max()
calc_df["Saving vs Worst"] = (worst - calc_df["Monthly Cost (฿)"]).apply(
    lambda x: f"Save ฿{x:,.0f}" if x > 0 else "Most expensive"
)
st.dataframe(calc_df, use_container_width=True, hide_index=True)

best_c  = calc_df.loc[calc_df["Monthly Cost (฿)"].idxmin()]
worst_c = calc_df.loc[calc_df["Monthly Cost (฿)"].idxmax()]
annual  = (worst_c["Monthly Cost (฿)"] - best_c["Monthly Cost (฿)"]) * 12
st.success(
    f"🏅 Switching from **{worst_c['Fuel']}** → **{best_c['Fuel']}** "
    f"saves ~**฿{annual:,.0f}/year** at {km_pm:,} km/month."
)

st.divider()


# ═══════════════════════════════════════════════════════════════════
# HISTORICAL CHARTS
# ═══════════════════════════════════════════════════════════════════
st.subheader("📈 Historical Trends")

# Range selector
date_min = df["Date"].min().to_pydatetime()
date_max = df["Date"].max().to_pydatetime()

c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    tf = st.radio("Resolution:", ["Daily", "Weekly", "Monthly"], horizontal=True)
with c2:
    quick = st.selectbox("Quick range:", ["All time", "Last 1 year", "Last 6 months", "Last 3 months", "2026 only"])
with c3:
    st.write("")  # spacer

from datetime import datetime
quick_map = {
    "All time":       date_min,
    "Last 1 year":    date_max - timedelta(days=365),
    "Last 6 months":  date_max - timedelta(days=183),
    "Last 3 months":  date_max - timedelta(days=91),
    "2026 only":      datetime(2026, 1, 1),
}
range_start = quick_map[quick]
mask = df["Date"] >= pd.Timestamp(range_start)
plot_df = df[mask]

rule_map = {"Daily": None, "Weekly": "W", "Monthly": "ME"}
rule = rule_map[tf]

def make_pivot(col):
    p = plot_df.pivot(index="Date", columns="Fuel Type", values=col)
    p.columns.name = None
    return p if rule is None else p.resample(rule).mean().round(4)

tab1, tab2 = st.tabs(["True Value — Cost/MJ (lower = better ↓)", "Pump Price (THB/L)"])
with tab1:
    st.line_chart(make_pivot("Cost/MJ (THB)"))
with tab2:
    st.line_chart(make_pivot("Price (THB/L)"))

# Price-change events log
with st.expander(f"📋 Price change log ({len(changes)} events since {changes['date'].min()})"):
    display = changes.sort_values("date", ascending=False).copy()
    display.columns = ["Date", "G95 (฿/L)", "G91 (฿/L)", "E20 (฿/L)", "E85 (฿/L)"]
    st.dataframe(display, use_container_width=True, hide_index=True)

st.divider()


# ═══════════════════════════════════════════════════════════════════
# CAR COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════
with st.expander("🚗 Which fuel can my car use?"):
    st.markdown("""
    <div class='warn'>
    ⚠️ Using the wrong fuel can damage your engine and void your warranty.
    Always verify in your owner's manual.
    </div>
    """, unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([
        {"Fuel": "Gasohol 91",  "Ethanol": "10%", "✅ Safe for": "Most petrol cars after 2001",
         "⛔ Avoid": "High-performance / old carburettor engines"},
        {"Fuel": "Gasohol 95",  "Ethanol": "10%", "✅ Safe for": "All modern petrol cars incl. turbos",
         "⛔ Avoid": "—"},
        {"Fuel": "Gasohol E20", "Ethanol": "20%", "✅ Safe for": "Most cars made ≥ 2010 (Honda/Toyota/Isuzu)",
         "⛔ Avoid": "Pre-2010 cars without E20 certification"},
        {"Fuel": "Gasohol E85", "Ethanol": "85%", "✅ Safe for": "Flex-Fuel Vehicles (FFV) ONLY",
         "⛔ Avoid": "ALL non-FFV vehicles — serious engine damage"},
    ]), use_container_width=True, hide_index=True)
