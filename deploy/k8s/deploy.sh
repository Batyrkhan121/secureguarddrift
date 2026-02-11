#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
NO_BUILD=false; PORT_FWD=false
for arg in "$@"; do
  case $arg in
    --no-build)     NO_BUILD=true ;;
    --port-forward) PORT_FWD=true ;;
  esac
done

# 1-2. Check tools
command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl not found"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Error: docker not found"; exit 1; }
echo "kubectl, docker — OK"

# 3. Build image
if [ "$NO_BUILD" = false ]; then
  echo "Building Docker image..."
  docker build -t secureguard-drift:latest -f deploy/Dockerfile .
else
  echo "Skipping build (--no-build)"
fi

# 4. Apply manifests
echo "Applying K8s manifests..."
kubectl apply -f deploy/k8s/

# 5. Wait for pod
echo "Waiting for pod to be ready..."
kubectl wait --for=condition=ready pod -l app=secureguard-drift \
  -n secureguard-drift --timeout=60s

# 6. Done
PF_CMD="kubectl port-forward -n secureguard-drift svc/secureguard-drift 8000:80"
echo "Deployed! Port-forward: $PF_CMD"

# 7. Port-forward
if [ "$PORT_FWD" = false ]; then
  read -rp "Start port-forward now? (y/n) " ans
  [ "$ans" = "y" ] && PORT_FWD=true
fi
[ "$PORT_FWD" = true ] && exec $PF_CMD || true
