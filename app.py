import streamlit as st
import pandas as pd
import requests
import time
import os
import base64
from datetime import datetime, timedelta

# --- 1. SET WIDE LAYOUT (FIXES "SHORT" APP) ---
st.set_page_config(page_title="BYPL Control Room Monitor", layout="wide")

# --- 2. IST TIME CALCULATION ---
def get_ist_time():
    # Offset UTC by 5.5 hours for India
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- 3. SMART PATH FINDER (FIXES "SYNCING" HANG) ---
def find_file(filename):
    """Checks the root and subfolders for a file."""
    if os.path.exists(filename):
        return filename
    # Checks if it's hidden inside "SLDC monitor" folder
    alt_path = os.path.join("SLDC monitor", filename)
    if os.path.exists(alt_path):
        return alt_path
    return None

def get_base64_file(bin_file):
    path = find_file(bin_file)
    if path:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return None

# --- 4. STYLE INJECTION ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .clock-container {
        background-color: #1c2128;
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #00ff00;
        text-align: center;
    }
    .clock-text { font-size: 36px; font-family: 'Courier New'; color: #00ff00; font-weight: bold; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# --- 5. DATA ENGINE ---
def process_sldc_data(api_json):
    try:
        master_path = find_file('plant_master.csv')
        fix_path = find_file('Fix load.csv')
        format_path = find_file('format.csv')

        if not master_path or not fix_path:
            st.error("CRITICAL ERROR: CSV files not found on GitHub!")
            return None

        pm = pd.read_csv(master_path)
        fix_load = pd.read_csv(fix_path)
        
        pm['clean_rldc'] = pm['RLDC'].str.replace(" ", "").str.upper()
        rldc_map = dict(zip(pm['clean_rldc'], pm['SLDC Code']))
        ent_map = dict(zip(pm['SLDC Code'], pm['ENT %AGE']))
        
        plant_cols = [c for c in fix_load.columns if c not in ['month', 'day', 'Period', 'Time Slot']]
        results = {c: [0.0]*96 for c in plant_cols}
        
        for group in api_json.get('ResponseBody', {}).get('GroupWiseDataList', []):
            for item in group['FullschdList']:
                seller = str(item.get('SellerAcronym', '')).replace(" ", "").upper()
                buyer = item.get('BuyerAcronym', '').strip()
                
                sldc_name = rldc_map.get(seller)
                if not sldc_name:
                    if "ALFANR" in seller: sldc_name = "ALFANR_II"
                    elif "SECI" in seller: sldc_name = "SECI_BYPL"

                if sldc_name and (sldc_name in results or sldc_name == "TEHRIPSP"):
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
                        if sldc_name == "TEHRIPSP":
                            if val < 0: results["TEHRIPSP_P"][i] += val
                            else: results["TEHRIPSP"][i] += val
                        elif sldc_name in results:
                            results[sldc_name][i] += val
        
        final_df = pd.read_csv(format_path) if format_path else pd.DataFrame({'Period': range(1, 97)})
        for col in plant_cols:
            if col in results: final_df[col] = results[col]
        return final_df
    except Exception as e:
        st.error(f"Engine Error: {e}")
        return None

# --- 6. UI LAYOUT ---
ist_now = get_ist_time()

# Header with Integrated Clock
c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    logo_b64 = get_base64_file("logo.png") or get_base64_file("logo.PNG")
    if logo_b64:
        st.markdown(f'<img src="data:image/png;base64,{logo_b64}" width="200">', unsafe_allow_html=True)
with c2:
    st.markdown("<h1 style='text-align: center; color: white;'>BYPL INTRADAY DASHBOARD</h1>", unsafe_allow_html=True)
with c3:
    st.markdown(f"""
        <div class="clock-container">
            <p style='color: #888; margin: 0;'>INDIAN STANDARD TIME</p>
            <p class="clock-text">{ist_now.strftime("%H:%M:%S")}</p>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- 7. DATA EXECUTION ---
try:
    ist_date = ist_now.strftime('%d-%m-%Y')
    url = f"https://www.delhisldc.org/Filesshared/api_response_{ist_date}.json"
    resp = requests.get(url, timeout=10)
    
    if resp.status_code == 200:
        data = resp.json()
        rev = data['ResponseBody']['FullSchdRevisionNo']
        
        if "last_rev" not in st.session_state: st.session_state.last_rev = rev
        
        # Detect Revision Change for Chime
        if rev > st.session_state.last_rev:
            chime_b64 = get_base64_file("chime.mp3") or get_base64_file("Chime.mp3")
            if chime_b64:
                st.markdown(f'<audio autoplay><source src="data:audio/mp3;base64,{chime_b64}"></audio>', unsafe_allow_html=True)
            st.session_state.last_rev = rev
            st.toast(f"New Revision {rev} Detected!", icon="🔔")

        df = process_sldc_data(data)
        if df is not None:
            st.success(f"LIVE FEED ACTIVE | REVISION: {rev} | DATE: {ist_date}")
            st.dataframe(df, use_container_width=True, height=600)
    else:
        st.warning(f"🔄 Waiting for SLDC to publish data for {ist_date}...")

except Exception as e:
    st.error("Connecting to SLDC server...")

# Auto-refresh every 30 seconds
time.sleep(30)
st.rerun()
