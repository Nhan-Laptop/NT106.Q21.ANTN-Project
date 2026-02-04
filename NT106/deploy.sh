#!/bin/bash

# ============================================
# DELTA CHAT - NGROK DEPLOYMENT SCRIPT
# ============================================
# Script này giúp deploy Delta Chat với Ngrok
# để mọi người có thể truy cập qua Internet

echo "🚀 Delta Chat - Ngrok Deployment"
echo "================================="
echo ""

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null
then
    echo "❌ Ngrok chưa được cài đặt!"
    echo ""
    echo "Cài đặt Ngrok:"
    echo "1. Download: https://ngrok.com/download"
    echo "2. Hoặc: wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz"
    echo "3. Extract: tar xvzf ngrok-v3-stable-linux-amd64.tgz"
    echo "4. Setup authtoken: ./ngrok authtoken YOUR_TOKEN"
    echo ""
    exit 1
fi

echo "✅ Ngrok đã được cài đặt"
echo ""

# Check if app.py exists
if [ ! -f "app.py" ]; then
    echo "❌ Không tìm thấy app.py. Vui lòng chạy script từ thư mục dự án!"
    exit 1
fi

echo "📋 Kiểm tra dependencies..."

# Check Python packages
python3 << EOF
import sys
required = ['flask', 'flask_socketio', 'boto3', 'cryptography']
missing = []

for package in required:
    try:
        __import__(package)
    except ImportError:
        missing.append(package)

if missing:
    print(f"❌ Thiếu packages: {', '.join(missing)}")
    print("Cài đặt: pip install " + " ".join(missing))
    sys.exit(1)
else:
    print("✅ Tất cả dependencies đã sẵn sàng")
EOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""
echo "🎯 Khởi động Delta Chat..."
echo ""

# Kill existing processes
pkill -f "python.*app.py" 2>/dev/null
pkill -f "ngrok" 2>/dev/null
sleep 2

# Start Flask app in background
echo "▶️  Starting Flask app on port 5000..."
python3 app.py > logs/app.log 2>&1 &
APP_PID=$!
echo "   PID: $APP_PID"

# Wait for app to start
sleep 5

# Check if app is running
if ! ps -p $APP_PID > /dev/null; then
    echo "❌ Flask app failed to start!"
    echo "Check logs/app.log for errors"
    exit 1
fi

echo "✅ Flask app running"
echo ""

# Start ngrok
echo "🌐 Starting Ngrok tunnel..."
ngrok http 5000 > /dev/null &
NGROK_PID=$!
echo "   PID: $NGROK_PID"

# Wait for ngrok to start
sleep 3

# Get ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*\.ngrok[^"]*' | head -1)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Không lấy được Ngrok URL!"
    echo "Kiểm tra: http://localhost:4040"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║          🎉 DELTA CHAT ĐANG CHẠY!                 ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "📡 Public URL:  $NGROK_URL"
echo "🔧 Local URL:   http://localhost:5000"
echo "📊 Ngrok Dashboard: http://localhost:4040"
echo ""
echo "✨ Chia sẻ link trên cho bạn bè để họ có thể:"
echo "   1. Đăng ký tài khoản"
echo "   2. Đăng nhập"
echo "   3. Chat với nhau"
echo ""
echo "💾 PIDs:"
echo "   Flask: $APP_PID"
echo "   Ngrok: $NGROK_PID"
echo ""
echo "🛑 Dừng server: Ctrl+C hoặc:"
echo "   kill $APP_PID $NGROK_PID"
echo ""
echo "📝 Logs: tail -f logs/app.log"
echo ""

# Save PIDs to file for easy cleanup
echo "$APP_PID" > .pids
echo "$NGROK_PID" >> .pids

# Keep script running
echo "⏳ Server đang chạy... (Ctrl+C để dừng)"
echo ""

# Trap Ctrl+C
trap 'echo ""; echo "🛑 Stopping servers..."; kill $APP_PID $NGROK_PID 2>/dev/null; rm .pids 2>/dev/null; echo "✅ Stopped"; exit 0' INT

# Wait
wait
