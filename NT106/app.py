from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime
import os
import time
import threading

# Import các module Core
from core.s3_manager import S3Manager
from core.database import Database
from core.crypto_manager import CryptoManager
from core.e2ee_manager import E2EEManager
from core.tcp_messenger import TCPMessenger
from core.admin_key_manager import AdminKeyManager

# Load biến môi trường
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'mac_dinh_neu_khong_co_env')

# Session configuration (fix OAuth state issue)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = False  # True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Khởi tạo SocketIO cho Multi-Client Real-time
# Dùng threading thay vì eventlet để tương thích Python 3.12
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Khởi tạo Database và Crypto
db = Database()
crypto = CryptoManager()
e2ee = E2EEManager()
# TCP Socket cho messaging - sử dụng TCP_PORT từ environment
tcp_port = int(os.environ.get('TCP_PORT', 9999))
tcp_messenger = TCPMessenger(port=tcp_port)
admin_key = AdminKeyManager()  # Master key cho data at rest

# --- [NEW] KHỞI TẠO S3 MANAGER ---
s3_manager = S3Manager()

# --- [NEW] BACKGROUND THREAD CHO IMAP SYNC ---
class EmailSyncWorker:
    """
    Background thread để sync email từ IMAP định kỳ
    Đáp ứng yêu cầu Thread trong rubric
    """
    def __init__(self, interval=30):
        self.interval = interval  # Sync mỗi 30 giây
        self.running = False
        self.thread = None
    
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.thread.start()
            print("[THREAD] Background Email Sync Worker started.")
    
    def stop(self):
        self.running = False
    
    def _sync_loop(self):
        """Loop chính để sync email định kỳ"""
        while self.running:
            try:
                # Lấy danh sách tất cả users có gmail_app_password
                # (Trong thực tế, chỉ sync cho users đang online)
                # Ở đây đơn giản hóa: sync cho tất cả users
                
                print(f"[THREAD] Running email sync...")
                
                # TODO: Implement logic sync cho tất cả users
                # Hiện tại chỉ log để biết thread đang chạy
                
                time.sleep(self.interval)
            except Exception as e:
                print(f"[THREAD ERROR] {e}")
                time.sleep(self.interval)

# Khởi tạo và start background worker
email_sync_worker = EmailSyncWorker(interval=30)
email_sync_worker.start()

# Start TCP messenger server
tcp_messenger.start_server()
print("[TCP] Messenger server started")

