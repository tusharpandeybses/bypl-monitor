import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="BYPL Intraday Dashboard", layout="wide")

def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- 2. THE CALCULATION ENGINE (FULL LOGIC) ---
def clean_key(text):
    return str(text).replace(" ", "").replace("_", "").upper().strip()

def process_sldc_data(api_json):
    try:
        # Load your local master files
        pm = pd.read_csv('plant_master.csv')
        fix_load = pd.read_csv('Fix load.csv')
        
        pm['clean_rldc'] = pm['RLDC'].apply(clean_key)
        rldc_map = dict(zip(pm['clean_rldc'], pm['SLDC Code']))
        ent_map = dict(zip(pm['SLDC Code'], pm['ENT %AGE']))
        
        # Identify columns for the 96-block table
        plant_cols = [c for c in fix_load.columns if c not in ['month', 'day', 'Period', 'Time Slot']]
        results = {c: [0.0]*96 for c in plant_cols}
        
        # Loop through API data
        for group in api_json.get('ResponseBody', {}).get('GroupWiseDataList', []):
            for item in group['FullschdList']:
                seller = clean_key(item.get('SellerAcronym', ''))
                buyer = item.get('BuyerAcronym', '').strip()
                
                # Resolve Plant Names (SECI, ALFANR, etc.)
                sldc_name = rldc_map.get(seller)
                if not sldc_name:
                    if "ALFANR" in seller: sldc_name = "ALFANR_II"
                    elif "SECI" in seller: sldc_name = "SECI_BYPL"

                if sldc_name and (sldc_name in results or sldc_name == "TEHRIPSP"):
                    # Calculate BYPL Share logic
                    share = 1.0 if buyer == "BYPL" else (float(ent_map.get(sldc_name, 0))/100.0 if buyer == "DELHI" else 0)
                    if share <= 0: continue
                    
                    sd = item.get('FullScheduleData', {})
                    isgs = sd.get('ISGSFullScheduleJsonData', {})
                    mw = [0.0]*96
                    
                    if isgs:
                        for k in ['ISGSThermalFullScheduleJsonData', 'ISGSHydroFullScheduleJsonData', 'ISGSGasFullScheduleJsonData']:
                            sub = isgs.get(k)
                            if sub: mw = sub.get('TotalDrwBoundarySchdAmount') or sub.get('SchdAmount') or [0.0]*96
                    else:
                        mw = sd.get('OAFullScheduleJsonData', {}).get('SchdAmount', [0.0]*96)
                    
                    for i in range(96):
                        val = round(float(mw[i]) * share, 2)
                        # Specific Split for TEHRI
                        if sldc_name == "TEHRIPSP":
                            if val < 0: results["TEHRIPSP_P"][i] += val
                            else: results["TEHRIPSP"][i] += val
                        elif sldc_name in results:
                            results[sldc_name][i] += val
        
        # Final Format Output
        final_df = pd.read_csv('format.csv') if os.path.exists('format.csv') else pd.DataFrame({'Period': range(1, 97)})
        for col in plant_cols:
            if col in results: final_df[col] = results[col]
        return final_df
    except Exception as e:
        st.error(f"Error in Processing: {e}")
        return None

# --- 3. DASHBOARD UI ---
ist_now = get_ist_time()
# Forced Logo fix: Using raw github URL so it never vanishes
LOGO_URL = "https://raw.githubusercontent.com/tusharpandeybses/bypl-monitor/main/logo.png"

col1, col2 = st.columns([1, 4])
with col1:
    st.image(LOGO_URL, width=150)
with col2:
    st.title("BYPL INTRADAY CONTROL ROOM")

st.markdown(f"### 🕒 IST Time: {ist_now.strftime('%H:%M:%S')} | Operating Block: {(ist_now.hour * 4) + (ist_now.minute // 15) + 1}")

# --- 4. DATA LOADING (FROM THE BRIDGE) ---
if os.path.exists("sldc_data.json"):
    with open("sldc_data.json", "r") as f:
        api_data = json.load(f)
    
    if "error" in api_data:
        st.error("🚨 SLDC Website Timed Out. GitHub Action will retry in 15 minutes.")
    else:
        rev = api_data.get('ResponseBody', {}).get('FullSchdRevisionNo', 'N/A')
        st.success(f"✅ Live Feed Active | Revision: {rev}")
        
        # Run the full processing logic
        df = process_sldc_data(api_data)
        if df is not None:
            st.dataframe(df, use_container_width=True, height=650)
else:
    st.warning("🔄 Syncing first data file from GitHub...")

time.sleep(30)
st.rerun()
