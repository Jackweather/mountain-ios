from flask import Flask, render_template, jsonify
import os, json, threading, subprocess, traceback, getpass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# JSON paths
JSON_PATH = os.path.join(BASE_DIR, "Whiteface", "whiteface_conditions.json")
JSON_SNOW_PATH = os.path.join(BASE_DIR, "Whiteface", "GFS_snow", "json_files", "whiteface_hourly_snow_rate.json")
JSON_PRECIP_PATH = os.path.join(BASE_DIR, "Whiteface", "GFS_precip_type", "json_files", "whiteface_precip_type.json")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# Thread-safety
task_lock = threading.Lock()
task_running = False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    if not os.path.exists(JSON_PATH):
        return jsonify({"error": "whiteface_conditions.json not found"}), 404
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return jsonify(payload)

@app.route("/data/snow_rate")
def snow_rate():
    if not os.path.exists(JSON_SNOW_PATH):
        return jsonify({"error": "whiteface_hourly_snow_rate.json not found"}), 404
    with open(JSON_SNOW_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return jsonify(payload)

@app.route("/data/precip_type")
def precip_type():
    if not os.path.exists(JSON_PRECIP_PATH):
        return jsonify({"error": "whiteface_precip_type.json not found"}), 404
    with open(JSON_PRECIP_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return jsonify(payload)

@app.route("/run-task1")
def run_task1():
    global task_running

    with task_lock:
        if task_running:
            return "Task is already running. Please wait until it finishes.", 429
        task_running = True

    def run_all_scripts():
        global task_running
        try:
            print("Flask is running as user:", getpass.getuser())
            scripts = [
               (os.path.join(BASE_DIR, "Whiteface", "Whiteface_GFS_snow.py"), os.path.join(BASE_DIR, "Whiteface")),
               (os.path.join(BASE_DIR, "Whiteface", "Whiteface_GFS_precip_type.py"), os.path.join(BASE_DIR, "Whiteface")),
               (os.path.join(BASE_DIR, "Whiteface", "Whiteface.py"), os.path.join(BASE_DIR, "Whiteface")),
            ]
            for script, cwd in scripts:
                try:
                    result = subprocess.run(
                        ["python", script],
                        check=True,
                        cwd=cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    print(f"{os.path.basename(script)} ran successfully!")
                    print("STDOUT:", result.stdout)
                    print("STDERR:", result.stderr)
                except subprocess.CalledProcessError as e:
                    print(f"Error running {os.path.basename(script)}:\n{traceback.format_exc()}")
                    print("STDOUT:", e.stdout)
                    print("STDERR:", e.stderr)
                except Exception:
                    print(f"Unexpected error running {os.path.basename(script)}:\n{traceback.format_exc()}")
        finally:
            with task_lock:
                task_running = False  # release lock when done

    threading.Thread(target=run_all_scripts).start()
    return "Task started in background! Check logs for output.", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
