"""
TCP MESSENGER - Direct P2P messaging using TCP sockets
Thay thế SMTP/IMAP để đơn giản hóa
"""

import socket
import json
import threading
import time
from datetime import datetime

class TCPMessenger:
    def __init__(self, host='0.0.0.0', port=9999):
        """
        Khởi tạo TCP server để nhận tin nhắn
        
        Args:
            host: IP address to bind (0.0.0.0 = all interfaces)
            port: Port number for TCP server
        """
        self.host = host
        self.port = port
        self.running = False
        self.server_thread = None
        self.message_handlers = []
        self.server_socket = None
        
        # Message queue (in-memory)
        self.message_queue = {}  # {user_email: [messages]}
        
        print(f"[TCP] Messenger initialized on {host}:{port}")
    
    def start_server(self):
        """Khởi động TCP server để lắng nghe connections"""
        if self.running:
            print("[TCP] Server already running")
            return
        
        self.running = True
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        print(f"[TCP] Server started on {self.host}:{self.port}")
    
    def stop_server(self):
        """Dừng TCP server"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        print("[TCP] Server stopped")
    
    def _server_loop(self):
        """Main server loop - lắng nghe incoming connections"""
        try:
            # Tạo TCP socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Timeout để check self.running
            
            print(f"[TCP] Listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    # Accept connection
                    client_socket, address = self.server_socket.accept()
                    print(f"[TCP] Connection from {address}")
                    
                    # Handle trong thread riêng
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    continue  # Timeout để check self.running flag
                except Exception as e:
                    if self.running:
                        print(f"[TCP ERROR] {e}")
                    break
        
        except Exception as e:
            print(f"[TCP ERROR] Server loop: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
            print("[TCP] Server loop ended")
    
    def _handle_client(self, client_socket, address):
        """Xử lý request từ client"""
        try:
            # Nhận data (max 4KB)
            data = client_socket.recv(4096).decode('utf-8')
            
            if not data:
                return
            
            # Parse JSON
            message_data = json.loads(data)
            
            # Lưu vào message queue
            recipient = message_data.get('recipient')
            if recipient:
                if recipient not in self.message_queue:
                    self.message_queue[recipient] = []
                
                # Thêm timestamp
                message_data['timestamp'] = datetime.now().isoformat()
                message_data['delivered'] = True
                
                self.message_queue[recipient].append(message_data)
                
                print(f"[TCP] Message from {message_data.get('sender')} to {recipient}")
                
                # Response OK
                response = json.dumps({"status": "success", "message": "Delivered"})
                client_socket.send(response.encode('utf-8'))
            else:
                response = json.dumps({"status": "error", "message": "No recipient"})
                client_socket.send(response.encode('utf-8'))
        
        except Exception as e:
            print(f"[TCP ERROR] Handle client: {e}")
            try:
                response = json.dumps({"status": "error", "message": str(e)})
                client_socket.send(response.encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()
    
    def send_message(self, sender, recipient, message, encrypted=False):
        """
        Gửi tin nhắn đến recipient qua TCP
        
        Args:
            sender: Email người gửi
            recipient: Email người nhận
            message: Nội dung tin nhắn
            encrypted: Có mã hóa hay không
        
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            # Tạo message packet
            message_data = {
                'sender': sender,
                'recipient': recipient,
                'body': message,
                'encrypted': encrypted,
                'timestamp': datetime.now().isoformat()
            }
            
            # Chuyển thành JSON
            message_json = json.dumps(message_data)
            
            # Kết nối đến server (chính nó hoặc remote)
            # Trong local development, gửi đến chính server này
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5.0)
            
            # Connect to localhost (hoặc remote server nếu deploy)
            client_socket.connect(('127.0.0.1', self.port))
            
            # Gửi data
            client_socket.send(message_json.encode('utf-8'))
            
            # Nhận response
            response = client_socket.recv(1024).decode('utf-8')
            response_data = json.loads(response)
            
            client_socket.close()
            
            if response_data.get('status') == 'success':
                print(f"[TCP] Message sent: {sender} -> {recipient}")
                return True
            else:
                print(f"[TCP ERROR] Send failed: {response_data.get('message')}")
                return False
        
        except Exception as e:
            print(f"[TCP ERROR] Send message: {e}")
            return False
    
    def get_messages(self, user_email, mark_read=True):
        """
        Lấy tin nhắn cho user từ queue
        
        Args:
            user_email: Email của user
            mark_read: Xóa tin nhắn sau khi lấy (default: True)
        
        Returns:
            list: Danh sách tin nhắn
        """
        if user_email not in self.message_queue:
            return []
        
        messages = self.message_queue[user_email].copy()
        
        if mark_read:
            # Xóa tin nhắn đã đọc
            self.message_queue[user_email] = []
        
        return messages
    
    def has_messages(self, user_email):
        """Check xem user có tin nhắn mới không"""
        return user_email in self.message_queue and len(self.message_queue[user_email]) > 0


