import streamlit as st
import pandas as pd
import requests
import json
import time
import os
import shutil
import base64
from datetime import datetime, timedelta

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="BYPL Control Room Monitor", layout="wide")
USER_ID = "1"; USER_PASS = "1"
PREV_CSV = "old_schedule/previous_fix_load.csv"

for folder in ["new_schedule", "old_schedule"]:
    os.makedirs(folder, exist_ok=True)

def get_base64_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1c2128; border-radius: 8px; padding: 15px; border: 1px solid #30363d; }
    .clock-text { font-size: 26px; font-family: 'Courier New'; color: #00ff00; font-weight: bold; text-align: right; }
    .alert-card { background-color: #2d1a1a; border-left: 5px solid #ff4b4b; padding: 12px; border_radius: 5px; color: #ff4b4b; margin-bottom: 8px; }
    .centered-title { text-align: center; color: #ffffff; margin-top: -10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN GATE ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
main_placeholder = st.empty()

if not st.session_state.authenticated:
    with main_placeholder.container():
        l_h1, l_h2 = st.columns([3, 1])
        with l_h2:
            st.markdown(f'<p class="clock-text">🕒 {datetime.now().strftime("%H:%M:%S")}</p>', unsafe_allow_html=True)
        
        _, center_col, _ = st.columns([1, 1.2, 1])
        with center_col:
            logo_b64 = get_base64_file("logo.png")
            if logo_b64:
                st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{logo_b64}" width="220"></div>', unsafe_allow_html=True)
            
            st.markdown("<h2 class='centered-title'>BYPL System Login</h2>", unsafe_allow_html=True)
            u = st.text_input("User ID", key="login_u")
            p = st.text_input("Password", type="password", key="login_p")
            if st.button("Access Dashboard", use_container_width=True):
                if u == USER_ID and p == USER_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    st.stop()

# --- 3. EXTRACTION ENGINE ---

def clean_key(text):
    return str(text).replace(" ", "").replace("\t", "").replace("_", "").replace("-", "").upper().strip()

def get_mw_values(item):
    sd = item.get('FullScheduleData', {})
    isgs = sd.get('ISGSFullScheduleJsonData', {})
    if isgs:
        for k in ['ISGSThermalFullScheduleJsonData', 'ISGSHydroFullScheduleJsonData', 'ISGSGasFullScheduleJsonData']:
            sub = isgs.get(k)
            if sub: 
                val = sub.get('TotalDrwBoundarySchdAmount') or sub.get('SchdAmount')
                if val: return val
    oa = sd.get('OAFullScheduleJsonData', {})
    if oa: return oa.get('SchdAmount', [0.0]*96)
    return [0.0]*96

def resolve_plant_name(raw_name, rldc_map):
    clean = clean_key(raw_name)
    if clean in rldc_map: return rldc_map[clean]
    
    if "KHST" in clean or "KAHAL" in clean:
        return "KAHLGAN2" if "2" in clean or "II" in clean else "KAHLGAN1"
    
    if "RAPP" in clean:
        if "7" in clean or "8" in clean or "D" in clean: return "RAPPD"
        return "RAPPC"

    if "SECI" in clean: return "SECI_BYPL"
    if "MEJIA" in clean: return "MEJIA7"
    if "DADRI" in clean and "2" in clean: return "DADRI_T2"
    if "ALFANR" in clean: return "ALFANR_II"
    if "ASEJ2" in clean: return "ASEJ2PL_BYPL"
    
    return None

def process_data(api_json):
    pm = pd.read_csv('plant_master.csv')
    pm['clean_key'] = pm['RLDC'].apply(clean_key)
    rldc_map = dict(zip(pm['clean_key'], pm['SLDC Code']))
    ent_map = dict(zip(pm['SLDC Code'], pm['ENT %AGE']))
    
    cols_source = pd.read_csv('Fix load.csv').columns.tolist()
    plant_cols = [c for c in cols_source if c not in ['month', 'day', 'Period', 'Time Slot']]
    
    results = {c: [0.0]*96 for c in plant_cols}
    
    for group in api_json.get('ResponseBody', {}).get('GroupWiseDataList', []):
        for item in group['FullschdList']:
            raw_rldc = item.get('SellerAcronym', '')
            buyer = item.get('BuyerAcronym', '').strip()
            
            if "BRPL" in raw_rldc.upper() and "SECI" not in raw_rldc.upper() and buyer != "BYPL":
                continue
            if buyer == "BRPL": continue

            sldc_name = resolve_plant_name(raw_rldc, rldc_map)

            if sldc_name and (sldc_name in results or sldc_name == "TEHRIPSP"):
                # SITAC capping removed as per request
                share = 1.0 if buyer == "BYPL" else float(ent_map.get(sldc_name, 0))/100.0
                mw = get_mw_values(item)
                
                for i in range(96):
                    val = round(mw[i] * share, 3)
                    
                    if sldc_name == "TEHRIPSP":
                        if val < 0:
                            if "TEHRIPSP_P" in results: results["TEHRIPSP_P"][i] += val
                        else:
                            if "TEHRIPSP" in results: results["TEHRIPSP"][i] += val
                    elif sldc_name in results:
                        results[sldc_name][i] += val
    
    final_df = pd.read_csv('format.csv') if os.path.exists('format.csv') else pd.DataFrame({'Period': range(1, 97)})
    for col in plant_cols: final_df[col] = results[col]
    return final_df

# --- 4. DASHBOARD ---
with main_placeholder.container():
    h1, h2, h3 = st.columns([1, 2, 1])
    with h1:
        logo_b64 = get_base64_file("logo.png")
        if logo_b64: st.markdown(f'<img src="data:image/png;base64,{logo_b64}" width="180">', unsafe_allow_html=True)
    with h2: st.markdown('<h1 class="centered-title">BYPL Intraday Dashboard</h1>', unsafe_allow_html=True)
    with h3: st.markdown(f'<p class="clock-text">🕒 {datetime.now().strftime("%H:%M:%S")}</p>', unsafe_allow_html=True)

    try:
        today_str = datetime.now().strftime("%d-%m-%Y")
        url = f"https://www.delhisldc.org/Filesshared/api_response_{today_str}.json"
        st.session_state.api_data = requests.get(url, timeout=5).json()
            
        api_data = st.session_state.api_data
        rev = api_data['ResponseBody']['FullSchdRevisionNo']
        full_df = process_data(api_data)
        
        now = datetime.now()
        curr_blk = (now.hour * 4) + (now.minute // 15) + 1
        alerts = []

        if os.path.exists(PREV_CSV):
            try:
                old_df = pd.read_csv(PREV_CSV)
                if list(old_df.columns) == list(full_df.columns):
                    numeric_cols = [c for c in full_df.columns if c not in ['Period', 'Time Slot']]
                    for col in numeric_cols:
                        for blk in range(curr_blk - 1, min(96, curr_blk + 12)):
                            diff = full_df.at[blk, col] - old_df.at[blk, col]
                            if abs(diff) >= 3.0:
                                alerts.append({"P": col, "B": blk+1, "O": old_df.at[blk, col], "N": full_df.at[blk, col], "D": round(diff, 2)})
                                break
                else: os.remove(PREV_CSV)
            except: os.remove(PREV_CSV)

        if "last_rev" not in st.session_state: st.session_state.last_rev = 0
        if rev > st.session_state.last_rev:
            if alerts and os.path.exists("chime.mp3"):
                audio_b64 = get_base64_file("chime.mp3")
                st.markdown(f'<audio autoplay><source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)
            
            files_in_new = [f for f in os.listdir("new_schedule") if f.endswith(".csv")]
            if files_in_new:
                old_path = os.path.join("new_schedule", files_in_new[0])
                if os.path.exists(PREV_CSV): os.remove(PREV_CSV)
                shutil.move(old_path, PREV_CSV)
            
            for f in os.listdir("new_schedule"): os.remove(os.path.join("new_schedule", f))
            full_df.to_csv(f"new_schedule/Rev_{rev}.csv", index=False)
            st.session_state.last_rev = rev

        st.divider()
        with st.expander("🔔 INTRADAY ALERTS (>3MW Change / Next 3 Hrs)", expanded=True):
            if alerts:
                for a in alerts:
                    st.markdown(f'<div class="alert-card">⚠️ <b>{a["P"]}</b> | Block {a["B"]} | Δ {a["D"]} MW</div>', unsafe_allow_html=True)
            else: st.success("✅ Schedule Stable")

        m1, m2, m3 = st.columns(3)
        m1.metric("Revision", f"REV {rev}"); m2.metric("Active Block", f"Block {curr_blk}"); m3.metric("Status", "LIVE")

        st.divider()
        col_list = [c for c in full_df.columns if c not in ['Period', 'Time Slot']]
        sel_plant = st.selectbox("🎯 Select Plant", sorted(col_list))
        
        g1, g2 = st.columns([2, 1])
        with g1: st.line_chart(full_df[sel_plant], color="#00ff00")
        with g2: 
            st.dataframe(full_df[['Time Slot', sel_plant]], height=350, use_container_width=True, hide_index=True)
            st.download_button("📥 Export CSV", full_df.to_csv(index=False).encode('utf-8'), f"Rev_{rev}.csv")

        st.divider()
        st.subheader("📋 Consolidated View")
        st.dataframe(full_df, height=400, use_container_width=True, hide_index=True)

    except Exception as e: st.error(f"Syncing Data...")

    time.sleep(1)
    st.rerun()
