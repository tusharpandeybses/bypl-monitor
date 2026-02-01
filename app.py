import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta

st.set_page_config(page_title="BYPL Dashboard", layout="wide")

def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# --- 1. THE CALCULATION ENGINE (FIXED MATCHING) ---
def clean_key(text):
    return str(text).replace(" ", "").replace("_", "").upper().strip()

def process_sldc_data(api_json):
    try:
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
                
                # IMPROVED MATCHING: Look for keywords if direct match fails
                sldc_name = rldc_map.get(seller)
                if not sldc_name:
                    if "ALFANR" in seller: sldc_name = "ALFANR_II"
                    elif "SECI" in seller: sldc_name = "SECI_BYPL"
                    elif "TEHRI" in seller: sldc_name = "TEHRIPSP"

                if sldc_name and (sldc_name in results or sldc_name == "TEHRIPSP"):
                    share = 1.0 if buyer == "BYPL" else (float(ent_map.get(sldc_name, 0))/100.0 if buyer == "DELHI" else 0)
                    if share <= 0: continue
                    
                    sd = item.get('FullScheduleData', {})
                    isgs = sd.get('ISGSFullScheduleJsonData', {})
                    mw = [0.0]*96
                    
                    if isgs:
                        for k in ['ISGSThermalFullScheduleJsonData', 'ISGSHydroFullScheduleJsonData', 'ISGSGasFullScheduleJsonData']:
                            sub = isgs.get(k)
                            if sub: 
                                schd = sub.get('TotalDrwBoundarySchdAmount') or sub.get('SchdAmount')
                                if schd: mw = schd
                    else:
                        mw = sd.get('OAFullScheduleJsonData', {}).get('SchdAmount', [0.0]*96)
                    
                    for i in range(min(len(mw), 96)):
                        val = round(float(mw[i]) * share, 2)
                        if sldc_name == "TEHRIPSP":
                            if val < 0: results["TEHRIPSP_P"][i] += val
                            else: results["TEHRIPSP"][i] += val
                        elif sldc_name in results:
                            results[sldc_name][i] += val
        
        final_df = pd.read_csv('format.csv') if os.path.exists('format.csv') else pd.DataFrame({'Period': range(1, 97)})
        for col in plant_cols:
            if col in results: final_df[col] = results[col]
        return final_df
    except Exception as e:
        st.error(f"Processing Error: {e}")
        return None

# --- 2. UI RENDER ---
ist_now = get_ist_time()
st.title("⚡ BYPL Intraday Control Room")
st.write(f"IST Time: {ist_now.strftime('%H:%M:%S')}")

if os.path.exists("sldc_data.json"):
    with open("sldc_data.json", "r") as f:
        api_data = json.load(f)
    
    if "error" in api_data:
        st.error("⚠️ Data bridge is active but SLDC website is currently timing out.")
    else:
        rev = api_data.get('ResponseBody', {}).get('FullSchdRevisionNo', 'N/A')
        st.success(f"✅ Data Active | Revision: {rev}")
        df = process_sldc_data(api_data)
        if df is not None:
            st.dataframe(df, use_container_width=True, height=600)
else:
    st.warning("🔄 Waiting for GitHub Action to sync data...")
