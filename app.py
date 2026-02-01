import streamlit as st
import pandas as pd
import requests
import time
import os
import base64
from datetime import datetime, timedelta

# --- 1. CONFIG & WIDE LAYOUT ---
st.set_page_config(page_title="BYPL Control Room Monitor", layout="wide")
USER_ID = "1"; USER_PASS = "1"

# --- 2. INDIAN STANDARD TIME (IST) FIX ---
def get_ist_time():
    # Streamlit servers are in UTC; add 5.5 hours for India
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- 3. ASSET LOADER (LOGO & CHIME) ---
def get_base64_file(bin_file):
    # Checks root and subfolder to avoid "File Not Found" errors
    paths = [bin_file, os.path.join("SLDC monitor", bin_file), bin_file.lower(), bin_file.upper()]
    for p in paths:
        if os.path.exists(p):
            with open(p, 'rb') as f:
                return base64.b64encode(f.read()).decode()
    return None

# --- 4. LOGIN GATE (FORCED START) ---
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
    st.stop() # Prevents further code execution until login

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

# --- 7. DATA FETCH WITH TIMEOUT PROTECTION ---
def load_csv(name):
    path = name if os.path.exists(name) else os.path.join("SLDC monitor", name)
    if os.path.exists(path): return pd.read_csv(path)
    return None

try:
    pm = load_csv('plant_master.csv')
    fix_load = load_csv('Fix load.csv')
    
    if pm is None:
        st.error("⚠️ DATA ERROR: 'plant_master.csv' not found. Please check your GitHub files.")
    else:
        ist_date = ist_now.strftime('%d-%m-%Y')
        url = f"https://www.delhisldc.org/Filesshared/api_response_{ist_date}.json"
        
        # Disguise the request as a real browser to prevent blocks
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        try:
            # Increase timeout to 25 seconds for slow international connections
            res = requests.get(url, headers=headers, timeout=25) 
            if res.status_code == 200:
                data = res.json()
                rev = data['ResponseBody']['FullSchdRevisionNo']
                st.success(f"✅ CONNECTED | REVISION {rev} | DATE {ist_date}")
                
                # Detect Revision Change for Chime
                if "last_rev" not in st.session_state: st.session_state.last_rev = rev
                if rev > st.session_state.last_rev:
                    chime_b64 = get_base64_file("chime.mp3") or get_base64_file("Chime.mp3")
                    if chime_b64:
                        st.markdown(f'<audio autoplay><source src="data:audio/mp3;base64,{chime_b64}"></audio>', unsafe_allow_html=True)
                    st.session_state.last_rev = rev
                
                # Show full dataframe
                st.dataframe(fix_load, use_container_width=True, height=600)
            else:
                st.warning(f"⚠️ SLDC Website reachable, but data for {ist_date} is not yet published.")
        except Exception:
            st.error("🚨 CONNECTION TIMEOUT: SLDC is blocking the cloud request. Retrying in 30s...")

except Exception as e:
    st.error(f"Software Error: {e}")

# Automatically refresh every 30 seconds
time.sleep(30)
st.rerun()
