from flask import Flask, render_template, jsonify, make_response
import os, json
import threading, subprocess, traceback, getpass, sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Look for the JSON inside /var/data
JSON_BASE = "/var/data"
JSON_PATH = os.path.join(JSON_BASE, "whiteface_conditions.json")
JSON_SNOW_PATH = os.path.join(JSON_BASE, "whiteface_hourly_snow_rate.json")
JSON_PRECIP_PATH = os.path.join(JSON_BASE, "whiteface_precip_type.json")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    if not os.path.exists(JSON_PATH):
        return jsonify({"error": "whiteface_conditions.json not found"}), 404
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    resp = make_response(jsonify(payload))
    # prevent client caching and expose mtime
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    try:
        mtime = datetime.utcfromtimestamp(os.path.getmtime(JSON_PATH)).isoformat() + "Z"
        resp.headers["X-File-Mtime"] = mtime
    except Exception:
        pass
    return resp

# New route: hourly snow rate
@app.route("/data/snow_rate")
def snow_rate():
    if not os.path.exists(JSON_SNOW_PATH):
        return jsonify({"error": "whiteface_hourly_snow_rate.json not found"}), 404
    with open(JSON_SNOW_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    try:
        mtime = datetime.utcfromtimestamp(os.path.getmtime(JSON_SNOW_PATH)).isoformat() + "Z"
        resp.headers["X-File-Mtime"] = mtime
    except Exception:
        pass
    return resp

# New route: precip type
@app.route("/data/precip_type")
def precip_type():
    if not os.path.exists(JSON_PRECIP_PATH):
        return jsonify({"error": "whiteface_precip_type.json not found"}), 404
    with open(JSON_PRECIP_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    try:
        mtime = datetime.utcfromtimestamp(os.path.getmtime(JSON_PRECIP_PATH)).isoformat() + "Z"
        resp.headers["X-File-Mtime"] = mtime
    except Exception:
        pass
    return resp

# Add a global lock so only one background run-task1 can execute at a time
TASK_LOCK = threading.Lock()

@app.route("/run-task1")
def run_task1():
    # Try to acquire lock without blocking; if already held, return conflict
    if not TASK_LOCK.acquire(blocking=False):
        return "Task already running", 409

    def run_all_scripts():
        try:
            print("Flask is running as user:", getpass.getuser())  # Print user for debugging
            scripts = [
                # Use the required absolute paths under /opt/render
                ("/opt/render/project/src/Whiteface/Whiteface_Snow_rate.py", "/opt/render/project/src/Whiteface"),
                ("/opt/render/project/src/Whiteface/Whiteface_precip_type.py", "/opt/render/project/src/Whiteface"),
                
            ]
            for script, cwd in scripts:
                if not os.path.exists(script):
                    print(f"Script not found, skipping: {script}")
                    continue
                try:
                    result = subprocess.run(
                        [sys.executable, script],
                        check=True, cwd=cwd,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    print(f"{os.path.basename(script)} ran successfully!")
                    print("STDOUT:", result.stdout)
                    print("STDERR:", result.stderr)
                except subprocess.CalledProcessError as e:
                    error_trace = traceback.format_exc()
                    print(f"Error running {os.path.basename(script)}:\n{error_trace}")
                    print("STDOUT:", e.stdout)
                    print("STDERR:", e.stderr)
                except Exception:
                    # catch-all so a failure doesn't stop remaining scripts
                    error_trace = traceback.format_exc()
                    print(f"Unexpected error running {os.path.basename(script)}:\n{error_trace}")
        finally:
            # Always release the lock so future requests can run
            try:
                TASK_LOCK.release()
            except Exception:
                pass

    t = threading.Thread(target=run_all_scripts, daemon=True)
    t.start()
    return "Task started in background! Check logs folder for output.", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
