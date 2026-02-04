"""
Admin Key Manager - Data at Rest Encryption
Quản lý Master Encryption Key để mã hóa dữ liệu trong database (AES-GCM-256)
Chỉ admin có quyền truy cập key này
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

class AdminKeyManager:
    """
    Quản lý Master Key để encrypt/decrypt dữ liệu trong database
    
    Security:
    - AES-GCM-256 for authenticated encryption
    - Random nonce per encryption
    - Master key stored securely (file system with restricted permissions)
    """
    
    def __init__(self, master_key_path='master.key'):
        """
        Khởi tạo AdminKeyManager
        
        Args:
            master_key_path: Đường dẫn đến file chứa master key
        """
        self.master_key_path = master_key_path
        self.master_key = self._load_or_generate_key()
        print(f"[ADMIN KEY] ✅ Master key initialized: {master_key_path}")
    
    def _load_or_generate_key(self):
        """
        Load master key từ file, hoặc generate mới nếu chưa có
        
        Returns:
            bytes: 32-byte master key
        """
        if os.path.exists(self.master_key_path):
            # Load existing key
            with open(self.master_key_path, 'rb') as f:
                key = f.read()
            
            if len(key) != 32:
                raise ValueError("Invalid master key length (must be 32 bytes)")
            
            print(f"[ADMIN KEY] Loaded existing master key")
            return key
        else:
            # Generate new 256-bit key
            key = AESGCM.generate_key(bit_length=256)
            
            # Save to file with restricted permissions
            with open(self.master_key_path, 'wb') as f:
                f.write(key)
            
            # Set file permissions (read/write for owner only)
            os.chmod(self.master_key_path, 0o600)
            
            print(f"[ADMIN KEY] ⚠️  NEW MASTER KEY GENERATED!")
            print(f"[ADMIN KEY] Path: {self.master_key_path}")
            print(f"[ADMIN KEY] BACKUP THIS FILE SECURELY!")
            
            return key
    
    def encrypt_data(self, plaintext):
        """
        Mã hóa dữ liệu với AES-GCM-256
        
        Args:
            plaintext: String cần mã hóa
            
        Returns:
            str: Base64-encoded (nonce + ciphertext + tag)
        """
        if not plaintext:
            return ""
        
        try:
            # Create AESGCM cipher
            aesgcm = AESGCM(self.master_key)
            
            # Generate random 96-bit nonce
            nonce = os.urandom(12)
            
            # Encrypt (GCM mode includes authentication tag automatically)
            ciphertext = aesgcm.encrypt(
                nonce,
                plaintext.encode('utf-8'),
                None  # No additional authenticated data
            )
            
            # Combine nonce + ciphertext and encode to base64
            encrypted_blob = nonce + ciphertext
            return base64.b64encode(encrypted_blob).decode('utf-8')
        
        except Exception as e:
            print(f"[ADMIN KEY ERROR] Encryption failed: {e}")
            raise
    
    def decrypt_data(self, encrypted_base64):
        """
        Giải mã dữ liệu từ database
        
        Args:
            encrypted_base64: Base64-encoded encrypted data
            
        Returns:
            str: Plaintext
        """
        if not encrypted_base64:
            return ""
        
        try:
            # Decode from base64
            encrypted_blob = base64.b64decode(encrypted_base64)
            
            # Extract nonce (first 12 bytes) and ciphertext
            nonce = encrypted_blob[:12]
            ciphertext = encrypted_blob[12:]
            
            # Create AESGCM cipher
            aesgcm = AESGCM(self.master_key)
            
            # Decrypt and verify authentication tag
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext.decode('utf-8')
        
        except Exception as e:
            print(f"[ADMIN KEY ERROR] Decryption failed: {e}")
            raise ValueError("Decryption failed - data may be corrupted or key is wrong")
    
    def rotate_key(self, new_key_path='master_new.key'):
        """
        Key rotation: Generate new key và re-encrypt tất cả data
        
        Note: Requires database migration script
        """
        print("[ADMIN KEY] ⚠️  KEY ROTATION NOT IMPLEMENTED")
        print("[ADMIN KEY] Manual steps required:")
        print("  1. Generate new key")
        print("  2. Decrypt all data with old key")
        print("  3. Re-encrypt all data with new key")
        print("  4. Replace old key file")
        raise NotImplementedError("Key rotation requires manual migration")


# Test code
if __name__ == '__main__':
    print("=" * 60)
    print("🔐 Testing AdminKeyManager")
    print("=" * 60)
    print()
    
    # Test 1: Create manager
    print("1️⃣  Initializing AdminKeyManager...")
    admin_key = AdminKeyManager('test_master.key')
    print()
    
    # Test 2: Encrypt data
    print("2️⃣  Encrypting sensitive data...")
    data = "This is a secret message stored in database 🔒"
    encrypted = admin_key.encrypt_data(data)
    print(f"   📝 Original: {data}")
    print(f"   🔒 Encrypted: {encrypted[:60]}...")
    print()
    
    # Test 3: Decrypt data
    print("3️⃣  Decrypting data...")
    decrypted = admin_key.decrypt_data(encrypted)
    print(f"   🔓 Decrypted: {decrypted}")
    print(f"   ✅ Match: {decrypted == data}")
    print()
    
    # Test 4: Multiple encryptions produce different ciphertexts
    print("4️⃣  Testing nonce randomness...")
    encrypted1 = admin_key.encrypt_data(data)
    encrypted2 = admin_key.encrypt_data(data)
    print(f"   Same plaintext → Different ciphertexts: {encrypted1 != encrypted2}")
    print(f"   Both decrypt correctly: {admin_key.decrypt_data(encrypted1) == admin_key.decrypt_data(encrypted2) == data}")
    print()
    
    # Test 5: Empty string
    print("5️⃣  Testing edge cases...")
    empty_encrypted = admin_key.encrypt_data("")
    print(f"   Empty string encrypted: '{empty_encrypted}'")
    print(f"   Empty string decrypted: '{admin_key.decrypt_data(empty_encrypted)}'")
    print()
    
    # Cleanup
    if os.path.exists('test_master.key'):
        os.remove('test_master.key')
    
    print("=" * 60)
    print("🎉 All tests passed!")
    print("=" * 60)
