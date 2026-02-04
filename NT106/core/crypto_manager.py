from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib

"""
⚠️ DEPRECATION WARNING:
CryptoManager sử dụng AES-CBC (vulnerable to padding oracle attacks).

🔐 NÊN SỬ DỤNG: E2EEManager (core/e2ee_manager.py)
   - AES-GCM-256 (authenticated encryption)
   - ECDH key exchange
   - Per-message nonce
   - Better security

CryptoManager được giữ lại chỉ để:
- Decrypt messages cũ trong database
- Backward compatibility
"""

class CryptoManager:
    """
    Mã hóa/Giải mã tin nhắn bằng AES-256-CBC
    ⚠️ DEPRECATED: Dùng E2EEManager thay vì class này
    """
    
    def __init__(self, secret_key=None):
        """
        :param secret_key: Khóa bí mật (string), nếu không có sẽ dùng default
        """
        if secret_key is None:
            secret_key = "DELTA_CHAT_SECRET_KEY_NT106"  # Default key
        
        # Tạo key 256-bit từ secret_key bằng SHA-256
        self.key = hashlib.sha256(secret_key.encode()).digest()
    
    def encrypt(self, plaintext):
        """
        Mã hóa văn bản
        :param plaintext: Văn bản gốc (string)
        :return: Văn bản đã mã hóa (base64 string)
        """
        try:
            # Tạo IV ngẫu nhiên (16 bytes cho AES)
            iv = get_random_bytes(16)
            
            # Tạo cipher AES-CBC
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            
            # Padding văn bản để chia hết cho block size (16 bytes)
            padded_text = pad(plaintext.encode('utf-8'), AES.block_size)
            
            # Mã hóa
            ciphertext = cipher.encrypt(padded_text)
            
            # Gộp IV + Ciphertext và encode base64 để dễ truyền qua mạng
            encrypted_data = iv + ciphertext
            return base64.b64encode(encrypted_data).decode('utf-8')
        
        except Exception as e:
            print(f"[CRYPTO ERROR] Encrypt failed: {e}")
            return None
    
    def decrypt(self, encrypted_text):
        """
        Giải mã văn bản
        :param encrypted_text: Văn bản đã mã hóa (base64 string)
        :return: Văn bản gốc (string)
        """
        try:
            # Decode base64
            encrypted_data = base64.b64decode(encrypted_text)
            
            # Tách IV (16 bytes đầu) và Ciphertext
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            # Tạo cipher để giải mã
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            
            # Giải mã và xóa padding
            decrypted_padded = cipher.decrypt(ciphertext)
            plaintext = unpad(decrypted_padded, AES.block_size)
            
            return plaintext.decode('utf-8')
        
        except Exception as e:
            print(f"[CRYPTO ERROR] Decrypt failed: {e}")
            return None
    
    def encrypt_message_body(self, body):
        """
        Mã hóa nội dung tin nhắn và thêm prefix để nhận biết
        """
        encrypted = self.encrypt(body)
        if encrypted:
            return f"[ENCRYPTED]{encrypted}"
        return body
    
    def decrypt_message_body(self, body):
        """
        Giải mã nội dung tin nhắn nếu có prefix [ENCRYPTED]
        """
        if body.startswith("[ENCRYPTED]"):
            encrypted_part = body.replace("[ENCRYPTED]", "")
            decrypted = self.decrypt(encrypted_part)
            return decrypted if decrypted else "[Lỗi giải mã]"
        return body


# TEST CODE
if __name__ == "__main__":
    print("=== TEST CRYPTO MODULE ===\n")
    
    crypto = CryptoManager()
    
    # Test 1: Mã hóa và giải mã
    original_text = "Hello, this is a secret message from NT106!"
    print(f"Original: {original_text}")
    
    encrypted = crypto.encrypt(original_text)
    print(f"Encrypted: {encrypted}")
    
    decrypted = crypto.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")
    
    print(f"\nMatch: {original_text == decrypted}")
    
    # Test 2: Message body with prefix
    print("\n--- Test Message Body ---")
    msg_body = "Đây là tin nhắn bí mật!"
    encrypted_body = crypto.encrypt_message_body(msg_body)
    print(f"Encrypted Body: {encrypted_body}")
    
    decrypted_body = crypto.decrypt_message_body(encrypted_body)
    print(f"Decrypted Body: {decrypted_body}")
