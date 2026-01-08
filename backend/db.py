#!/usr/bin/env python3
"""
Database setup using SQLite and SQLAlchemy with memory optimizations
"""

from __future__ import annotations

import os
import gc
import weakref
from contextlib import contextmanager
from typing import Iterator, Optional
import threading
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool


DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')
DATABASE_URL = f'sqlite:///{DB_PATH}'

# Memory-optimized engine configuration
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # Connection timeout
    },
    poolclass=StaticPool,  # Use static pool for SQLite
    pool_pre_ping=True,   # Verify connections before use
    pool_recycle=3600,    # Recycle connections every hour
    future=True,
    echo=False,  # Disable SQL logging for production
)

# Memory-optimized session configuration
SessionLocal = sessionmaker(
    bind=engine, 
    autoflush=False, 
    autocommit=False, 
    future=True,
    expire_on_commit=False  # Prevent lazy loading after commit
)

class Base(DeclarativeBase):
    pass

# Session registry for cleanup
_active_sessions = weakref.WeakSet()
_session_lock = threading.Lock()

# Memory monitoring
_memory_stats = {
    'sessions_created': 0,
    'sessions_closed': 0,
    'last_cleanup': time.time()
}


@contextmanager
def get_session() -> Iterator[SessionLocal]:
    """Memory-optimized session context manager"""
    session = None
    try:
        with _session_lock:
            session = SessionLocal()
            _active_sessions.add(session)
            _memory_stats['sessions_created'] += 1
        
        yield session
        session.commit()
    except Exception:
        if session:
            session.rollback()
        raise
    finally:
        if session:
            with _session_lock:
                session.close()
                _active_sessions.discard(session)
                _memory_stats['sessions_closed'] += 1
                
                # Periodic cleanup
                _cleanup_if_needed()

def _cleanup_if_needed():
    """Periodic memory cleanup"""
    current_time = time.time()
    if current_time - _memory_stats['last_cleanup'] > 300:  # Every 5 minutes
        _memory_stats['last_cleanup'] = current_time
        
        # Force garbage collection
        collected = gc.collect()
        
        # Log memory stats
        active_count = len(_active_sessions)
        if active_count > 0:
            print(f"🧠 Memory: {active_count} active sessions, {collected} objects collected")

def get_memory_stats() -> dict:
    """Get current memory statistics"""
    return {
        **_memory_stats,
        'active_sessions': len(_active_sessions),
        'gc_counts': gc.get_count()
    }

def cleanup_sessions():
    """Force cleanup of all active sessions"""
    with _session_lock:
        for session in list(_active_sessions):
            try:
                session.close()
            except Exception:
                pass
        _active_sessions.clear()
        gc.collect()

def init_db():
    """Initialize database with memory optimizations"""
    # Import models to register mappings before create_all
    import models  # noqa: F401
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Set up memory-optimized event listeners
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set SQLite pragmas for memory optimization"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
        cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        cursor.execute("PRAGMA cache_size=10000")  # Increase cache
        cursor.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
        cursor.close()


