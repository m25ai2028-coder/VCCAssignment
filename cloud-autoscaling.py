import psutil
import subprocess
import time
import tempfile
import os

PROJECT_ID = "vcc-assignment3-saumyadhi"
ZONE = "asia-south1-a"
INSTANCE_NAME = "Saumyadhi-VM-Autoscaling"
MACHINE_TYPE = "e2-micro"
IMAGE_FAMILY = "ubuntu-2204-lts"
IMAGE_PROJECT = "ubuntu-os-cloud"
THRESHOLD = 75.0
CHECK_INTERVAL = 30  # seconds


def check_system_health():
    cpu = psutil.cpu_percent(interval=2)
    mem = psutil.virtual_memory().percent
    return cpu, mem


def is_vm_alive():
    result = subprocess.run(
        ["gcloud", "compute", "instances", "describe", INSTANCE_NAME,
         "--zone", ZONE, "--project", PROJECT_ID],
        capture_output=True
    )
    return result.returncode == 0


def spin_up_vm():
    print(f"[ALERT] Usage > {THRESHOLD}%. Launching cloud instance...")

    startup_script = """#!/bin/bash
cat << 'EOF' > /home/app.py
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<h1>Auto-Scaled GCP Instance is Running!</h1><BR><h2>VCC Assignment3 completed")
    def log_message(self, format, *args):
        pass

server = HTTPServer(('0.0.0.0', 8088), Handler)
server.serve_forever()
EOF
python3 /home/app.py &
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(startup_script)
        tmp_path = f.name

    subprocess.run([
        "gcloud", "compute", "instances", "create", INSTANCE_NAME,
        "--project", PROJECT_ID,
        "--zone", ZONE,
        "--machine-type", MACHINE_TYPE,
        "--image-family", IMAGE_FAMILY,
        "--image-project", IMAGE_PROJECT,
        "--tags", "http-server",
        "--no-service-account",
        "--no-scopes",
        "--metadata-from-file", f"startup-script={tmp_path}"
    ])

    os.unlink(tmp_path)

    result = subprocess.run([
        "gcloud", "compute", "instances", "describe", INSTANCE_NAME,
        "--zone", ZONE,
        "--project", PROJECT_ID,
        "--format=get(networkInterfaces[0].accessConfigs[0].natIP)"
    ], capture_output=True, text=True)

    external_ip = result.stdout.strip()
    print(f"[INFO] Instance '{INSTANCE_NAME}' is up and running.")
    print(f"[INFO] Access it here: http://{external_ip}:8088")


def shut_down_vm():
    print(f"[INFO] Usage below {THRESHOLD}%. Shutting down cloud instance...")
    subprocess.run([
        "gcloud", "compute", "instances", "delete", INSTANCE_NAME,
        "--zone", ZONE, "--project", PROJECT_ID, "--quiet"
    ])
    print(f"[INFO] Instance '{INSTANCE_NAME}' removed.")


if __name__ == "__main__":
    print("Starting smart auto-scaler...")

    while True:
        cpu, mem = check_system_health()
        print(f"CPU: {cpu}% | Memory: {mem}%")

        vm_running = is_vm_alive()

        if (cpu > THRESHOLD or mem > THRESHOLD) and not vm_running:
            spin_up_vm()

        elif cpu < THRESHOLD and mem < THRESHOLD and vm_running:
            shut_down_vm()

        else:
            if vm_running:
                print("[OK] Instance already running. No action needed.")
            else:
                print("[OK] System stable. No instance required.")

        time.sleep(CHECK_INTERVAL)