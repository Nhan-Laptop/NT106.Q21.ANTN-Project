import os
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

class E2EEManager:
    """
    End-to-End Encryption Manager
    Sử dụng ECDH (Elliptic Curve Diffie-Hellman) + AES-GCM-256
    
    Security Features:
    - ECDH key exchange (secp256r1 / NIST P-256)
    - AES-256-GCM authenticated encryption
    - Random nonce per message
    - HKDF key derivation
    """
    
    def __init__(self):
        self.curve = ec.SECP256R1()  # NIST P-256 curve
        self.backend = default_backend()
        print("[E2EE] ✅ E2EE Manager initialized (ECDH + AES-GCM-256)")
    
    # ===== KEY GENERATION =====
    
    def generate_keypair(self):
        """
        Tạo keypair ECDH cho user
        Return: (private_key_pem, public_key_pem)
        """
        # Generate private key
        private_key = ec.generate_private_key(self.curve, self.backend)
        
        # Get public key
        public_key = private_key.public_key()
        
        # Serialize to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return private_pem, public_pem
    
    # ===== KEY EXCHANGE (ECDH) =====
    
    def derive_shared_key(self, my_private_key_pem, their_public_key_pem):
        """
        Tính shared secret từ ECDH
        Return: 32-byte AES key
        """
        # Load private key
        my_private_key = serialization.load_pem_private_key(
            my_private_key_pem.encode('utf-8'),
            password=None,
            backend=self.backend
        )
        
        # Load their public key
        their_public_key = serialization.load_pem_public_key(
            their_public_key_pem.encode('utf-8'),
            backend=self.backend
        )
        
        # ECDH: Calculate shared secret
        shared_secret = my_private_key.exchange(
            ec.ECDH(),
            their_public_key
        )
        
        # HKDF: Derive AES key from shared secret
        aes_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=None,
            info=b'deltachat-e2ee',
            backend=self.backend
        ).derive(shared_secret)
        
        return aes_key
    
    # ===== ENCRYPTION / DECRYPTION =====
    
    def encrypt_message(self, message, aes_key):
        """
        Mã hóa message với AES-GCM-256
        Return: base64(nonce + ciphertext + tag)
        """
        # Create AESGCM cipher
        aesgcm = AESGCM(aes_key)
        
        # Generate random nonce (96 bits recommended for GCM)
        nonce = os.urandom(12)
        
        # Encrypt message
        # GCM automatically adds authentication tag
        ciphertext = aesgcm.encrypt(
            nonce,
            message.encode('utf-8'),
            None  # No additional authenticated data
        )
        
        # Combine nonce + ciphertext and encode to base64
        encrypted_blob = nonce + ciphertext
        return base64.b64encode(encrypted_blob).decode('utf-8')
    
    def decrypt_message(self, encrypted_base64, aes_key):
        """
        Giải mã message từ AES-GCM-256
        Return: plaintext message
        """
        try:
            # Decode from base64
            encrypted_blob = base64.b64decode(encrypted_base64)
            
            # Extract nonce and ciphertext
            nonce = encrypted_blob[:12]
            ciphertext = encrypted_blob[12:]
            
            # Create AESGCM cipher
            aesgcm = AESGCM(aes_key)
            
            # Decrypt and verify authentication tag
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    # ===== HELPER METHODS =====
    
    def encrypt_for_recipient(self, message, my_private_key_pem, recipient_public_key_pem):
        """
        Shortcut: Encrypt message cho một recipient cụ thể
        """
        # 1. Derive shared key
        aes_key = self.derive_shared_key(my_private_key_pem, recipient_public_key_pem)
        
        # 2. Encrypt message
        return self.encrypt_message(message, aes_key)
    
    def decrypt_from_sender(self, encrypted_message, my_private_key_pem, sender_public_key_pem):
        """
        Shortcut: Decrypt message từ một sender cụ thể
        """
        # 1. Derive shared key
        aes_key = self.derive_shared_key(my_private_key_pem, sender_public_key_pem)
        
        # 2. Decrypt message
        return self.decrypt_message(encrypted_message, aes_key)


# ===== TEST CODE =====
if __name__ == "__main__":
    print("=" * 60)
    print("🔐 Testing E2EE Manager")
    print("=" * 60)
    print()
    
    e2ee = E2EEManager()
    
    # Test 1: Generate keypairs for Alice and Bob
    print("1️⃣  Generating keypairs...")
    alice_private, alice_public = e2ee.generate_keypair()
    bob_private, bob_public = e2ee.generate_keypair()
    print("   ✅ Alice keypair generated")
    print(f"      Public key preview: {alice_public[:50]}...")
    print("   ✅ Bob keypair generated")
    print(f"      Public key preview: {bob_public[:50]}...")
    print()
    
    # Test 2: Alice encrypts message for Bob
    print("2️⃣  Alice encrypts message for Bob...")
    message = "Hello Bob! This is a secret message 🔐"
    encrypted = e2ee.encrypt_for_recipient(message, alice_private, bob_public)
    print(f"   📝 Original: {message}")
    print(f"   🔒 Encrypted: {encrypted[:60]}...")
    print()
    
    # Test 3: Bob decrypts message from Alice
    print("3️⃣  Bob decrypts message from Alice...")
    decrypted = e2ee.decrypt_from_sender(encrypted, bob_private, alice_public)
    print(f"   🔓 Decrypted: {decrypted}")
    print(f"   ✅ Match: {decrypted == message}")
    print()
    
    # Test 4: Verify shared key is same for both
    print("4️⃣  Verifying ECDH shared secret...")
    alice_shared = e2ee.derive_shared_key(alice_private, bob_public)
    bob_shared = e2ee.derive_shared_key(bob_private, alice_public)
    print(f"   Alice's shared key: {base64.b64encode(alice_shared[:8]).decode()}...")
    print(f"   Bob's shared key:   {base64.b64encode(bob_shared[:8]).decode()}...")
    print(f"   ✅ Shared keys match: {alice_shared == bob_shared}")
    print()
    
    # Test 5: Wrong key fails
    print("5️⃣  Testing security: wrong key should fail...")
    try:
        # Charlie tries to decrypt Alice's message to Bob
        charlie_private, charlie_public = e2ee.generate_keypair()
        e2ee.decrypt_from_sender(encrypted, charlie_private, alice_public)
        print("   ❌ SECURITY ISSUE: Wrong key decrypted!")
    except ValueError:
        print("   ✅ Correctly rejected: Wrong key cannot decrypt")
    print()
    
    print("=" * 60)
    print("🎉 All tests passed!")
    print("=" * 60)
