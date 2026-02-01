import requests
import json
from datetime import datetime, timedelta
import os

def fetch_data():
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    ist_date = ist_now.strftime('%d-%m-%Y')
    url = f"https://www.delhisldc.org/Filesshared/api_response_{ist_date}.json"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code == 200:
            with open("sldc_data.json", "w") as f:
                json.dump(res.json(), f)
            print(f"Successfully updated sldc_data.json for {ist_date}")
        else:
            print(f"Failed to fetch. Status: {res.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_data()
