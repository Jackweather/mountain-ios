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
BASE_DIR = os.path.join(script_dir, "GFS_temp")
GRIB_DIR = os.path.join(BASE_DIR, "grib_files")
JSON_DIR = "/var/data"
os.makedirs(GRIB_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

WHITEFACE_LAT = 44.3659
WHITEFACE_LON = -73.9023

BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
VARIABLE_TMP = "TMP"

# Current UTC time offset to last 6 h cycle
current_utc_time = datetime.utcnow() - timedelta(hours=6)
DATE_STR = current_utc_time.strftime("%Y%m%d")
HOUR_STR = str(current_utc_time.hour // 6 * 6).zfill(2)

# Forecast steps: every 6 h up to f384 (match snow script)
FORECAST_STEPS = list(range(0, 385, 6))  # 0,6,12,…,384

# ------------------------
# FUNCTIONS
# ------------------------
def download_file(hour_str, step):
    """Download a GFS 0.25° GRIB2 forecast file for the given forecast step requesting TMP at 975 mb."""
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(GRIB_DIR, file_name)
    url = (
        f"{BASE_URL}"
        f"?dir=%2Fgfs.{DATE_STR}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{VARIABLE_TMP}=on"
        f"&lev_975_mb=on"
    )
    resp = requests.get(url, stream=True)
    if resp.status_code == 200:
        with open(file_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    fh.write(chunk)
        if os.path.getsize(file_path) < 10240:
            print(f"[WARN] {file_name} too small → removing.")
            os.remove(file_path)
            return None
        return file_path
    else:
        print(f"[ERROR] Failed to download {file_name} (status {resp.status_code})")
        return None

def find_temp_variable(ds):
    """Find a plausible temperature variable name in the dataset."""
    for name in ds.data_vars:
        lname = name.lower()
        if 'temp' in lname or lname == 't' or 'tmp' in lname:
            return name
    return list(ds.data_vars.keys())[0]

def get_var_at_location(ds, varname, lat, lon):
    """Extract the variable value at the nearest grid point (handles 1D/2D lats/lons and squeezes extra dims)."""
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    lons = np.where(lons > 180, lons - 360, lons)

    # get variable and squeeze trailing singleton dims (e.g. time/step)
    vararr = np.squeeze(ds[varname].values)

    # locate nearest grid point
    if lats.ndim == 2 and lons.ndim == 2:
        distances = np.sqrt((lats - lat)**2 + (lons - lon)**2)
        lat_idx, lon_idx = np.unravel_index(np.argmin(distances), distances.shape)
        if vararr.ndim == 2:
            return vararr[lat_idx, lon_idx]
        # if vararr has leading extra dims after squeeze, select first available 2D slice
        return vararr[..., lat_idx, lon_idx] if vararr.ndim >= 3 else vararr[lat_idx, lon_idx]
    elif lats.ndim == 1 and lons.ndim == 1:
        lat_idx = np.abs(lats - lat).argmin()
        lon_idx = np.abs(lons - lon).argmin()
        if vararr.ndim == 2:
            return vararr[lat_idx, lon_idx]
        # handle e.g. (time, lat, lon) or (level, lat, lon) after squeeze
        if vararr.ndim >= 3:
            return vararr[0, lat_idx, lon_idx]
        if vararr.ndim == 1:
            return vararr[lat_idx]
        return vararr[lat_idx, lon_idx]
    else:
        raise ValueError("Unexpected lat/lon array dimensions.")

# ------------------------
# MAIN
# ------------------------
forecast_hours = []
temps_f = []                     # changed: store Fahrenheit

for step in FORECAST_STEPS:
    grib_file = download_file(HOUR_STR, step)
    if not grib_file:
        continue
    ds = xr.open_dataset(grib_file, engine="cfgrib")
    try:
        varname = find_temp_variable(ds)
        raw_val = get_var_at_location(ds, varname, WHITEFACE_LAT, WHITEFACE_LON)
        # GRIB temperature is typically Kelvin → convert to Fahrenheit
        temp_c = float(raw_val) - 273.15
        temp_f = temp_c * 9.0/5.0 + 32.0
        forecast_hours.append(step)
        temps_f.append(round(temp_f, 2))
        print(f"f{step:03d} 975 mb temp at Whiteface: {temp_f:.2f} °F (variable: {varname})")
    except Exception as e:
        print(f"[ERROR] Processing step f{step:03d}: {e}")
    finally:
        ds.close()

def generate_temp_json(hours, temps):
    data = {
        "forecast_hours": [int(h) for h in hours],
        "temps_975mb_F": [float(t) for t in temps]   # changed key to Fahrenheit
    }
    json_path = os.path.join(JSON_DIR, "whiteface_975mb_temp_F.json")  # changed filename
    with open(json_path, "w") as jf:
        json.dump(data, jf, indent=4)
    print(f"Generated temperature JSON: {json_path}")

if forecast_hours and temps_f:
    generate_temp_json(forecast_hours, temps_f)
else:
    print("No temperature data available to generate JSON.")

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
    temps_f.clear()                # clear Fahrenheit list
except Exception:
    pass
gc.collect()