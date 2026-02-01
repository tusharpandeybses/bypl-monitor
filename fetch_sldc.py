import requests, json, os
from datetime import datetime, timedelta

def fetch_data():
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    ist_date = ist_now.strftime('%d-%m-%Y')
    url = f"https://www.delhisldc.org/Filesshared/api_response_{ist_date}.json"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=40)
        if res.status_code == 200:
            with open("sldc_data.json", "w") as f:
                json.dump(res.json(), f)
            print("Successfully saved sldc_data.json")
    except Exception as e:
        print(f"Error: {e}")
        if not os.path.exists("sldc_data.json"):
            with open("sldc_data.json", "w") as f: json.dump({"error": "Offline"}, f)

if __name__ == "__main__":
    fetch_data()
