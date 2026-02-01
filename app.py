import streamlit as st
import pandas as pd
import requests
import time
import os
import base64
from datetime import datetime, timedelta

# --- 1. CONFIG ---
st.set_page_config(page_title="BYPL Control Room Monitor", layout="wide")
USER_ID = "1"; USER_PASS = "1"

# --- 2. IST TIME ---
def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- 3. ASSET LOADER ---
def get_base64_file(bin_file):
    # Try multiple common paths for Streamlit Cloud
    paths = [bin_file, os.path.join("SLDC monitor", bin_file), bin_file.lower(), bin_file.upper()]
    for p in paths:
        if os.path.exists(p):
            with open(p, 'rb') as f:
                return base64.b64encode(f.read()).decode()
    return None

# --- 4. LOGIN GATE (FORCED) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        logo_b64 = get_base64_file("logo.png") or get_base64_file("logo.PNG")
        if logo_b64:
            st.markdown(f'<center><img src="data:image/png;base64,{logo_b64}" width="220"></center>', unsafe_allow_html=True)
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

# --- 5. STYLING ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .clock-box { background-color: #1c2128; padding: 10px; border-radius: 10px; border: 1px solid #00ff00; text-align: center; }
    .clock-text { font-size: 32px; font-family: 'Courier New'; color: #00ff00; font-weight: bold; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

# --- 6. HEADER ---
ist_now = get_ist_time()
c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    logo_b64 = get_base64_file("logo.png") or get_base64_file("logo.PNG")
    if logo_b64: st.markdown(f'<img src="data:image/png;base64,{logo_b64}" width="180">', unsafe_allow_html=True)
with c2:
    st.markdown("<h1 style='text-align: center;'>BYPL INTRADAY DASHBOARD</h1>", unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="clock-box"><p style="color:#888;margin:0">IST TIME</p><p class="clock-text">{ist_now.strftime("%H:%M:%S")}</p></div>', unsafe_allow_html=True)

st.divider()

# --- 7. DATA FETCH ---
def load_csv(name):
    path = name if os.path.exists(name) else os.path.join("SLDC monitor", name)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None

try:
    pm = load_csv('plant_master.csv')
    fix_load = load_csv('Fix load.csv')
    fmt = load_csv('format.csv')

    if pm is None or fix_load is None:
        st.error("⚠️ DATA FILES MISSING: Please ensure plant_master.csv and Fix load.csv are in the GitHub root.")
    else:
        # API URL for Today
        ist_date = ist_now.strftime('%d-%m-%Y')
        url = f"https://www.delhisldc.org/Filesshared/api_response_{ist_date}.json"
        res = requests.get(url, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            rev = data['ResponseBody']['FullSchdRevisionNo']
            st.success(f"✅ CONNECTED | REVISION {rev} | DATE {ist_date}")
            
            # (Insert your process_data function logic here to fill the dataframe)
            # For now, showing a placeholder table to verify layout
            st.dataframe(fmt if fmt is not None else fix_load, use_container_width=True, height=600)
        else:
            st.warning(f"🔄 SLDC Server hasn't published data for {ist_date} yet.")

except Exception as e:
    st.error(f"System Error: {e}")

time.sleep(30)
st.rerun()