class UDPMessenger:
    """
    Alternative: UDP implementation (connectionless)
    Nhanh hơn TCP nhưng không đảm bảo delivery
    """
    def __init__(self, host='0.0.0.0', port=9998):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.message_queue = {}
        
        print(f"[UDP] Messenger initialized on {host}:{port}")
    
    def start_server(self):
        """Khởi động UDP server"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._server_loop, daemon=True)
        self.thread.start()
        print(f"[UDP] Server started on {self.host}:{self.port}")
    
    def _server_loop(self):
        """Main UDP server loop"""
        try:
            # Tạo UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(1.0)
            
            print(f"[UDP] Listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    # Nhận datagram
                    data, address = self.socket.recvfrom(4096)
                    
                    # Parse JSON
                    message_data = json.loads(data.decode('utf-8'))
                    
                    # Lưu vào queue
                    recipient = message_data.get('recipient')
                    if recipient:
                        if recipient not in self.message_queue:
                            self.message_queue[recipient] = []
                        
                        message_data['timestamp'] = datetime.now().isoformat()
                        self.message_queue[recipient].append(message_data)
                        
                        print(f"[UDP] Message from {message_data.get('sender')} to {recipient}")
                        
                        # Send ACK (optional)
                        ack = json.dumps({"status": "success"})
                        self.socket.sendto(ack.encode('utf-8'), address)
                
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[UDP ERROR] {e}")
        
        except Exception as e:
            print(f"[UDP ERROR] Server loop: {e}")
        finally:
            if self.socket:
                self.socket.close()
    
    def send_message(self, sender, recipient, message, encrypted=False):
        """Gửi tin nhắn qua UDP"""
        try:
            message_data = {
                'sender': sender,
                'recipient': recipient,
                'body': message,
                'encrypted': encrypted,
                'timestamp': datetime.now().isoformat()
            }
            
            message_json = json.dumps(message_data)
            
            # Tạo UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2.0)
            
            # Gửi datagram
            sock.sendto(message_json.encode('utf-8'), ('127.0.0.1', self.port))
            
            # Đợi ACK (optional)
            try:
                response, _ = sock.recvfrom(1024)
                response_data = json.loads(response.decode('utf-8'))
                print(f"[UDP] Message sent: {sender} -> {recipient}")
                return True
            except socket.timeout:
                print(f"[UDP] No ACK received (but message might be delivered)")
                return True  # UDP không đảm bảo, coi như OK
        
        except Exception as e:
            print(f"[UDP ERROR] Send message: {e}")
            return False
        finally:
            sock.close()
    
    def get_messages(self, user_email, mark_read=True):
        """Lấy tin nhắn từ queue"""
        if user_email not in self.message_queue:
            return []
        
        messages = self.message_queue[user_email].copy()
        
        if mark_read:
            self.message_queue[user_email] = []
        
        return messages


# Test code
if __name__ == '__main__':
    # Test TCP
    print("=== Testing TCP Messenger ===")
    tcp = TCPMessenger(port=9999)
    tcp.start_server()
    
    time.sleep(1)
    
    # Test send
    tcp.send_message(
        sender='alice@example.com',
        recipient='bob@example.com',
        message='Hello Bob!',
        encrypted=False
    )
    
    time.sleep(1)
    
    # Test receive
    messages = tcp.get_messages('bob@example.com')
    print(f"Bob's messages: {messages}")
    
    tcp.stop_server()
    
    print("\n=== Testing UDP Messenger ===")
    udp = UDPMessenger(port=9998)
    udp.start_server()
    
    time.sleep(1)
    
    # Test send
    udp.send_message(
        sender='alice@example.com',
        recipient='bob@example.com',
        message='Hello via UDP!',
        encrypted=False
    )
    
    time.sleep(1)
    
    # Test receive
    messages = udp.get_messages('bob@example.com')
    print(f"Bob's UDP messages: {messages}")
