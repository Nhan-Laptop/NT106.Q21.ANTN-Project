#!/bin/bash
# Script dừng cluster và giải phóng ports

echo "🛑 Stopping Delta Chat Cluster..."

# Kill Python processes
echo "📦 Stopping Python app instances..."
pkill -f "run_cluster.py" 2>/dev/null
pkill -f "python.*app.py" 2>/dev/null
sleep 2

# Kill processes as root if needed
sudo pkill -9 -f "python.*app.py" 2>/dev/null
sudo pkill -9 -f "run_cluster" 2>/dev/null

# Stop Docker containers if running
echo "🐳 Stopping Docker containers (if any)..."
sudo docker stop deltachat_loadbalancer deltachat_backend_1 deltachat_backend_2 deltachat_backend_3 deltachat_websocket deltachat_nginx 2>/dev/null

echo ""
echo "✅ Cluster stopped!"
echo ""
echo "🔍 Verifying ports..."
if sudo lsof -i :8000 -i :9000 2>/dev/null; then
    echo "⚠️  WARNING: Ports still in use!"
else
    echo "✅ Ports 8000 and 9000 are free"
fi
