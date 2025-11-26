import os
import requests
import time
import random
from bs4 import BeautifulSoup
import json

URL = "https://whiteface.com/mountain/conditions/"

# Rotate user agents so every request looks different
USER_AGENTS = [
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    # Older Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.90 Safari/537.36",
    # Mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    # Windows Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# Random fake home IPs (purely header spoof — NOT real)
FAKE_IPS = [
    "24.32.44.121",
    "67.82.19.244",
    "12.104.88.54",
    "73.229.115.98",
    "98.14.22.177"
]

def make_headers():
    ua = random.choice(USER_AGENTS)
    fake_ip = random.choice(FAKE_IPS)

    headers = {
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;"
            "q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://google.com",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "X-Forwarded-For": fake_ip,  # FAKE home IP
        "X-Real-IP": fake_ip
    }

    print(f"[DEBUG] Using User-Agent: {ua}")
    print(f"[DEBUG] Using fake IP: {fake_ip}")

    return headers


def fetch_whiteface_conditions():
    session = requests.Session()

    for attempt in range(1, 5):  # try up to 4 times
        try:
            print(f"[DEBUG] Attempt {attempt} — requesting page...")
            headers = make_headers()
            session.headers.update(headers)

            # Random sleep so it looks more human
            delay = random.uniform(1.0, 3.0)
            print(f"[DEBUG] Sleeping {delay:.2f} seconds before request")
            time.sleep(delay)

            response = session.get(URL, timeout=15)

            print(f"[DEBUG] HTTP Status: {response.status_code}")

            if response.status_code == 403:
                print("[DEBUG] Got 403 — retrying with new headers...")
                continue  # try again

            response.raise_for_status()
            html = response.text

            soup = BeautifulSoup(html, "html.parser")
            blocks = soup.find_all("div", class_="main-detail")

            results = []
            seen = set()

            for block in blocks:
                primary = block.find("span", class_="primary")
                secondary = block.find("span", class_="secondary")
                if primary and secondary:
                    item = (primary.text.strip(), secondary.text.strip())
                    if item not in seen:
                        seen.add(item)
                        results.append({"primary": item[0], "secondary": item[1]})

            print(f"[DEBUG] Parsed {len(results)} items from page")
            return {"conditions": results}

        except Exception as e:
            print(f"[DEBUG] Error: {e}")
            print("[DEBUG] Retrying...\n")
            time.sleep(2)

    print("[DEBUG] FAILED after multiple attempts.")
    return {"conditions": []}


if __name__ == "__main__":
    data = fetch_whiteface_conditions()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "whiteface_conditions.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"[DEBUG] Data saved to {output_file}")
