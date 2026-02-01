import streamlit as st
import pandas as pd
import json
import os
import base64
from datetime import datetime, timedelta

# --- 1. SETTINGS & LAYOUT ---
st.set_page_config(page_title="BYPL Intraday Dashboard", layout="wide")
USER_ID = "1"; USER_PASS = "1"

def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- 2. LOGIN GATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        st.title("BYPL System Login")
        u = st.text_input("User ID")
        p = st.text_input("Password", type="password")
        if st.button("Access Dashboard", use_container_width=True):
            if u == USER_ID and p == USER_PASS:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# --- 3. DATA ENGINE (FULL BYPL LOGIC) ---
def clean_key(text):
    return str(text).replace(" ", "").replace("_", "").upper().strip()

def process_sldc_data(api_json):
    try:
        # Load local master files
        pm = pd.read_csv('plant_master.csv')
        fix_load = pd.read_csv('Fix load.csv')
        
        pm['clean_rldc'] = pm['RLDC'].apply(clean_key)
        rldc_map = dict(zip(pm['clean_rldc'], pm['SLDC Code']))
        ent_map = dict(zip(pm['SLDC Code'], pm['ENT %AGE']))
        
        plant_cols = [c for c in fix_load.columns if c not in ['month', 'day', 'Period', 'Time Slot']]
        results = {c: [0.0]*96 for c in plant_cols}
        
        for group in api_json.get('ResponseBody', {}).get('GroupWiseDataList', []):
            for item in group['FullschdList']:
                seller = clean_key(item.get('SellerAcronym', ''))
                buyer = item.get('BuyerAcronym', '').strip()
                
                # Resolve Plant Name
                sldc_name = rldc_map.get(seller)
                if not sldc_name:
                    if "ALFANR" in seller: sldc_name = "ALFANR_II"
                    elif "SECI" in seller: sldc_name = "SECI_BYPL"

                if sldc_name and (sldc_name in results or sldc_name == "TEHRIPSP"):
                    # Calculate BYPL Share
                    share = 1.0 if buyer == "BYPL" else (float(ent_map.get(sldc_name, 0))/100.0 if buyer == "DELHI" else 0)
                    if share <= 0: continue
                    
                    # Extract 96-block MW data
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
                        if sldc_name == "TEHRIPSP":
                            if val < 0: results["TEHRIPSP_P"][i] += val
                            else: results["TEHRIPSP"][i] += val
                        elif sldc_name in results:
                            results[sldc_name][i] += val
        
        # Merge with Format
        final_df = pd.read_csv('format.csv') if os.path.exists('format.csv') else pd.DataFrame({'Period': range(1, 97)})
        for col in plant_cols:
            if col in results: final_df[col] = results[col]
        return final_df
    except Exception as e:
        st.error(f"Processing Error: {e}")
        return None

# --- 4. MAIN DASHBOARD UI ---
ist_now = get_ist_time()
col1, col2 = st.columns([3, 1])
with col1:
    st.title("⚡ BYPL Intraday Control Room")
with col2:
    st.metric("Indian Standard Time", ist_now.strftime("%H:%M:%S"))

# --- 5. DATA LOADING (FROM BRIDGE) ---
if os.path.exists("sldc_data.json"):
    with open("sldc_data.json", "r") as f:
        api_data = json.load(f)
    
    rev = api_data.get('ResponseBody', {}).get('FullSchdRevisionNo', 'N/A')
    st.success(f"✅ Data Active | SLDC Revision: {rev} | Date: {ist_now.strftime('%d-%m-%Y')}")
    
    # Run the engine
    df = process_sldc_data(api_data)
    
    if df is not None:
        # Highlight current block
        curr_blk = (ist_now.hour * 4) + (ist_now.minute // 15) + 1
        st.info(f"Current Operating Block: {curr_blk}")
        
        # Display full 96-block schedule
        st.dataframe(df.style.highlight_max(axis=0), use_container_width=True, height=600)
    else:
        st.warning("Data found but could not be processed. Check CSV files.")
else:
    st.warning("🔄 Waiting for GitHub Action to sync data...")
    st.info("Please trigger the 'Update SLDC Data' workflow in the Actions tab on GitHub.")

