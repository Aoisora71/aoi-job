#!/usr/bin/env python3
"""
Database migration script to add missing columns and tables
"""

import os
import sys
from sqlalchemy import text, inspect

# Add backend directory to path
BACKEND_DIR = os.path.dirname(__file__)
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from db import engine, get_session, Base
import models  # Import all models

def migrate():
    """Run database migrations"""
    print("🔄 Starting database migration...")
    
    with engine.connect() as conn:
        inspector = inspect(engine)
        
        # Check if user_settings table exists and has max_jobs column
        if 'user_settings' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('user_settings')]
            
            if 'max_jobs' not in columns:
                print("  ➕ Adding 'max_jobs' column to user_settings table...")
                try:
                    conn.execute(text("ALTER TABLE user_settings ADD COLUMN max_jobs INTEGER DEFAULT 50"))
                    conn.commit()
                    print("  ✅ Added 'max_jobs' column successfully")
                except Exception as e:
                    print(f"  ⚠️  Error adding max_jobs column: {e}")
                    conn.rollback()
            else:
                print("  ✓ 'max_jobs' column already exists")
        else:
            print("  ⚠️  user_settings table does not exist, will be created by init_db()")
        
        # Check if blocked_users table exists
        if 'blocked_users' not in inspector.get_table_names():
            print("  ➕ Creating 'blocked_users' table...")
            try:
                # Create table using raw SQL
                conn.execute(text("""
                    CREATE TABLE blocked_users (
                        id INTEGER NOT NULL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        employer_id VARCHAR(64),
                        client_username VARCHAR(255),
                        employer_name VARCHAR(255),
                        employer_display_name VARCHAR(255),
                        avatar_url TEXT,
                        profile_url TEXT,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users (id),
                        UNIQUE (user_id, employer_id),
                        UNIQUE (user_id, client_username)
                    )
                """))
                conn.commit()
                print("  ✅ Created 'blocked_users' table successfully")
            except Exception as e:
                print(f"  ⚠️  Error creating blocked_users table: {e}")
                conn.rollback()
        else:
            print("  ✓ 'blocked_users' table already exists")
    
    print("✅ Database migration completed!")

if __name__ == '__main__':
    migrate()
