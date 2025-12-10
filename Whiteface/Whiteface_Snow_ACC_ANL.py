import os
import requests
from datetime import datetime, timedelta
import xarray as xr
import numpy as np
import json
import gc

# ------------------------
# SETTINGS
# ------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(script_dir, "GFS_snow_anl")
GRIB_DIR = os.path.join(BASE_DIR, "grib_files")
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

# Forecast steps: every 6 h up to f384
FORECAST_STEPS = list(range(0, 385, 6))  # 0,6,12,…,384

def download_file(hour_str, step):
    """Download a GFS 0.25° GRIB2 forecast file for the given forecast step requesting SNOD at surface."""
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(GRIB_DIR, file_name)
    url = (
        f"{BASE_URL}"
        f"?dir=%2Fgfs.{DATE_STR}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{VARIABLE_SNOD}=on"
        f"&lev_surface=on"
    )
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        with open(file_path, "wb") as fh:
            for chunk in r.iter_content(1024):
                if chunk:
                    fh.write(chunk)
        if os.path.getsize(file_path) < 10240:
            print(f"[WARN] {file_name} too small → removing.")
            os.remove(file_path)
            return None
        return file_path
    else:
        print(f"[ERROR] failed to download {file_name} (status {r.status_code})")
        return None

def find_snow_var(ds):
    for name in ds.data_vars:
        lname = name.lower()
        if "sno" in lname or "sde" in lname or "snod" in lname:
            return name
    return list(ds.data_vars.keys())[0]

def get_snow_depth_at_location(ds, varname, lat, lon):
    """Return snow depth at nearest grid point in inches."""
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons = np.where(lons > 180, lons - 360, lons)

    if lats.ndim == 2 and lons.ndim == 2:
        d = np.sqrt((lats - lat)**2 + (lons - lon)**2)
        lat_idx, lon_idx = np.unravel_index(np.argmin(d), d.shape)
    elif lats.ndim == 1 and lons.ndim == 1:
        lat_idx = np.abs(lats - lat).argmin()
        lon_idx = np.abs(lons - lon).argmin()
    else:
        raise ValueError("Unexpected lat/lon array dimensions.")

    arr = np.squeeze(ds[varname].values)
    # handle shapes: (lat, lon) or (time, lat, lon)
    if arr.ndim == 2:
        val_m = float(arr[lat_idx, lon_idx])
    elif arr.ndim >= 3:
        # take first time/index if present (forecast files typically have single field)
        val_m = float(arr[0, lat_idx, lon_idx]) if arr.shape[0] > 0 else float(arr[lat_idx, lon_idx])
    else:
        val_m = float(arr)
    return val_m * 39.3701  # meters -> inches

# ------------------------
# MAIN: download all forecast steps and extract depths
# ------------------------
forecast_hours = []
depths_in = []

for step in FORECAST_STEPS:
    grib = download_file(HOUR_STR, step)
    if not grib:
        continue
    ds = xr.open_dataset(grib, engine="cfgrib")
    try:
        varname = find_snow_var(ds)
        depth = get_snow_depth_at_location(ds, varname, WHITEFACE_LAT, WHITEFACE_LON)
        forecast_hours.append(step)
        depths_in.append(round(max(depth, 0.0), 3))
        print(f"f{step:03d}: snow_depth = {depths_in[-1]} in (var: {varname})")
    except Exception as e:
        print(f"[ERROR] processing f{step:03d}: {e}")
    finally:
        ds.close()

def compute_positive_accum(depths):
    """Compute running positive accumulated total that resets on any zero increment.
       Return only the running totals list (inches)."""
    running = []
    total = 0.0
    accumulating = False
    for i in range(len(depths)):
        if i == 0:
            inc = 0.0
            total = 0.0
            accumulating = False
        else:
            inc = max(depths[i] - depths[i-1], 0.0)
            if inc > 0:
                if not accumulating:
                    total = 0.0
                    accumulating = True
                total += inc
            else:
                total = 0.0
                accumulating = False
        running.append(round(total, 3))
    return running

if forecast_hours and depths_in:
    running = compute_positive_accum(depths_in)
    out = {
        "forecast_hours": [int(h) for h in forecast_hours],
        "running_positive_accum_in": running
    }
    json_path = os.path.join(JSON_DIR, "whiteface_snod_forecast_running_positive_accum_in.json")
    with open(json_path, "w") as jf:
        json.dump(out, jf, indent=2)
    print(f"Generated accumulation JSON (hours + running positive accum): {json_path}")
else:
    print("No forecast snow-depth data available to generate JSON.")

# cleanup GRIB files
for f in os.listdir(GRIB_DIR):
    try:
        os.remove(os.path.join(GRIB_DIR, f))
    except Exception:
        pass
print("All GRIB files deleted.")

# free memory
try:
    forecast_hours.clear()
    depths_in.clear()
except Exception:
    pass
gc.collect()
