import requests

API_KEY = "8ede0702426bcab31e4e804d36b3b41d538df6ce3063fbf2fd55ea531b0906ec"

WARDS = [
    ("Kothrud", 18.5074, 73.8077),
    ("Hadapsar", 18.5018, 73.9260),
    ("Hinjewadi", 18.5912, 73.7389),
    ("Shivajinagar", 18.5308, 73.8474),
    ("Kharadi", 18.5515, 73.9355),
    ("Aundh", 18.5586, 73.8080),
    ("Katraj", 18.4530, 73.8567),
    ("Wakad", 18.5986, 73.7615),
]

headers = {"x-api-key": API_KEY, "Content-type": "application/json"}

print(f"{'Ward':14} {'AQI':>4} {'PM2.5':>6} {'PM10':>6}  Place")
print("-"*70)
for name, lat, lng in WARDS:
    r = requests.get("https://api.ambeedata.com/latest/by-lat-lng",
                     params={"lat": lat, "lng": lng}, headers=headers)
    if r.status_code == 200:
        s = r.json()["stations"][0]
        print(f"{name:14} {s['AQI']:>4} {s['PM25']:>6} {s['PM10']:>6}  {s.get('placeName','')}")
    else:
        print(f"{name:14} ERROR {r.status_code}")