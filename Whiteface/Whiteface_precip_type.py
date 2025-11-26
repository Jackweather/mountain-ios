import os
import requests
from datetime import datetime, timedelta
import xarray as xr
import numpy as np
import json

# ------------------------
# SETTINGS
# ------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(script_dir, "GFS_precip_type")
GRIB_DIR = os.path.join(BASE_DIR, "grib_files")
JSON_DIR = os.path.join(BASE_DIR, "json_files")
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(GRIB_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

WHITEFACE_LAT = 44.3659
WHITEFACE_LON = -73.9023

BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
VARIABLE_PRATE = "PRATE"
VARIABLE_CSNOW = "CSNOW"

current_utc_time = datetime.utcnow() - timedelta(hours=6)
DATE_STR = current_utc_time.strftime("%Y%m%d")
HOUR_STR = str(current_utc_time.hour // 6 * 6).zfill(2)

FORECAST_STEPS = list(range(0, 385, 6))

forecast_hours = []
precip_types = []

# ------------------------
# FUNCTIONS
# ------------------------
def download_file(variable, hour_str, step):
    file_name = f"gfs.t{hour_str}z.pgrb2.0p25.f{step:03d}"
    file_path = os.path.join(GRIB_DIR, f"{variable}_{file_name}")
    url = (
        f"{BASE_URL}"
        f"?dir=%2Fgfs.{DATE_STR}%2F{hour_str}%2Fatmos"
        f"&file={file_name}"
        f"&var_{variable}=on"
        f"&lev_surface=on"
    )
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        if os.path.getsize(file_path) < 10240:
            os.remove(file_path)
            return None
        return file_path
    else:
        return None

def get_precip_type(ds, lat, lon):
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

    csnow = ds['csnow'].values[lat_idx, lon_idx] * 3600 if 'csnow' in ds else 0
    prate = ds['prate'].values[lat_idx, lon_idx] * 3600

    if csnow > 0:
        return "snow"
    elif prate > 0:
        return "rain"
    else:
        return "none"

# ------------------------
# DOWNLOAD & PROCESS
# ------------------------
for step in FORECAST_STEPS:
    prate_file = download_file(VARIABLE_PRATE, HOUR_STR, step)
    csnow_file = download_file(VARIABLE_CSNOW, HOUR_STR, step)
    if prate_file and csnow_file:
        try:
            ds_prate = xr.open_dataset(prate_file, engine="cfgrib", filter_by_keys={"stepType": "instant"})
            ds_csnow = xr.open_dataset(csnow_file, engine="cfgrib", filter_by_keys={"stepType": "instant"})
            ds_combined = xr.merge([ds_prate, ds_csnow])
            precip_type = get_precip_type(ds_combined, WHITEFACE_LAT, WHITEFACE_LON)

            forecast_hours.append(step)
            precip_types.append(precip_type)

        except Exception as e:
            print(f"[ERROR] Processing step {step}: {e}")
        finally:
            if 'ds_prate' in locals():
                ds_prate.close()
            if 'ds_csnow' in locals():
                ds_csnow.close()

# ------------------------
# GENERATE JSON FUNCTION
# ------------------------
def generate_precip_type_json(hours, types):
    data = {
        "forecast_hours": hours,
        "precipitation_types": types
    }
    json_path = os.path.join(JSON_DIR, "whiteface_precip_type.json")
    with open(json_path, "w") as json_file:
        json.dump(data, json_file, indent=4)
    print(f"Generated precipitation type JSON: {json_path}")

# ------------------------
# GENERATE OUTPUT
# ------------------------
if forecast_hours and precip_types:
    generate_precip_type_json(forecast_hours, precip_types)
else:
    print("No data available to generate the precipitation type JSON.")
