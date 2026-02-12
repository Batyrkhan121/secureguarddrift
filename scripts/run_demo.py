"""scripts/run_demo.py — запуск SecureGuard Drift (Windows/Linux/macOS)."""
import argparse
import os
import subprocess
import sys
try:
    import venv
except ImportError:
    sys.exit("Module 'venv' not found. On Ubuntu/Debian: sudo apt install python3-venv")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# 1. Python 3.11+
if sys.version_info < (3, 11):
    sys.exit("Python 3.11+ required (found %d.%d)" % sys.version_info[:2])
print("Python %d.%d — OK" % sys.version_info[:2])

# CLI
ap = argparse.ArgumentParser(description="SecureGuard Drift demo launcher")
ap.add_argument("--port", type=int, default=8000)
ap.add_argument("--regenerate", action="store_true")
args = ap.parse_args()

# 2. venv
VENV = os.path.join(ROOT, ".venv")
BIN = os.path.join(VENV, "Scripts" if os.name == "nt" else "bin")
PY = os.path.join(BIN, "python.exe" if os.name == "nt" else "python")
PIP = os.path.join(BIN, "pip")
if not os.path.isdir(VENV):
    print("Creating venv...")
    venv.create(VENV, with_pip=True)

# 3. Dependencies
try:
    subprocess.run([PY, "-c", "import fastapi, uvicorn"], check=True, capture_output=True)
    print("Dependencies — OK")
except subprocess.CalledProcessError:
    print("Installing dependencies...")
    subprocess.run([PIP, "install", "-q", "fastapi", "uvicorn"], check=True)

# 4. Directories
os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)

# 5. Regenerate
if args.regenerate:
    print("Regenerating data...")
    for name in ("snapshots.db", "mock_ingress.csv"):
        p = os.path.join(ROOT, "data", name)
        if os.path.exists(p):
            os.remove(p)

# 6. Start server
print("\nSecureGuard Drift: http://localhost:%d" % args.port)
try:
    subprocess.run([PY, "-m", "uvicorn", "api.server:app",
                    "--host", "0.0.0.0", "--port", str(args.port)])
except KeyboardInterrupt:
    print("\nServer stopped.")
