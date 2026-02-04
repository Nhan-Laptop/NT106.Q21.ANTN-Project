"""
Custom Load Balancer - Tự code không xài Nginx/HAProxy
Implements: Round-Robin, Weighted Round-Robin, Health Checks
"""

import socket
import threading
import time
import json
import requests
from datetime import datetime
from collections import deque
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BackendServer:
    """Represents a backend server instance"""
    
    def __init__(self, host, port, weight=1):
        self.host = host
        self.port = port
        self.weight = weight
        self.healthy = True
        self.connections = 0
        self.total_requests = 0
        self.failed_checks = 0
        self.last_check = None
        
    def __repr__(self):
        status = "✓" if self.healthy else "✗"
        return f"{status} {self.host}:{self.port} (weight={self.weight}, conn={self.connections})"


class LoadBalancer:
    """
    Custom Load Balancer implementation
    - Round-Robin algorithm
    - Health checks
    - Connection pooling
    """
    
    def __init__(self, listen_host='0.0.0.0', listen_port=8000):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.backends = []
        self.current_backend_index = 0
        self.lock = threading.Lock()
        self.running = False
        self.stats = {
            'total_requests': 0,
            'total_failures': 0,
            'start_time': None
        }
        
    def add_backend(self, host, port, weight=1):
        """Add a backend server to the pool"""
        backend = BackendServer(host, port, weight)
        self.backends.append(backend)
        logger.info(f"Added backend: {backend}")
        
    def get_next_backend(self):
        """
        Round-Robin with Weight support
        Server với weight=3 sẽ được chọn 3 lần liên tiếp
        """
        with self.lock:
            if not self.backends:
                return None
            
            # Filter healthy backends
            healthy_backends = [b for b in self.backends if b.healthy]
            if not healthy_backends:
                logger.error("No healthy backends available!")
                return None
            
            # Weighted Round-Robin
            # Create weighted list: [server1, server1, server1, server2, server2, ...]
            weighted_list = []
            for backend in healthy_backends:
                weighted_list.extend([backend] * backend.weight)
            
            # Round-robin through weighted list
            backend = weighted_list[self.current_backend_index % len(weighted_list)]
            self.current_backend_index += 1
            
            return backend
    
    def check_health(self, backend):
        """Health check for a backend server"""
        try:
            url = f"http://{backend.host}:{backend.port}/health"
            response = requests.get(url, timeout=2)
            
            if response.status_code == 200:
                backend.healthy = True
                backend.failed_checks = 0
                backend.last_check = datetime.now()
                return True
            else:
                backend.failed_checks += 1
        except Exception as e:
            backend.failed_checks += 1
            logger.warning(f"Health check failed for {backend}: {e}")
        
        # Mark as unhealthy after 3 consecutive failures
        if backend.failed_checks >= 3:
            backend.healthy = False
            logger.error(f"Backend marked unhealthy: {backend}")
        
        backend.last_check = datetime.now()
        return False
    
    def health_check_loop(self):
        """Background thread for health checking"""
        while self.running:
            for backend in self.backends:
                self.check_health(backend)
            time.sleep(5)  # Check every 5 seconds
    
    def handle_http_connection(self, client_socket, client_addr):
        """Handle HTTP request and proxy to backend"""
        try:
            # Receive request from client
            request_data = b''
            client_socket.settimeout(5)
            
            while True:
                try:
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        break
                    request_data += chunk
                    
                    # Check if we have complete HTTP request
                    if b'\r\n\r\n' in request_data:
                        # Check Content-Length for POST requests
                        headers_end = request_data.find(b'\r\n\r\n')
                        headers = request_data[:headers_end].decode('utf-8', errors='ignore')
                        
                        if 'Content-Length:' in headers:
                            for line in headers.split('\r\n'):
                                if line.startswith('Content-Length:'):
                                    content_length = int(line.split(':')[1].strip())
                                    body_received = len(request_data) - (headers_end + 4)
                                    
                                    if body_received >= content_length:
                                        break
                        else:
                            break
                except socket.timeout:
                    break
            
            if not request_data:
                client_socket.close()
                return
            
            # Get backend server
            backend = self.get_next_backend()
            if not backend:
                client_socket.sendall(b'HTTP/1.1 503 Service Unavailable\r\n\r\n')
                client_socket.close()
                self.stats['total_failures'] += 1
                return
            
            # Connect to backend
            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.settimeout(10)
            
            try:
                backend_socket.connect((backend.host, backend.port))
                backend.connections += 1
                backend.total_requests += 1
                self.stats['total_requests'] += 1
                
                # Forward request to backend
                backend_socket.sendall(request_data)
                
                # Receive response from backend and forward to client
                while True:
                    response_data = backend_socket.recv(4096)
                    if not response_data:
                        break
                    client_socket.sendall(response_data)
                
                backend.connections -= 1
                
            except Exception as e:
                logger.error(f"Error proxying to {backend}: {e}")
                client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                backend.healthy = False
                self.stats['total_failures'] += 1
            finally:
                backend_socket.close()
                
        except Exception as e:
            logger.error(f"Error handling connection from {client_addr}: {e}")
        finally:
            client_socket.close()
    
    def start(self):
        """Start the load balancer"""
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        # Start health check thread
        health_thread = threading.Thread(target=self.health_check_loop, daemon=True)
        health_thread.start()
        logger.info("Health check thread started")
        
        # Start HTTP server
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.listen_host, self.listen_port))
        server_socket.listen(100)
        
        logger.info(f"Load Balancer listening on {self.listen_host}:{self.listen_port}")
        logger.info(f"Backend servers: {len(self.backends)}")
        for backend in self.backends:
            logger.info(f"  - {backend}")
        
        try:
            while self.running:
                client_socket, client_addr = server_socket.accept()
                
                # Handle in new thread
                client_thread = threading.Thread(
                    target=self.handle_http_connection,
                    args=(client_socket, client_addr),
                    daemon=True
                )
                client_thread.start()
                
        except KeyboardInterrupt:
            logger.info("Shutting down load balancer...")
        finally:
            server_socket.close()
            self.running = False
    
    def get_stats(self):
        """Get load balancer statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds() if self.stats['start_time'] else 0
        
        return {
            'uptime_seconds': uptime,
            'total_requests': self.stats['total_requests'],
            'total_failures': self.stats['total_failures'],
            'backends': [
                {
                    'address': f"{b.host}:{b.port}",
                    'healthy': b.healthy,
                    'weight': b.weight,
                    'connections': b.connections,
                    'total_requests': b.total_requests,
                    'last_check': b.last_check.isoformat() if b.last_check else None
                }
                for b in self.backends
            ]
        }


class TCPLoadBalancer:
    """
    Load Balancer for TCP connections (for Messenger)
    Simple round-robin for TCP streams
    """
    
    def __init__(self, listen_host='0.0.0.0', listen_port=9000):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.backends = []
        self.current_index = 0
        self.lock = threading.Lock()
        self.running = False
        
    def add_backend(self, host, port):
        """Add TCP backend"""
        backend = {'host': host, 'port': port, 'healthy': True}
        self.backends.append(backend)
        logger.info(f"Added TCP backend: {host}:{port}")
    
    def get_next_backend(self):
        """Simple round-robin"""
        with self.lock:
            if not self.backends:
                return None
            
            backend = self.backends[self.current_index % len(self.backends)]
            self.current_index += 1
            return backend
    
    def handle_tcp_connection(self, client_socket, client_addr):
        """Proxy TCP connection to backend"""
        try:
            backend = self.get_next_backend()
            if not backend:
                client_socket.close()
                return
            
            # Connect to backend
            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.connect((backend['host'], backend['port']))
            
            # Bidirectional forwarding
            def forward(source, destination):
                try:
                    while True:
                        data = source.recv(4096)
                        if not data:
                            break
                        destination.sendall(data)
                except:
                    pass
                finally:
                    source.close()
                    destination.close()
            
            # Create two threads for bidirectional communication
            t1 = threading.Thread(target=forward, args=(client_socket, backend_socket), daemon=True)
            t2 = threading.Thread(target=forward, args=(backend_socket, client_socket), daemon=True)
            
            t1.start()
            t2.start()
            
            t1.join()
            t2.join()
            
        except Exception as e:
            logger.error(f"TCP proxy error: {e}")
            client_socket.close()
    
    def start(self):
        """Start TCP load balancer"""
        self.running = True
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.listen_host, self.listen_port))
        server_socket.listen(100)
        
        logger.info(f"TCP Load Balancer listening on {self.listen_host}:{self.listen_port}")
        
        try:
            while self.running:
                client_socket, client_addr = server_socket.accept()
                
                # Handle in new thread
                client_thread = threading.Thread(
                    target=self.handle_tcp_connection,
                    args=(client_socket, client_addr),
                    daemon=True
                )
                client_thread.start()
                
        except KeyboardInterrupt:
            logger.info("Shutting down TCP load balancer...")
        finally:
            server_socket.close()
            self.running = False


if __name__ == '__main__':
    """
    Test the load balancer
    """
    # HTTP Load Balancer
    lb = LoadBalancer(listen_host='0.0.0.0', listen_port=8000)
    
    # Add backend servers (example)
    lb.add_backend('127.0.0.1', 5001, weight=3)
    lb.add_backend('127.0.0.1', 5002, weight=2)
    lb.add_backend('127.0.0.1', 5003, weight=1)
    
    print("\n" + "="*60)
    print("CUSTOM LOAD BALANCER - Tự code không xài Nginx")
    print("="*60)
    print(f"HTTP Proxy: http://0.0.0.0:8000 → Backends")
    print("Algorithm: Weighted Round-Robin")
    print("Health Check: Every 5 seconds")
    print("="*60 + "\n")
    
    lb.start()
