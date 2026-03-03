import requests
import json
import sys

BASE_URL = "http://127.0.0.1:7010"

def test_smart_fit():
    print("\n[Testing Smart Fit API]")
    url = f"{BASE_URL}/api/recommend/smart_fit"
    payload = {"keywords": ["定位", "滑動"]}
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data['ok'] and data['count'] > 0:
                print(f"✅ Success! Found {data['count']} fits for keywords '定位', '滑動'")
                print(f"   Sample: {data['results'][0]['ansi']} - {data['results'][0]['function']}")
            else:
                print(f"❌ Failed: OK={data.get('ok')}, Count={data.get('count')}")
        else:
            print(f"❌ HTTP Error: {r.status_code}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def test_machine_check():
    print("\n[Testing Machine Check API]")
    url = f"{BASE_URL}/api/recommend/machine_check"
    # Diameter 50mm, Safety Factor 3.0
    # ISO 286 for 50mm: IT7 = 25um
    # Target repeatability = 25um / 3 ~= 8.33um = 0.00833mm
    # Machines with <= 0.00833mm should be returned.
    payload = {"diameter": 50.0, "safety_factor": 3.0}
    
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data['ok'] and data.get('data'):
                res = data['data']
                machines = res['machines']
                print(f"✅ Success! Target Repeatability: {res['target_repeat_mm']:.5f} mm")
                print(f"   Found {len(machines)} capable machines.")
                if len(machines) > 0:
                    print(f"   Sample: {machines[0]['model']} (Repeatability: {machines[0]['repeatability_mm']} mm)")
            else:
                print(f"❌ Failed: Data invalid or empty. Response: {data}")
        else:
            print(f"❌ HTTP Error: {r.status_code}")
            print(r.text)
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    print(f"Targeting: {BASE_URL}")
    test_smart_fit()
    test_machine_check()