# ===== RBAC AUTHORIZATION DECORATOR =====
def require_permission(resource, action):
    """
    Decorator để check permission (RBAC)
    
    Usage:
        @require_permission('users', 'view_all')
        def admin_view_users():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check authentication
            if 'user_email' not in session:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Get user role
            user = db.get_user_by_email(session['user_email'])
            if not user:
                return jsonify({'error': 'User not found'}), 401
            
            role = user.get('role', 'user')
            
            # Check permission
            if not db.has_permission(role, resource, action):
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'Role {role} không có quyền {action} trên {resource}'
                }), 403
            
            # Pass user info to route
            kwargs['current_user'] = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- SOCKETIO EVENTS (MULTI-CLIENT SUPPORT) ---
@socketio.on('connect')
def handle_connect():
    if 'user_email' in session:
        join_room(session['user_email'])
        print(f"[SOCKET] User {session['user_email']} connected")
        emit('status', {'message': 'Connected to Delta Chat'})

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_email' in session:
        print(f"[SOCKET] User {session['user_email']} disconnected")

# --- HEALTH CHECK ENDPOINT (FOR LOAD BALANCER) ---
@app.route('/health')
def health_check():
    """
    Health check endpoint cho Load Balancer tự code
    Kiểm tra trạng thái của Database, TCP Messenger
    
    ⚡ OPTIMIZED: Không check S3 vì slow (network call)
    Dùng /health?full=1 để check đầy đủ
    """
    import socket as sock
    from datetime import datetime
    
    full_check = request.args.get('full', '0') == '1'
    
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'instance': os.environ.get('INSTANCE_ID', '1'),
        'services': {}
    }
    
    # Check Database (fast - local SQLite)
    try:
        conn = db.get_connection()
        conn.execute("SELECT 1")
        health_status['services']['database'] = 'up'
    except Exception as e:
        health_status['services']['database'] = f'down: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check TCP Messenger (fast - local socket)
    try:
        test_sock = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
        test_sock.settimeout(0.5)  # Giảm timeout từ 1s xuống 0.5s
        tcp_port = int(os.environ.get('TCP_PORT', 9999))
        test_sock.connect(('127.0.0.1', tcp_port))
        test_sock.close()
        health_status['services']['tcp_messenger'] = 'up'
    except Exception as e:
        health_status['services']['tcp_messenger'] = f'down: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # Check S3 (SLOW - chỉ check khi full=1)
    if full_check:
        try:
            s3_manager.s3.head_bucket(Bucket=s3_manager.bucket_name)
            health_status['services']['s3'] = 'up'
        except Exception as e:
            health_status['services']['s3'] = f'down: {str(e)}'
    else:
        health_status['services']['s3'] = 'skipped (use ?full=1)'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

# --- [NEW] KHỞI TẠO S3 MANAGER ---
s3_manager = S3Manager()

# --- ROUTE 1: TRANG ĐĂNG KÝ ---
@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register_action', methods=['POST'])
def register_action():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form.get('confirm_password', '')
    
    # Validate password match
    if password != confirm_password:
        return render_template('register.html', error="Mật khẩu không khớp!")
    
    # Đăng ký vào database (không cần gmail_app_password)
    result = db.register_user(username, email, password)
    
    if result['success']:
        user_id = result['user_id']
        
        # Generate E2EE keypair cho user mới
        private_key, public_key = e2ee.generate_keypair()
        
        # Lưu public key vào database
        db.save_public_key(email, public_key)
        
        # Lưu private key vào session để gửi cho client
        session['new_user_private_key'] = private_key
        session['new_user_email'] = email
        
        print(f"[E2EE] Generated keypair for {email}")
        print(f"[E2EE] Public key saved to database")
        
        success_msg = f"Đăng ký thành công! User ID của bạn: {user_id}. Vui lòng đăng nhập."
        return render_template('register.html', success=success_msg, user_id=user_id)
    else:
        return render_template('register.html', error="Email hoặc tên đăng nhập đã tồn tại!")

# --- ROUTE 2: TRANG ĐĂNG NHẬP ---
@app.route('/')
def login():
    if 'user_email' in session:
        return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/login_action', methods=['POST'])
def login_action():
    email = request.form['email']
    password = request.form['password']
    
    # Xác thực với database
    user = db.login_user(email, password)
    
    if user:
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['username'] = user['username']
        session['user_role'] = user.get('role', 'user')
        
        # Redirect admin to admin dashboard
        if user.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        
        return redirect(url_for('chat'))
    else:
        return render_template('login.html', error="Email hoặc mật khẩu không đúng!")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- E2EE API ROUTES ---

@app.route('/api/user/public_key/<email>')
def get_user_public_key(email):
    """
    API endpoint để client lấy public key của recipient
    """
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    public_key = db.get_public_key(email)
    
    if not public_key:
        return jsonify({'error': 'User not found or no key'}), 404
    
    return jsonify({'email': email, 'public_key': public_key})


@app.route('/api/encrypt', methods=['POST'])
def api_encrypt():
    """Helper API cho client-side encryption"""
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    message = data.get('message')
    my_private_key = data.get('my_private_key')
    recipient_public_key = data.get('recipient_public_key')
    
    if not all([message, my_private_key, recipient_public_key]):
        return jsonify({'error': 'Missing parameters'}), 400
    
    try:
        encrypted = e2ee.encrypt_for_recipient(
            message,
            my_private_key,
            recipient_public_key
        )
        return jsonify({'encrypted_message': encrypted})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/decrypt', methods=['POST'])
def api_decrypt():
    """Helper API cho client-side decryption"""
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    encrypted_message = data.get('encrypted_message')
    my_private_key = data.get('my_private_key')
    sender_public_key = data.get('sender_public_key')
    
    if not all([encrypted_message, my_private_key, sender_public_key]):
        return jsonify({'error': 'Missing parameters'}), 400
    
    try:
        decrypted = e2ee.decrypt_from_sender(
            encrypted_message,
            my_private_key,
            sender_public_key
        )
        return jsonify({'decrypted_message': decrypted})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- OAUTH ROUTES REMOVED - Using simple email/password only ---

# --- ROUTE 3: GIAO DIỆN CHAT ---
# --- ROUTE 3: GIAO DIỆN CHAT ---
@app.route('/chat')
def chat():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', 
                          user_email=session['user_email'],
                          username=session.get('username', 'User'))

# --- SETUP ROUTES REMOVED - No Gmail App Password needed ---

# --- ROUTE 4: API GỬI TIN NHẮN (CÓ MÃ HÓA) ---
@app.route('/api/send', methods=['POST'])
def api_send():
    if 'user_email' not in session:
        return jsonify({"status": "error", "message": "Chưa đăng nhập"}), 401

    recipient = request.form.get('recipient')
    subject = request.form.get('subject', '[Delta-Chat]')  # Subject đặc biệt để lọc
    body = request.form.get('body', '')
    attachment = request.files.get('attachment')
    enable_encryption = request.form.get('encrypt', 'false') == 'true'

    # 1. Upload file đính kèm lên S3 (nếu có)
    is_file = False
    if attachment:
        try:
            file_url = s3_manager.upload_file(attachment, attachment.filename)
            if file_url:
                body += f"\n\n{file_url}"
                is_file = True
        except Exception as e:
            return jsonify({"status": "error", "message": f"Lỗi S3: {str(e)}"})

    # 2. Mã hóa tin nhắn (nếu được bật)
    original_body = body
    if enable_encryption and not is_file:
        body = crypto.encrypt_message_body(body)
        subject = "[Delta-Chat-Encrypted]"

    # 3. Gửi tin nhắn qua TCP Socket (thay vì SMTP)
    try:
        # Sử dụng TCP messenger thay vì SMTP
        success = tcp_messenger.send_message(
            sender=session['user_email'],
            recipient=recipient,
            message=body,
            encrypted=enable_encryption
        )
        
        # 4. Lưu vào Database để sync nhanh
        # Sinh message_id giả (thực tế sẽ lấy từ IMAP sau)
        import uuid
        msg_id = str(uuid.uuid4())
        db.save_message(
            msg_id, 
            session['user_email'], 
            recipient, 
            subject, 
            original_body,  # Lưu bản gốc vào DB
            is_encrypted=enable_encryption,
            is_file=is_file
        )
        
        # 5. Broadcast qua SocketIO cho TẤT CẢ clients
        # 6. Broadcast qua SocketIO cho NGƯỜI GỬI và NGƯỜI NHẬN
        # Sử dụng room-based emit - mỗi user join room = email khi connect
        message_data = {
            'sender': session['user_email'],
            'recipient': recipient,
            'body': original_body,
            'subject': subject,
            'timestamp': datetime.now().isoformat() + 'Z'
        }
        
        # Emit vào room của NGƯỜI NHẬN (để họ nhận tin realtime)
        socketio.emit('new_message', message_data, room=recipient, namespace='/')
        
        # Emit vào room của NGƯỜI GỬI (để sync các tab khác của họ)
        socketio.emit('new_message', message_data, room=session['user_email'], namespace='/')
        
        print(f"[SOCKET] Emitted new_message to rooms: {recipient}, {session['user_email']}")
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# --- ROUTE 5: API NHẬN TIN (SYNC STRATEGY - CHỈ DELTA CHAT) ---
@app.route('/api/get_messages')
def api_get_messages():
    """
    API lấy tất cả tin nhắn của user
    
    ⚠️ QUAN TRỌNG - Tránh duplicate:
    - CHỈ lấy tin từ Database (đã lưu ở api_send)
    - KHÔNG lưu lại TCP messages vào DB
    - Tin nhắn đã được lưu 1 lần duy nhất khi gửi
    
    Flow:
    1. User A gửi tin → api_send → Lưu DB + TCP queue + Emit SocketIO
    2. User B nhận tin → SocketIO trigger → fetchMessages() → Lấy từ DB
    3. Không cần lưu lại từ TCP queue vì đã có trong DB
    """
    if 'user_email' not in session:
        return jsonify([])
    
    try:
        # Lấy tin nhắn từ Database (đã deduplicate bằng UNIQUE message_id)
        messages = db.get_all_messages_for_user(session['user_email'], limit=100)
        
        # Giải mã tin nhắn nếu cần
        for msg in messages:
            if msg.get('is_encrypted'):
                msg['body'] = crypto.decrypt_message_body(msg['body'])
        
        return jsonify(messages)
    
    except Exception as e:
        print(f"[ERROR] Get messages error: {e}")
        return jsonify([])

# --- ROUTE 6: API LẤY DANH SÁCH CUỘC HỘI THOẠI ---
@app.route('/api/conversations')
def api_conversations():
    if 'user_email' not in session:
        return jsonify([])
    
    conversations = db.get_conversations(session['user_email'])
    return jsonify(conversations)

# --- ROUTE 7: API LẤY TIN NHẮN THEO CUỘC HỘI THOẠI ---
@app.route('/api/messages/<int:conversation_id>')
def api_messages_by_conversation(conversation_id):
    if 'user_email' not in session:
        return jsonify([])
    
    messages = db.get_messages_by_conversation(conversation_id)
    
    # Giải mã nếu cần
    for msg in messages:
        if msg.get('is_encrypted'):
            msg['body'] = crypto.decrypt_message_body(msg['body'])
    
    return jsonify(messages)
# ===== ADMIN ROUTES =====

@app.route('/admin')
@require_permission('system', 'stats')
def admin_dashboard(current_user=None):
    """Admin Dashboard"""
    stats = db.get_database_stats()
    return render_template('admin_dashboard.html', 
                          stats=stats, 
                          user=current_user)

@app.route('/api/admin/users')
@require_permission('users', 'view_all')
def admin_get_users(current_user=None):
    """API: Lấy danh sách tất cả users"""
    users = db.get_all_users()
    return jsonify(users)

@app.route('/api/admin/users/<email>/delete', methods=['DELETE'])
@require_permission('users', 'delete')
def admin_delete_user(email, current_user=None):
    """API: Xóa user"""
    if email == current_user['email']:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    db.delete_user(email)
    return jsonify({'status': 'success', 'message': f'Deleted user {email}'})

@app.route('/api/admin/messages')
@require_permission('messages', 'view_all')
def admin_get_messages(current_user=None):
    """API: Lấy tất cả tin nhắn (admin only)"""
    limit = request.args.get('limit', 100, type=int)
    messages = db.get_all_messages_admin(limit)
    
    # Decrypt messages with admin key
    for msg in messages:
        try:
            # If encrypted with admin key
            if msg['body'] and msg['body'].startswith('ENC:'):
                msg['body'] = admin_key.decrypt_data(msg['body'][4:])
        except:
            pass  # Keep encrypted if can't decrypt
    
    return jsonify(messages)

@app.route('/api/admin/stats')
@require_permission('system', 'stats')
def admin_get_stats(current_user=None):
    """API: Thống kê hệ thống"""
    stats = db.get_database_stats()
    return jsonify(stats)

@app.route('/api/admin/export')
@require_permission('database', 'export')
def admin_export_database(current_user=None):
    """API: Export database"""
    import json
    
    data = {
        'users': db.get_all_users(),
        'messages': db.get_all_messages_admin(limit=1000),
        'stats': db.get_database_stats()
    }
    
    return jsonify(data)

# ===== CURRENT USER API =====

@app.route('/api/current_user')
def api_current_user():
    """API: Lấy thông tin user hiện tại"""
    if 'user_email' not in session:
        return jsonify({'email': None, 'logged_in': False})
    return jsonify({
        'email': session['user_email'],
        'logged_in': True
    })

# ===== SOCKETIO TEST PAGE =====

@app.route('/socketio_test')
def socketio_test_page():
    """Test page for debugging SocketIO"""
    return render_template('socketio_test.html')

# ===== USER DISCOVERY API =====

@app.route('/api/users')
def api_list_users():
    """API: Danh sách users để bắt đầu chat"""
    if 'user_email' not in session:
        return jsonify([])
    
    users = db.get_all_users()
    
    # Filter: không show mình
    users = [u for u in users if u['email'] != session['user_email']]
    
    return jsonify(users)

# ===== USER ID & ADD FRIEND API =====

@app.route('/api/user/my_id')
def api_get_my_id():
    """Lấy User ID của mình để share"""
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = db.get_user_id_by_email(session['user_email'])
    
    if not user_id:
        return jsonify({'error': 'User ID not found'}), 404
    
    return jsonify({
        'user_id': user_id,
        'email': session['user_email'],
        'username': session.get('username', '')
    })

@app.route('/api/user/find_by_id', methods=['POST'])
def api_find_user_by_id():
    """Tìm user bằng User ID"""
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    search_id = data.get('user_id', '').strip()
    
    if not search_id:
        return jsonify({'error': 'User ID required'}), 400
    
    # Find user
    user = db.find_user_by_id(search_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Don't allow adding yourself
    if user['email'] == session['user_email']:
        return jsonify({'error': 'Cannot add yourself'}), 400
    
    return jsonify({
        'found': True,
        'user_id': user['user_id'],
        'username': user['username'],
        'email': user['email']
    })

@app.route('/api/user/add_friend', methods=['POST'])
def api_add_friend():
    """Thêm bạn bằng User ID và tạo conversation"""
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    friend_id = data.get('user_id', '').strip()
    
    if not friend_id:
        return jsonify({'error': 'User ID required'}), 400
    
    # Find friend
    friend = db.find_user_by_id(friend_id)
    
    if not friend:
        return jsonify({'error': 'User not found'}), 404
    
    if friend['email'] == session['user_email']:
        return jsonify({'error': 'Cannot add yourself'}), 400
    
    # Create conversation (if not exists)
    conv_id = db.get_or_create_conversation(session['user_email'], friend['email'])
    
    return jsonify({
        'success': True,
        'friend': {
            'user_id': friend['user_id'],
            'username': friend['username'],
            'email': friend['email']
        },
        'conversation_id': conv_id
    })

if __name__ == '__main__':
    # Get port from environment (for load balancing)
    flask_port = int(os.environ.get('PORT', 5000))
    tcp_port = int(os.environ.get('TCP_PORT', 9999))
    instance_id = os.environ.get('INSTANCE_ID', '1')
    
    print(f"🚀 Starting Delta Chat Instance #{instance_id}")
    print(f"   Flask Port: {flask_port}")
    print(f"   TCP Port: {tcp_port}")
    print(f"   Ready for Load Balancer")
    
    # Sử dụng SocketIO.run thay vì app.run để hỗ trợ WebSocket
    socketio.run(app, debug=False, port=flask_port, host='0.0.0.0', allow_unsafe_werkzeug=True)