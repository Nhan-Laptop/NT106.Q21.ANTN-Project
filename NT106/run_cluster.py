#!/usr/bin/env python3
"""
Script để chạy cluster với Load Balancer tự chế
Không xài Nginx/HAProxy - TỰ CODE 100%
"""

import os
import sys
import time
import signal
import subprocess
from core.load_balancer import LoadBalancer, TCPLoadBalancer

# Danh sách các process
processes = []

def start_backend_instance(port, tcp_port, instance_id):
    """Start a Flask backend instance"""
    env = os.environ.copy()
    env['PORT'] = str(port)
    env['TCP_PORT'] = str(tcp_port)
    env['INSTANCE_ID'] = str(instance_id)
    
    process = subprocess.Popen(
        [sys.executable, 'app.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    processes.append(process)
    print(f"✓ Started instance {instance_id} on Flask:{port} TCP:{tcp_port} (PID: {process.pid})")
    return process

def signal_handler(sig, frame):
    """Graceful shutdown"""
    print("\n\n🛑 Shutting down cluster...")
    for process in processes:
        process.terminate()
    sys.exit(0)

def main():
    print("="*70)
    print("  DELTA CHAT LOAD BALANCED CLUSTER")
    print("  TỰ CODE LOAD BALANCER - KHÔNG XÀI NGINX/HAPROXY")
    print("="*70)
    print()
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start backend instances
    print("📦 Starting backend instances...")
    print()
    
    backends = [
        {'flask_port': 5001, 'tcp_port': 9991, 'weight': 3, 'id': 1},
        {'flask_port': 5002, 'tcp_port': 9992, 'weight': 2, 'id': 2},
        {'flask_port': 5003, 'tcp_port': 9993, 'weight': 1, 'id': 3},
    ]
    
    for backend in backends:
        start_backend_instance(backend['flask_port'], backend['tcp_port'], backend['id'])
        time.sleep(1)  # Give time to start
    
    print()
    print("⏳ Waiting for backends to initialize...")
    time.sleep(3)
    
    # Start HTTP Load Balancer
    print()
    print("🔀 Starting HTTP Load Balancer...")
    http_lb = LoadBalancer(listen_host='0.0.0.0', listen_port=8000)
    
    for backend in backends:
        http_lb.add_backend('127.0.0.1', backend['flask_port'], weight=backend['weight'])
    
    print()
    print("🔀 Starting TCP Load Balancer...")
    tcp_lb = TCPLoadBalancer(listen_host='0.0.0.0', listen_port=9000)
    
    for backend in backends:
        tcp_lb.add_backend('127.0.0.1', backend['tcp_port'])
    
    print()
    print("="*70)
    print("✅ CLUSTER READY!")
    print("="*70)
    print()
    print("📊 Access Points:")
    print(f"   HTTP Load Balancer:  http://0.0.0.0:8000")
    print(f"   TCP Load Balancer:   tcp://0.0.0.0:9000")
    print()
    print("🎯 Backend Instances:")
    for backend in backends:
        print(f"   Instance {backend['id']}: Flask:{backend['flask_port']} TCP:{backend['tcp_port']} Weight:{backend['weight']}")
    print()
    print("🔍 Algorithm: Weighted Round-Robin")
    print("🏥 Health Check: Every 5 seconds")
    print("⚡ Automatic Failover: Enabled")
    print()
    print("="*70)
    print("Press Ctrl+C to shutdown cluster")
    print("="*70)
    print()
    
    # Start load balancers in threads
    import threading
    
    http_thread = threading.Thread(target=http_lb.start, daemon=False)
    tcp_thread = threading.Thread(target=tcp_lb.start, daemon=False)
    
    http_thread.start()
    tcp_thread.start()
    
    # Stats monitor
    try:
        while True:
            time.sleep(10)
            stats = http_lb.get_stats()
            print(f"\n📈 Stats: {stats['total_requests']} requests, {stats['total_failures']} failures, uptime: {stats['uptime_seconds']:.0f}s")
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == '__main__':
    main()
