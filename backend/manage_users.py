#!/usr/bin/env python3
"""
User management utility script
Allows you to list, delete, and create users
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure backend dir is importable
BACKEND_DIR = os.path.dirname(__file__)
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from db import get_session, init_db
from models import User, UserSettings
from auth_service import auth_service

def list_users():
    """List all users in the database"""
    print("\n📋 Current Users:")
    print("-" * 60)
    with get_session() as session:
        users = session.query(User).all()
        if not users:
            print("No users found in database.")
            return
        
        for user in users:
            print(f"ID: {user.id}")
            print(f"  Email: {user.email or 'N/A'}")
            print(f"  Display Name: {user.display_name or 'N/A'}")
            print(f"  Created: {user.created_at}")
            print(f"  Has Password: {'Yes' if user.password_hash else 'No'}")
            print("-" * 60)

def delete_user(user_id: int = None, email: str = None):
    """Delete a user by ID or email"""
    with get_session() as session:
        if user_id:
            user = session.query(User).filter(User.id == user_id).first()
        elif email:
            user = session.query(User).filter(User.email == email).first()
        else:
            print("❌ Please provide either user_id or email")
            return False
        
        if not user:
            print(f"❌ User not found")
            return False
        
        # Delete associated settings
        settings = session.query(UserSettings).filter(UserSettings.user_id == user.id).first()
        if settings:
            session.delete(settings)
        
        # Delete user
        session.delete(user)
        session.commit()
        
        print(f"✅ User deleted: {user.email or f'ID {user.id}'}")
        return True

def delete_all_users():
    """Delete all users from the database"""
    with get_session() as session:
        users = session.query(User).all()
        if not users:
            print("No users to delete.")
            return
        
        count = len(users)
        for user in users:
            # Delete associated settings
            settings = session.query(UserSettings).filter(UserSettings.user_id == user.id).first()
            if settings:
                session.delete(settings)
            session.delete(user)
        
        session.commit()
        print(f"✅ Deleted {count} user(s)")

def create_user(email: str, password: str, display_name: str = None):
    """Create a new user"""
    result = auth_service.register_user(email, password, display_name)
    
    if result['success']:
        print(f"✅ User created successfully!")
        print(f"   Email: {result['user']['email']}")
        print(f"   Display Name: {result['user']['display_name']}")
        print(f"   User ID: {result['user']['id']}")
        return True
    else:
        print(f"❌ Failed to create user: {result.get('error', 'Unknown error')}")
        return False

def reset_database():
    """Reset the entire database (WARNING: Deletes all data!)"""
    import sqlite3
    from db import DB_PATH
    
    if not os.path.exists(DB_PATH):
        print("Database file not found.")
        return
    
    response = input("⚠️  WARNING: This will delete ALL data including users, jobs, and settings. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return
    
    try:
        # Close all connections first
        from db import engine
        engine.dispose()
        
        # Delete database file
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print(f"✅ Deleted database file: {DB_PATH}")
        
        # Recreate database
        init_db()
        print("✅ Database recreated successfully")
        
        # Create default user
        print("\nCreating default user...")
        create_user("admin@example.com", "admin123", "Admin User")
        
    except Exception as e:
        print(f"❌ Error resetting database: {e}")

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("""
User Management Utility

Usage:
  python manage_users.py list                    - List all users
  python manage_users.py create <email> <password> [display_name]  - Create new user
  python manage_users.py delete <user_id>         - Delete user by ID
  python manage_users.py delete-email <email>     - Delete user by email
  python manage_users.py delete-all               - Delete all users
  python manage_users.py reset                    - Reset entire database (WARNING: Deletes everything!)
        """)
        return
    
    command = sys.argv[1].lower()
    
    # Initialize database
    init_db()
    
    if command == 'list':
        list_users()
    
    elif command == 'create':
        if len(sys.argv) < 4:
            print("❌ Usage: python manage_users.py create <email> <password> [display_name]")
            return
        email = sys.argv[2]
        password = sys.argv[3]
        display_name = sys.argv[4] if len(sys.argv) > 4 else None
        create_user(email, password, display_name)
    
    elif command == 'delete':
        if len(sys.argv) < 3:
            print("❌ Usage: python manage_users.py delete <user_id>")
            return
        try:
            user_id = int(sys.argv[2])
            delete_user(user_id=user_id)
        except ValueError:
            print("❌ Invalid user_id. Must be a number.")
    
    elif command == 'delete-email':
        if len(sys.argv) < 3:
            print("❌ Usage: python manage_users.py delete-email <email>")
            return
        email = sys.argv[2]
        delete_user(email=email)
    
    elif command == 'delete-all':
        response = input("⚠️  Are you sure you want to delete ALL users? (yes/no): ")
        if response.lower() == 'yes':
            delete_all_users()
        else:
            print("Cancelled.")
    
    elif command == 'reset':
        reset_database()
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Run 'python manage_users.py' for usage information.")

if __name__ == "__main__":
    main()

