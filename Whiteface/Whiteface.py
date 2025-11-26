import os
import requests
from bs4 import BeautifulSoup
import json

URL = "https://whiteface.com/mountain/conditions/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
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
}

def fetch_whiteface_conditions():
    r = requests.get(URL, headers=HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    blocks = soup.find_all("div", class_="main-detail")
    
    results = []
    seen = set()  # track duplicates

    for block in blocks:
        primary = block.find("span", class_="primary")
        secondary = block.find("span", class_="secondary")
        if primary and secondary:
            item = (primary.text.strip(), secondary.text.strip())
            if item not in seen:
                seen.add(item)
                results.append({"primary": item[0], "secondary": item[1]})

    return {"conditions": results}

if __name__ == "__main__":
    data = fetch_whiteface_conditions()
    
    # Save JSON in the same folder as Whiteface.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, "whiteface_conditions.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"Data saved to {output_file}")
