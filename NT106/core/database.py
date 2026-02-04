import sqlite3
import hashlib
import os
from datetime import datetime

class Database:
    def __init__(self, db_path="delta_chat.db"):
        """
        Khởi tạo Database SQLite cho Delta Chat
        """
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Tạo kết nối tới database"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """
        Tạo các bảng cần thiết nếu chưa tồn tại
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Bảng 1: Users - Lưu thông tin đăng ký
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                username TEXT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                verified INTEGER DEFAULT 0,
                verification_token TEXT,
                oauth_refresh_token TEXT,
                oauth_access_token TEXT,
                oauth_token_expiry TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Bảng 2: Conversations - Danh sách cuộc hội thoại
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                last_message TEXT,
                last_timestamp TIMESTAMP,
                unread_count INTEGER DEFAULT 0,
                UNIQUE(user_email, contact_email)
            )
        """)
        
        # Bảng 3: Messages - Lưu tin nhắn chi tiết
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                conversation_id INTEGER,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                is_encrypted BOOLEAN DEFAULT 0,
                is_file BOOLEAN DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # Bảng 4: OAuth Tokens - Lưu OAuth tokens từ Google
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                user_email TEXT PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT,
                token_expiry TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_email) REFERENCES users(email)
            )
        """)
        
        # Bảng 5: User Keys - Lưu public keys cho E2EE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_keys (
                user_email TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_email) REFERENCES users(email)
            )
        """)
        
        # Bảng 6: Permissions - RBAC system
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                resource TEXT NOT NULL,
                action TEXT NOT NULL,
                UNIQUE(role, resource, action)
            )
        """)
        
        # Insert default permissions
        cursor.execute("SELECT COUNT(*) FROM permissions")
        if cursor.fetchone()[0] == 0:
            default_permissions = [
                # Admin permissions
                ('admin', '*', '*'),
                ('admin', 'users', 'view_all'),
                ('admin', 'users', 'delete'),
                ('admin', 'users', 'edit'),
                ('admin', 'messages', 'view_all'),
                ('admin', 'messages', 'delete'),
                ('admin', 'database', 'export'),
                ('admin', 'database', 'backup'),
                ('admin', 'system', 'stats'),
                # User permissions
                ('user', 'messages', 'send'),
                ('user', 'messages', 'read_own'),
                ('user', 'profile', 'edit_own'),
                ('user', 'users', 'list'),
            ]
            cursor.executemany("""
                INSERT INTO permissions (role, resource, action) VALUES (?, ?, ?)
            """, default_permissions)
            print("[DB] Default permissions created")
        
        conn.commit()
        
        # Migration: Add user_id column if not exists
        try:
            cursor.execute("SELECT user_id FROM users LIMIT 1")
        except sqlite3.OperationalError:
            print("[DB] Migrating: Adding user_id column...")
            cursor.execute("ALTER TABLE users ADD COLUMN user_id TEXT")
            
            # Generate user_ids for existing users
            cursor.execute("SELECT id, email FROM users WHERE user_id IS NULL")
            existing_users = cursor.fetchall()
            
            for user_id, email in existing_users:
                new_user_id = self.generate_user_id(email)
                cursor.execute("UPDATE users SET user_id = ? WHERE id = ?", (new_user_id, user_id))
                print(f"[DB] Generated user_id for {email}: {new_user_id}")
            
            conn.commit()
            print("[DB] Migration completed!")
        
        conn.close()
        print("[DB] Database initialized successfully.")
    
    def hash_password(self, password):
        """
        Mã hóa mật khẩu bằng PBKDF2-HMAC-SHA256 với salt
        Format: salt$hash (hex)
        """
        import secrets
        
        # Generate random 16-byte salt
        salt = secrets.token_hex(16)  # 32 chars hex
        
        # PBKDF2 with 100,000 iterations
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )
        
        # Return format: salt$hash
        return f"{salt}${pwd_hash.hex()}"
    
    def generate_user_id(self, email):
        """
        Tạo User ID duy nhất từ email + salt
        Format: 12 ký tự hex (a3f4e8b9c2d1)
        
        Args:
            email: Email của user
            
        Returns:
            str: User ID (12 chars)
        """
        import secrets
        import time
        
        # Tạo deterministic ID từ email + timestamp
        # Để ID không đổi nhưng vẫn unpredictable
        salt = str(int(time.time() * 1000000))  # microseconds
        
        # SHA256 hash
        hash_obj = hashlib.sha256((email + salt).encode())
        hash_hex = hash_obj.hexdigest()
        
        # Lấy 12 ký tự đầu
        return hash_hex[:12]
    
    def verify_password(self, password, stored_hash):
        """
        Xác thực mật khẩu với stored hash
        
        Args:
            password: Mật khẩu plaintext
            stored_hash: Hash từ database (salt$hash)
        
        Returns:
            bool: True nếu match
        """
        try:
            # Parse salt and hash
            salt, pwd_hash = stored_hash.split('$')
            
            # Compute hash with same salt
            check_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            )
            
            # Compare
            return check_hash.hex() == pwd_hash
        except:
            # Fallback: Old SHA-256 format (for backward compatibility)
            old_hash = hashlib.sha256(password.encode()).hexdigest()
            return old_hash == stored_hash
    
    def register_user(self, username, email, password, role='user'):
        """
        Đăng ký user mới
        
        Args:
            username: Tên user
            email: Email (unique)
            password: Mật khẩu plaintext
            role: 'admin' hoặc 'user' (default: 'user')
        
        Returns:
            dict: {'success': True, 'user_id': 'xxx'} hoặc {'success': False}
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            password_hash = self.hash_password(password)
            user_id = self.generate_user_id(email)
            
            cursor.execute("""
                INSERT INTO users (user_id, username, email, password_hash, role, verified)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (user_id, username, email, password_hash, role))
            
            conn.commit()
            conn.close()
            
            print(f"[DB] ✅ Created user: {email} → User ID: {user_id}")
            return {'success': True, 'user_id': user_id}
        except sqlite3.IntegrityError as e:
            print(f"[DB] ❌ Registration failed: {e}")
            return {'success': False, 'error': 'Email already exists'}
    
    def login_user(self, email, password):
        """
        Xác thực đăng nhập
        
        Args:
            email: Email
            password: Mật khẩu plaintext
        
        Returns:
            dict: User info nếu thành công, None nếu thất bại
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get user by email
        cursor.execute("""
            SELECT id, username, email, password_hash, role
            FROM users
            WHERE email = ?
        """, (email,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Verify password
            if self.verify_password(password, user[3]):
                return {
                    "id": user[0],
                    "username": user[1],
                    "email": user[2],
                    "role": user[4]
                }
        
        return None
    
    # Gmail App Password methods removed - using TCP sockets instead
    
    def get_or_create_conversation(self, user_email, contact_email):
        """
        Lấy hoặc tạo mới conversation
        :return: conversation_id
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tìm conversation hiện có
        cursor.execute("""
            SELECT id FROM conversations
            WHERE user_email = ? AND contact_email = ?
        """, (user_email, contact_email))
        
        conv = cursor.fetchone()
        
        if conv:
            conn.close()
            return conv[0]
        
        # Tạo mới nếu chưa có
        cursor.execute("""
            INSERT INTO conversations (user_email, contact_email)
            VALUES (?, ?)
        """, (user_email, contact_email))
        
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return conversation_id
    
    def save_message(self, message_id, sender, recipient, subject, body, is_encrypted=False, is_file=False):
        """
        Lưu tin nhắn vào database
        :return: True nếu tin nhắn mới, False nếu đã tồn tại
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Xác định conversation (người gửi hoặc người nhận là user hiện tại)
            # Logic: Lấy email nhỏ hơn làm user_email, lớn hơn làm contact_email
            emails = sorted([sender, recipient])
            conv_id = self.get_or_create_conversation(emails[0], emails[1])
            
            cursor.execute("""
                INSERT INTO messages (message_id, conversation_id, sender, recipient, subject, body, is_encrypted, is_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (message_id, conv_id, sender, recipient, subject, body, is_encrypted, is_file))
            
            # Cập nhật last_message trong conversation
            cursor.execute("""
                UPDATE conversations
                SET last_message = ?, last_timestamp = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (body[:50] + "..." if len(body) > 50 else body, conv_id))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.IntegrityError:
            return False  # Tin nhắn đã tồn tại
    
    def get_conversations(self, user_email):
        """
        Lấy danh sách cuộc hội thoại của user
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, contact_email, last_message, last_timestamp, unread_count
            FROM conversations
            WHERE user_email = ?
            ORDER BY last_timestamp DESC
        """, (user_email,))
        
        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                "id": row[0],
                "contact": row[1],
                "last_message": row[2],
                "last_timestamp": row[3],
                "unread_count": row[4]
            })
        
        conn.close()
        return conversations
    
    def get_messages_by_conversation(self, conversation_id, limit=50):
        """
        Lấy tin nhắn trong 1 cuộc hội thoại
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT message_id, sender, recipient, subject, body, is_encrypted, is_file, timestamp
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (conversation_id, limit))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "message_id": row[0],
                "sender": row[1],
                "recipient": row[2],
                "subject": row[3],
                "body": row[4],
                "is_encrypted": row[5],
                "is_file": row[6],
                "timestamp": row[7]
            })
        
        conn.close()
        return messages
    
    def get_all_messages_for_user(self, user_email, limit=100):
        """
        Lấy TẤT CẢ tin nhắn liên quan đến user (gửi hoặc nhận)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT message_id, sender, recipient, subject, body, is_encrypted, is_file, timestamp
            FROM messages
            WHERE sender = ? OR recipient = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_email, user_email, limit))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "message_id": row[0],
                "sender": row[1],
                "recipient": row[2],
                "subject": row[3],
                "body": row[4],
                "is_encrypted": row[5],
                "is_file": row[6],
                "timestamp": row[7]
            })
        
        conn.close()
        return messages
    
    def save_oauth_tokens(self, email, access_token, refresh_token, token_expiry):
        """
        Lưu OAuth tokens vào database
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO oauth_tokens 
            (user_email, access_token, refresh_token, token_expiry, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (email, access_token, refresh_token, token_expiry))
        
        conn.commit()
        conn.close()

    def get_oauth_tokens(self, email):
        """
        Lấy OAuth tokens từ database
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT access_token, refresh_token, token_expiry
            FROM oauth_tokens
            WHERE user_email = ?
        """, (email,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'access_token': result[0],
                'refresh_token': result[1],
                'token_expiry': result[2]
            }
        return None
    
    def save_public_key(self, email, public_key):
        """
        Lưu public key của user cho E2EE
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_keys (user_email, public_key, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (email, public_key))
        
        conn.commit()
        conn.close()
    
    def get_all_users(self):
        """
        Lấy danh sách tất cả users (kể cả user_id)
        Return: List of {id, user_id, username, email}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, user_id, username, email
            FROM users
            ORDER BY username
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'email': row[3]
            })
        
        conn.close()
        return users
    
    def find_user_by_id(self, user_id):
        """
        Tìm user bằng User ID
        
        Args:
            user_id: User ID (12 chars hex)
            
        Returns:
            dict: {id, user_id, username, email} hoặc None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, user_id, username, email
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'user_id': result[1],
                'username': result[2],
                'email': result[3]
            }
        return None
    
    def get_user_id_by_email(self, email):
        """
        Lấy User ID từ email
        
        Args:
            email: Email của user
            
        Returns:
            str: User ID hoặc None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id FROM users WHERE email = ?
        """, (email,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None

    def get_public_key(self, email):
        """
        Lấy public key của user
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT public_key FROM user_keys WHERE user_email = ?
        """, (email,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def verify_email(self, token):
        """Verify email với token"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users SET verified = 1, verification_token = NULL
            WHERE verification_token = ?
        """, (token,))
        
        rows_affected = cursor.rowcount
        conn.commit()
        
        if rows_affected > 0:
            # Get user info
            cursor.execute("SELECT id, email, username FROM users WHERE verification_token IS NULL AND verified = 1 ORDER BY id DESC LIMIT 1")
            user = cursor.fetchone()
            conn.close()
            if user:
                return {'id': user[0], 'email': user[1], 'username': user[2]}
        
        conn.close()
        return None
    
    def update_oauth_tokens(self, email, access_token, refresh_token, expiry):
        """Lưu OAuth tokens"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET oauth_access_token = ?, oauth_refresh_token = ?, oauth_token_expiry = ?
            WHERE email = ?
        """, (access_token, refresh_token, expiry, email))
        
        conn.commit()
        conn.close()
    
    def get_oauth_tokens(self, email):
        """Lấy OAuth tokens"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT oauth_access_token, oauth_refresh_token, oauth_token_expiry
            FROM users WHERE email = ?
        """, (email,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'access_token': result[0],
                'refresh_token': result[1],
                'expiry': result[2]
            }
        return None
    
    # ===== ADMIN FUNCTIONS =====
    
    def get_all_users_admin(self):
        """Admin: Lấy danh sách tất cả users (với role và created_at)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, user_id, username, email, role, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'email': row[3],
                'role': row[4],
                'created_at': row[5]
            })
        
        conn.close()
        return users
    
    def get_user_by_email(self, email):
        """Lấy thông tin user theo email"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, created_at
            FROM users
            WHERE email = ?
        """, (email,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'role': row[3],
                'created_at': row[4]
            }
        return None
    
    def delete_user(self, email):
        """Admin: Xóa user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM users WHERE email = ?", (email,))
        cursor.execute("DELETE FROM messages WHERE sender = ? OR recipient = ?", (email, email))
        cursor.execute("DELETE FROM conversations WHERE user_email = ? OR contact_email = ?", (email, email))
        cursor.execute("DELETE FROM user_keys WHERE user_email = ?", (email,))
        
        conn.commit()
        conn.close()
        return True
    
    def get_all_messages_admin(self, limit=100):
        """Admin: Lấy tất cả tin nhắn (encrypted)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT message_id, sender, recipient, subject, body, 
                   is_encrypted, is_file, timestamp
            FROM messages
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'message_id': row[0],
                'sender': row[1],
                'recipient': row[2],
                'subject': row[3],
                'body': row[4],
                'is_encrypted': row[5],
                'is_file': row[6],
                'timestamp': row[7]
            })
        
        conn.close()
        return messages
    
    def has_permission(self, role, resource, action):
        """Check xem role có permission không"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check wildcard permission
        cursor.execute("""
            SELECT COUNT(*) FROM permissions
            WHERE role = ? AND (
                (resource = '*' AND action = '*') OR
                (resource = ? AND action = '*') OR
                (resource = ? AND action = ?)
            )
        """, (role, resource, resource, action))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def get_database_stats(self):
        """Admin: Lấy thống kê database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]
        
        # Total messages
        cursor.execute("SELECT COUNT(*) FROM messages")
        stats['total_messages'] = cursor.fetchone()[0]
        
        # Total conversations
        cursor.execute("SELECT COUNT(*) FROM conversations")
        stats['total_conversations'] = cursor.fetchone()[0]
        
        # Encrypted messages
        cursor.execute("SELECT COUNT(*) FROM messages WHERE is_encrypted = 1")
        stats['encrypted_messages'] = cursor.fetchone()[0]
        
        # Users by role
        cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
        stats['users_by_role'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        return stats


# TEST CODE
if __name__ == "__main__":
    db = Database("test_delta.db")
    
    # Test đăng ký
    print("Test 1: Register user")
    result = db.register_user("nhan", "nhan@gmail.com", "123456")
    print(f"Register: {result}")
    
    # Test login
    print("\nTest 2: Login")
    user = db.login_user("nhan@gmail.com", "123456")
    print(f"Login: {user}")
    
    # Test save message
    print("\nTest 3: Save message")
    db.save_message("msg001", "nhan@gmail.com", "friend@gmail.com", "Hello", "This is a test message")
    
    # Test get conversations
    print("\nTest 4: Get conversations")
    convs = db.get_conversations("nhan@gmail.com")
    print(f"Conversations: {convs}")
