import requests, json, os
from datetime import datetime, timedelta

def fetch_data():
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    ist_date = ist_now.strftime('%d-%m-%Y')
    target_url = f"https://www.delhisldc.org/Filesshared/api_response_{ist_date}.json"
    
    # We use a proxy to bypass the GitHub IP block
    proxy_url = f"https://api.allorigins.win/get?url={target_url}"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        print(f"Fetching via proxy: {ist_date}...")
        res = requests.get(proxy_url, headers=headers, timeout=40)
        
        if res.status_code == 200:
            # The proxy wraps the data in a 'contents' key
            raw_data = res.json().get('contents')
            if raw_data:
                final_json = json.loads(raw_data)
                with open("sldc_data.json", "w") as f:
                    json.dump(final_json, f)
                print("✅ Successfully saved sldc_data.json via Proxy")
                return True
        print(f"❌ Proxy failed. Status: {res.status_code}")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    
    return False

if __name__ == "__main__":
    fetch_data()
