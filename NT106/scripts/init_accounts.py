"""
Script to initialize admin account and test users
Run once to setup the system
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Database
from core.e2ee_manager import E2EEManager

def initialize_accounts():
    """Create admin account and test users"""
    
    print("=" * 60)
    print("🚀 INITIALIZING DELTA CHAT ACCOUNTS")
    print("=" * 60)
    print()
    
    db = Database()
    e2ee = E2EEManager()
    
    # 1. Create admin account
    print("1️⃣  Creating admin account...")
    admin_email = "admin@gmail.com"
    admin_password = "admin@123123"
    
    # Check if admin exists
    existing_admin = db.get_user_by_email(admin_email)
    if existing_admin:
        print(f"   ⚠️  Admin already exists: {admin_email}")
    else:
        success = db.register_user(
            username="Administrator",
            email=admin_email,
            password=admin_password,
            role='admin'
        )
        
        if success:
            # Generate keypair
            private_key, public_key = e2ee.generate_keypair()
            db.save_public_key(admin_email, public_key)
            
            print(f"   ✅ Admin created: {admin_email}")
            print(f"   🔑 Password: {admin_password}")
        else:
            print(f"   ❌ Failed to create admin")
    
    print()
    
    # 2. Create test users
    print("2️⃣  Creating test users...")
    test_users = [
        ("Alice", "alice@example.com", "123123"),
        ("Bob", "bob@example.com", "123123"),
        ("Charlie", "charlie@example.com", "123123"),
        ("Diana", "diana@example.com", "123123"),
    ]
    
    created_count = 0
    for username, email, password in test_users:
        existing = db.get_user_by_email(email)
        if existing:
            print(f"   ⚠️  User exists: {email}")
            continue
        
        success = db.register_user(username, email, password, role='user')
        if success:
            # Generate keypair
            private_key, public_key = e2ee.generate_keypair()
            db.save_public_key(email, public_key)
            
            print(f"   ✅ Created: {username} ({email})")
            created_count += 1
        else:
            print(f"   ❌ Failed: {email}")
    
    print()
    print(f"   📊 Created {created_count} new test users")
    print()
    
    # 3. Summary
    print("=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    all_users = db.get_all_users()
    admin_users = [u for u in all_users if u['role'] == 'admin']
    regular_users = [u for u in all_users if u['role'] == 'user']
    
    print(f"\n👥 Total Users: {len(all_users)}")
    print(f"   🔐 Admins: {len(admin_users)}")
    print(f"   👤 Regular Users: {len(regular_users)}")
    
    print("\n🔐 Admin Account:")
    print(f"   Email: {admin_email}")
    print(f"   Password: {admin_password}")
    print(f"   Dashboard: http://127.0.0.1:5000/admin")
    
    print("\n👤 Test Accounts (all password: 123123):")
    for user in test_users:
        print(f"   - {user[0]}: {user[1]}")
    
    print("\n" + "=" * 60)
    print("🎉 INITIALIZATION COMPLETE!")
    print("=" * 60)
    print()
    print("📌 Next steps:")
    print("   1. Start app: python3 app.py")
    print("   2. Login as admin: http://127.0.0.1:5000")
    print("   3. Or login as test user to chat")
    print()

if __name__ == '__main__':
    try:
        initialize_accounts()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
