import os
import requests
from datetime import datetime, timedelta
import xarray as xr
import numpy as np
import json  # Import json module for JSON file generation
import gc

# ------------------------
# SETTINGS
# ------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(script_dir, "GFS_snow")
GRIB_DIR = os.path.join(BASE_DIR, "grib_files")
# write JSON to central dir
JSON_DIR = "/var/data"
os.makedirs(GRIB_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

WHITEFACE_LAT = 44.3659
WHITEFACE_LON = -73.9023

BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
VARIABLE_SNOD = "SNOD"

# Current UTC time offset to last 6 h cycle
current_utc_time = datetime.utcnow() - timedelta(hours=6)
DATE_STR = current_utc_time.strftime("%Y%m%d")
HOUR_STR = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps: every 6 h up to f384
FORECAST_STEPS = list(range(0, 385, 6))  # 0,6,12,…,384

forecast_hours = []
snow_depths = []

# ------------------------
# FUNCTIONS
# ------------------------
def download_file(hour_str, step):
    """Download a GFS 0.25° GRIB2 file for the given forecast step."""
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(GRIB_DIR, file_name)
    url = (
        f"{BASE_URL}"
        f"?dir=%2Fgfs.{DATE_STR}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{VARIABLE_SNOD}=on"
        f"&lev_surface=on"
    )
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(file_path) < 10240:
            print(f"[WARN] {file_name} is too small → removing.")
            os.remove(file_path)
            return None
        return file_path
    else:
        print(f"[ERROR] Failed to download {file_name} (status {response.status_code})")
        return None

def get_snow_depth_at_location(ds, lat, lon):
    """Extract snow depth at the given lat/lon from the dataset."""
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons = np.where(lons > 180, lons - 360, lons)

    if lats.ndim == 2 and lons.ndim == 2:
        distances = np.sqrt((lats - lat)**2 + (lons - lon)**2)
        lat_idx, lon_idx = np.unravel_index(np.argmin(distances), distances.shape)
    elif lats.ndim == 1 and lons.ndim == 1:
        lat_idx = np.abs(lats - lat).argmin()
        lon_idx = np.abs(lons - lon).argmin()
    else:
        raise ValueError("Unexpected latitude/longitude array dimensions.")
    
    return ds['sde'].values[lat_idx, lon_idx] * 39.3701  # meters → inches

# ------------------------
# DOWNLOAD & PROCESS
# ------------------------
for step in FORECAST_STEPS:
    grib_file = download_file(HOUR_STR, step)
    if grib_file:
        ds = xr.open_dataset(grib_file, engine="cfgrib")
        try:
            snow_depth = get_snow_depth_at_location(ds, WHITEFACE_LAT, WHITEFACE_LON)
            forecast_hours.append(step)
            snow_depths.append(max(snow_depth, 0))
        except Exception as e:
            print(f"[ERROR] Processing step {step}: {e}")
        finally:
            ds.close()


hourly_snow = []  # Initialize the list for hourly snowfall rates
accumulated_snow = 0  

for i in range(len(snow_depths)):
    if i == 0 or snow_depths[i] <= snow_depths[i - 1]:  #
        accumulated_snow = 0
        hourly_snow.append(0)
    else:
        increment = max(snow_depths[i] - snow_depths[i - 1], 0)
        accumulated_snow += increment
        hourly_snow.append(accumulated_snow)

# Print hourly snowfall in terminal
print("\nHourly Snowfall Rate at Whiteface Mountain (inches):")
for hour, snow in zip(forecast_hours, hourly_snow):
    print(f"Hour {hour:03d}: {snow:.2f} in")


def generate_snowfall_json(hours, depths):
    """Generate a JSON file with forecast hours and hourly snowfall rates."""
    data = {
        "forecast_hours": [int(hour) for hour in hours],
        "hourly_snowfall_rates": [float(depth) for depth in depths]
    }
    json_path = os.path.join(JSON_DIR, "whiteface_hourly_snow_rate.json")
    with open(json_path, "w") as json_file:
        json.dump(data, json_file, indent=4)
    print(f"Generated snowfall JSON: {json_path}")

# ------------------------
# GENERATE OUTPUT
# ------------------------
if forecast_hours and hourly_snow:
    generate_snowfall_json(forecast_hours, hourly_snow)  # Generate JSON file
else:
    print("No data available to generate the snowfall JSON.")

# ------------------------
# CLEAN UP
# ------------------------
for f in os.listdir(GRIB_DIR):
    os.remove(os.path.join(GRIB_DIR, f))
print("All GRIB files deleted.")

# Free large in-memory structures and trigger GC to reduce memory pressure
try:
    # clear lists
    forecast_hours.clear()
    snow_depths.clear()
    hourly_snow.clear()
except Exception:
    pass
gc.collect()
