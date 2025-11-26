import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
import re

# compute script directory and output file
script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, "whiteface_conditions.json")

# Launch browser
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get("https://whiteface.com/mountain/conditions/")

# Wait for page to fully load (adjust if needed)
time.sleep(5)

# Get page source
html = driver.page_source
soup = BeautifulSoup(html, "html.parser")

# Find all divs with class 'main-detail'
details = soup.find_all("div", class_="main-detail")

lines = []
for d in details:
    primary_tag = d.find("span", class_="primary")
    secondary_tag = d.find("span", class_="secondary")

    if primary_tag and secondary_tag:
        primary = primary_tag.get_text(strip=True)
        secondary = secondary_tag.get_text(strip=True)
        line = f"{primary} {secondary}"  # e.g., "14 of 94"
        print(line)
        lines.append(line)

driver.quit()

# Clean and dedupe lines while preserving order
seen = set()
deduped = []
for l in lines:
    if l not in seen:
        seen.add(l)
        deduped.append(l)

# Try to identify date, temperature, lifts and trails
date = None
temperature = None
lifts_raw = None
trails_raw = None

for l in deduped:
    # normalize unicode degree symbol to a single character
    l_norm = l.replace('\u00b0', '°')

    # try parse as date (e.g. "Nov 25 2025" or "November 25 2025")
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            _ = datetime.strptime(l_norm, fmt)
            date = l_norm
            break
        except Exception:
            pass
    if date and date == l_norm:
        continue

    # temperature line contains "F" (with or without degree symbol) or words like "Cloudy"
    if re.search(r'\d+\s*°?\s*[Ff]', l_norm):
        temperature = l_norm
        continue

    # lines like "2 of 11" or "14 of 94"
    if re.match(r'^\d+\s+of\s+\d+', l_norm):
        if lifts_raw is None:
            lifts_raw = l_norm
        elif trails_raw is None:
            trails_raw = l_norm
        continue

# Fallbacks if any piece wasn't found
if not date and deduped:
    # pick first plausible looking token as date if present
    for token in deduped:
        if re.search(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b', token, re.I):
            date = token
            break

if not temperature:
    for token in deduped:
        if 'F' in token or '°' in token:
            temperature = token.replace('\u00b0', '°')
            break

# helper to parse "X of Y" -> {"raw": "X of Y", "open": X, "total": Y}
def parse_of_pair(s):
    m = re.match(r'^\s*(\d+)\s+of\s+(\d+)\s*$', s)
    if not m:
        return None
    return {"raw": s, "open": int(m.group(1)), "total": int(m.group(2))}

lifts = parse_of_pair(lifts_raw) if lifts_raw else None
trails = parse_of_pair(trails_raw) if trails_raw else None

# Build final structured single conditions object
conditions_obj = {
    "date": date,
    "temperature": temperature,
    "lifts": lifts,
    "trails": trails
}

data = {
    "generated_at_utc": datetime.utcnow().isoformat() + "Z",
    "conditions": conditions_obj
}

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(f"Wrote cleaned conditions to: {json_path}")
