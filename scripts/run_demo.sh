#!/bin/bash
# scripts/run_demo.sh — запуск SecureGuard Drift одной командой
set -e
cd "$(dirname "$0")/.."

PORT=8000; REGEN=0
while [[ $# -gt 0 ]]; do
  case $1 in --port) PORT="$2"; shift 2;; --regenerate) REGEN=1; shift;; *) shift;; esac
done

# 1. Python 3.11+
PY=$(command -v python3 || command -v python) || { echo "❌ Python not found"; exit 1; }
VER=$($PY -c "import sys;v=sys.version_info;print(f'{v.major}.{v.minor}')")
MAJ=${VER%%.*}; MIN=${VER##*.}
[[ $MAJ -ge 3 && $MIN -ge 11 ]] || { echo "❌ Python 3.11+ required (found $VER)"; exit 1; }
echo "✅ Python $VER"

# 2. venv
if [ ! -d .venv ]; then
  echo "📦 Creating venv..."
  $PY -m venv .venv
fi
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate

# 3. Dependencies
echo "📦 Installing dependencies..."
pip install -q fastapi uvicorn

# 4. Directories
mkdir -p data reports

# 5. Regenerate if requested
if [ $REGEN -eq 1 ]; then
  echo "🔄 Regenerating data..."
  rm -f data/snapshots.db data/mock_ingress.csv
  [ -f scripts/generate_mock_data.py ] && $PY scripts/generate_mock_data.py
fi

# 6. Start
echo ""
echo "🚀 SecureGuard Drift запущен: http://localhost:$PORT"
exec $PY -m uvicorn api.server:app --host 0.0.0.0 --port "$PORT" --reload
