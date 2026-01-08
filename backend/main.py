#!/usr/bin/env python3
"""
Simple HTTP server for Crowdworks Monitor API
This avoids the Python 3.13 compatibility issues with Flask/FastAPI
"""

import http.server
import socketserver
import json
import threading
import time
import signal
import sys
import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from typing import Optional
import logging
from queue import Queue, Empty
import weakref
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Selenium imports for web automation
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium not available. Auto-bid will use simulation mode.")

# Ensure backend dir is importable when run from project root
BACKEND_DIR = os.path.dirname(__file__)
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from bot_service import (
    start_bot, stop_bot, pause_bot, resume_bot,
    get_bot_status, get_bot_jobs, mark_job_read,
    bot_instance, get_current_settings
)
from auth_service import auth_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    '/',
    '/health',
    '/api/auth/login',
    '/api/auth/verify'
]

# SSE clients registry (weak references to per-connection queues)
sse_clients: list = []
# Lock to protect sse_clients from race conditions
sse_clients_lock = threading.Lock()

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    timeout = 30  # Set request timeout to prevent hanging
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_sse = False  # Flag to track if this is an SSE connection
    
    def end_headers(self):
        try:
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cache-Control, Pragma')
            self.send_header('Access-Control-Allow-Credentials', 'true')
            # Only set Connection: close if not SSE (SSE needs keep-alive)
            if not getattr(self, '_is_sse', False):
                self.send_header('Connection', 'close')  # Ensure connection is closed after response
            super().end_headers()
        except (ConnectionAbortedError, BrokenPipeError, OSError):
            # Client disconnected - silently ignore, re-raise to be caught by caller
            raise
        except Exception as e:
            # Other errors - log but don't crash, re-raise to be caught by caller
            logger.debug(f"Error in end_headers: {e}")
            raise
    
    def handle_one_request(self):
        """Override to add error handling for each request"""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, BrokenPipeError, OSError) as e:
            # Client disconnected - this is normal (especially for SSE on refresh), don't log as error
            # Check errno to be more specific
            if hasattr(e, 'errno') and e.errno in (104, 32, 10053, 10054):
                # Connection reset/aborted - normal for client disconnections
                pass
            elif hasattr(e, 'winerror') and e.winerror in (10053, 10054):
                # Windows connection errors - normal
                pass
            else:
                # Other OSErrors - might be worth logging at debug level
                logger.debug(f"Client connection error: {e}")
        except Exception as e:
            # Log unexpected errors but don't crash
            logger.error(f"❌ Error handling request: {e}", exc_info=True)
            try:
                self.send_error(500, "Internal server error")
            except (ConnectionAbortedError, BrokenPipeError, OSError):
                # Client disconnected while sending error - normal
                pass
            except Exception:
                pass  # Ignore errors sending error response

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.end_headers()
        except (ConnectionAbortedError, BrokenPipeError, OSError):
            # Client disconnected - normal
            pass
        except Exception:
            # Other errors - silently ignore for OPTIONS
            pass
    
    def safe_write(self, data: bytes):
        """Safely write data, handling connection errors gracefully"""
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except (ConnectionAbortedError, BrokenPipeError, OSError) as e:
            # Client disconnected - this is normal, don't log as error
            # Check errno to be more specific
            if hasattr(e, 'errno') and e.errno in (104, 32, 10053, 10054):
                # Connection reset/aborted - normal
                pass
            elif hasattr(e, 'winerror') and e.winerror in (10053, 10054):
                # Windows connection errors - normal
                pass
            # Silently ignore - don't re-raise
        except Exception as e:
            # Other write errors - log at debug level but don't crash
            logger.debug(f"Write error in safe_write: {e}")
            # Don't re-raise - silently handle
    
    def safe_send_json(self, status_code: int, data: dict):
        """Safely send JSON response, handling connection errors gracefully"""
        try:
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.safe_write(json.dumps(data).encode())
        except (ConnectionAbortedError, BrokenPipeError, OSError) as e:
            # Client disconnected - this is normal, don't log as error
            # Check errno to be more specific
            if hasattr(e, 'errno') and e.errno in (104, 32, 10053, 10054):
                # Connection reset/aborted - normal
                pass
            elif hasattr(e, 'winerror') and e.winerror in (10053, 10054):
                # Windows connection errors - normal
                pass
            # Silently ignore
        except Exception as e:
            # Other errors - log at debug level but don't crash
            logger.debug(f"Error in safe_send_json: {e}")
            # Silently ignore

    def get_auth_token(self) -> Optional[str]:
        """Extract JWT token from Authorization header or query parameter"""
        # Try Authorization header first
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Try query parameter (for SSE/EventSource which doesn't support headers)
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        if 'token' in query_params and query_params['token']:
            return query_params['token'][0]
        
        return None

    def get_current_user_id(self) -> Optional[int]:
        """Get current user ID from JWT token"""
        token = self.get_auth_token()
        if not token:
            return None
        
        payload = auth_service.verify_token(token)
        if payload:
            return payload.get('user_id')
        return None

    def require_auth(self) -> Optional[int]:
        """Check if request is authenticated, return user_id or None"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Allow public endpoints
        if path in PUBLIC_ENDPOINTS:
            return None
        
        # Check authentication for protected endpoints
        user_id = self.get_current_user_id()
        if not user_id:
            try:
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"error": "Unauthorized", "message": "Authentication required"}
                self.safe_write(json.dumps(response).encode())
            except (ConnectionAbortedError, BrokenPipeError, OSError):
                # Client disconnected - normal
                pass
            # Don't log 401 errors - they're expected when user is not authenticated
            return None
        
        return user_id

    def do_GET(self):
        """Handle GET requests with proper error handling and connection management"""
        # Wrap entire method in comprehensive error handling to prevent crashes
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"message": "Crowdworks Monitor API", "version": "1.0.0"}
                self.safe_write(json.dumps(response).encode())
            
            elif path == '/health':
                # Health endpoint - should be fast and always respond
                try:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                    self.end_headers()
                    # Include server start time to detect restarts
                    server_start_time = getattr(run_server, '_start_time', None)
                    if server_start_time is None:
                        # First time, set it
                        run_server._start_time = time.time()
                        server_start_time = run_server._start_time
                    response = {
                        "status": "healthy",
                        "timestamp": datetime.now().isoformat(),
                        "server_start_time": server_start_time,
                        "uptime": int(time.time() - server_start_time)
                    }
                    self.safe_write(json.dumps(response).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log
                    pass
                except Exception as e:
                    # Log but don't crash - health endpoint should be robust
                    logger.debug(f"Health check error: {e}")
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps({"status": "error", "message": str(e)}).encode())
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
        
            elif path == '/api/auth/verify':
                # Verify token endpoint
                try:
                    user_id = self.get_current_user_id()
                    if user_id:
                        user = auth_service.get_user_by_id(user_id)
                        if user:
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            response = {
                                "valid": True,
                                "user": {
                                    "id": user.id,
                                    "email": user.email,
                                    "display_name": user.display_name
                                }
                            }
                            self.safe_write(json.dumps(response).encode())
                        else:
                            self.send_response(401)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            response = {"valid": False, "error": "User not found"}
                            self.safe_write(json.dumps(response).encode())
                    else:
                        self.send_response(401)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        response = {"valid": False, "error": "Invalid or missing token"}
                        self.safe_write(json.dumps(response).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log as error
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/auth/verify: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/jobs':
                # Require authentication
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    jobs = get_bot_jobs()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"jobs": jobs}
                    self.safe_write(json.dumps(response).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log as error
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/jobs: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/bot/status':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    status = get_bot_status()
                    # Ensure all required fields are present
                    status_response = {
                    'running': status.get('running', False),
                    'paused': status.get('paused', False),
                    'jobs_found': status.get('jobs_found', 0),
                    'unread_count': status.get('unread_count', 0),
                    'uptime': status.get('uptime', 0),
                    'categories': status.get('categories', []),
                    'keywords': status.get('keywords', []),
                    'interval': status.get('interval', 60),
                        'auto_bid_enabled': status.get('auto_bid_enabled', False)
                    }
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps(status_response).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log as error
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/bot/status: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/settings':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    # Single-user mode: always use user_id=1
                    settings = get_current_settings()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps(settings).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log as error
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/settings GET: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/categories':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    "categories": [
                        {"id": "all", "name": "All Categories"},
                        {"id": "web", "name": "Web Development"},
                        {"id": "system", "name": "System Development"},
                        {"id": "ec", "name": "E-commerce"},
                        {"id": "app", "name": "Mobile App Development"},
                        {"id": "ai", "name": "AI & Machine Learning"},
                        {"id": "other", "name": "Other"}
                    ]
                }
                self.safe_write(json.dumps(response).encode())
            
            elif path == '/api/auto-bid/test':
                # Simple test endpoint to verify backend connectivity
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    "success": True,
                    "message": "Auto-bid backend is working",
                    "timestamp": datetime.now().isoformat(),
                    "selenium_available": SELENIUM_AVAILABLE,
                    "simulation_mode": os.environ.get('AUTO_BID_SIMULATION', 'true').lower() == 'true'
                }
                self.safe_write(json.dumps(response).encode())
            
            elif path == '/api/auto-bid/config':
                # Configuration endpoint for auto-bid settings
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    "selenium_available": SELENIUM_AVAILABLE,
                    "simulation_mode": os.environ.get('AUTO_BID_SIMULATION', 'true').lower() == 'true',
                    "webdriver_available": SELENIUM_AVAILABLE,
                    "instructions": {
                        "simulation_mode": "Auto-bid submissions are simulated for testing. No actual bids are sent to Crowdworks.",
                        "real_mode": "To enable real bid submission, set AUTO_BID_SIMULATION=false and ensure proper Crowdworks login credentials."
                    }
                }
                self.safe_write(json.dumps(response).encode())
            
            elif path.startswith('/api/jobs/stream'):
                # Server-Sent Events stream for real-time jobs
                # Note: path may include query params, so we check with startswith
                # Wrap entire SSE endpoint in comprehensive error handling to prevent crashes
                user_id = None
                client_queue = None
                connection_closed = False
                
                try:
                    user_id = self.require_auth()
                    if user_id is None:
                        return
                except Exception as auth_err:
                    # Auth error - don't crash, just return
                    logger.debug(f"Auth error in SSE: {auth_err}")
                    return
                
                try:
                    # Mark as SSE connection to prevent Connection: close header
                    self._is_sse = True
                    
                    # Send headers - wrap each step individually
                    try:
                        self.send_response(200)
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        return  # Client disconnected - normal
                    except Exception:
                        return  # Any error - just return, don't crash
                    
                    try:
                        self.send_header('Content-Type', 'text/event-stream')
                        self.send_header('Cache-Control', 'no-cache')
                        self.send_header('Connection', 'keep-alive')
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        return  # Client disconnected - normal
                    except Exception:
                        return  # Any error - just return
                    
                    try:
                        self.end_headers()
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        return  # Client disconnected - normal
                    except Exception:
                        return  # Any error - just return

                    # Create client queue
                    try:
                        client_queue = Queue(maxsize=100)
                        with sse_clients_lock:
                            sse_clients.append(weakref.ref(client_queue))
                    except Exception:
                        # If queue creation fails, just return
                        return

                    # Send initial snapshot
                    try:
                        snapshot = get_bot_jobs() or []
                        # Use max_jobs from bot instance
                        max_jobs = getattr(bot_instance, 'max_jobs', 50)
                        snapshot = snapshot[:max_jobs]
                        compressed_snapshot = []
                        for job in snapshot:
                            try:
                                compressed_job = {
                                    'id': job.get('id'),
                                    'title': job.get('title'),
                                    'description': job.get('description'),
                                    'original_description': job.get('original_description'),
                                    'client': job.get('client'),
                                    'client_display_name': job.get('client_display_name'),
                                    'client_username': job.get('client_username'),
                                    'avatar': job.get('avatar'),
                                    'employer_id': job.get('employer_id'),
                                    'employer_contracts_count': job.get('employer_contracts_count'),
                                    'employer_completed_count': job.get('employer_completed_count'),
                                    'employer_last_activity': job.get('employer_last_activity'),
                                    'link': job.get('link'),
                                    'posted_time_formatted': job.get('posted_time_formatted'),
                                    'posted_time_relative': job.get('posted_time_relative'),
                                    'job_price': job.get('job_price'),
                                    'category': job.get('category'),
                                    'is_read': job.get('is_read', False),
                                    'bid_generated': job.get('bid_generated', False),
                                    'suitability_score': job.get('suitability_score'),
                                    'auto_bid_enabled': job.get('auto_bid_enabled', False),
                                    'evaluation_rate': job.get('evaluation_rate'),
                                    'order_count': job.get('order_count'),
                                    'evaluation_count': job.get('evaluation_count'),
                                    'contract_rate': job.get('contract_rate'),
                                    'identity_verified': job.get('identity_verified'),
                                    'identity_status': job.get('identity_status'),
                                    'budget_info': job.get('budget_info')
                                }
                                compressed_snapshot.append(compressed_job)
                            except Exception:
                                # Skip invalid jobs
                                continue
                        
                        if compressed_snapshot:
                            data = json.dumps({"type": "snapshot", "jobs": compressed_snapshot})
                            try:
                                self.safe_write(f"data: {data}\n\n".encode('utf-8'))
                            except (ConnectionAbortedError, BrokenPipeError, OSError):
                                return  # Client disconnected - normal
                            except Exception:
                                # Write failed - continue to loop
                                pass
                    except Exception as snapshot_error:
                        # Snapshot failed - continue to loop anyway
                        logger.debug(f"Error sending initial snapshot: {snapshot_error}")

                    # Event loop - check for client disconnection on each iteration
                    max_iterations = 10000
                    iteration_count = 0
                    
                    while not shutdown_flag.is_set() and not connection_closed and iteration_count < max_iterations:
                        iteration_count += 1
                        try:
                            # Check if connection is still alive by trying to get an event
                            event = client_queue.get(timeout=15)
                            try:
                                data = json.dumps(event)
                                self.safe_write(f"data: {data}\n\n".encode('utf-8'))
                            except (ConnectionAbortedError, BrokenPipeError, OSError):
                                # Client disconnected - normal for SSE
                                connection_closed = True
                                break
                            except Exception:
                                # Write error - break loop
                                connection_closed = True
                                break
                        except Empty:
                            # heartbeat comment to keep connection alive
                            try:
                                self.safe_write(b": keep-alive\n\n")
                            except (ConnectionAbortedError, BrokenPipeError, OSError):
                                # Client disconnected - normal for SSE
                                connection_closed = True
                                break
                            except Exception:
                                # Heartbeat failed - break loop
                                connection_closed = True
                                break
                        except (ConnectionAbortedError, BrokenPipeError, OSError):
                            # Client disconnected during queue.get()
                            connection_closed = True
                            break
                        except Exception:
                            # Any other error - break loop
                            connection_closed = True
                            break
                            
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - this is completely normal for SSE on refresh
                    # Silently return - no logging needed
                    pass
                except Exception as e:
                    # Log unexpected errors but don't crash
                    logger.debug(f"SSE endpoint error (non-fatal): {e}")
                finally:
                    # Remove dead refs - always run cleanup
                    try:
                        if client_queue is not None:
                            alive = []
                            with sse_clients_lock:
                                for r in sse_clients:
                                    try:
                                        q = r()
                                        if q is not None and q is not client_queue:
                                            alive.append(r)
                                    except Exception:
                                        pass
                                sse_clients[:] = alive
                    except Exception:
                        pass
            
            elif path == '/api/favorites':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from favorite_clients_service import favorite_clients_service
                    
                    # Single-user mode: always use user_id=1
                    favorites = favorite_clients_service.get_favorites(1)
                    
                    # Ensure all favorites have complete data
                    enriched_favorites = []
                    for fav in favorites:
                        enriched_fav = dict(fav) if isinstance(fav, dict) else {
                            'id': getattr(fav, 'id', None),
                            'employer_id': getattr(fav, 'employer_id', ''),
                            'employer_name': getattr(fav, 'employer_name', None),
                            'employer_display_name': getattr(fav, 'employer_display_name', None),
                            'avatar_url': getattr(fav, 'avatar_url', None),
                            'profile_url': getattr(fav, 'profile_url', None),
                            'last_activity_hours': getattr(fav, 'last_activity_hours', None),
                            'contracts_count': getattr(fav, 'contracts_count', None),
                            'completed_count': getattr(fav, 'completed_count', None),
                            'last_status_update': getattr(fav, 'last_status_update', None),
                            'created_at': getattr(fav, 'created_at', None)
                        }
                        # Convert datetime to string if needed
                        if enriched_fav.get('last_status_update') and hasattr(enriched_fav['last_status_update'], 'isoformat'):
                            enriched_fav['last_status_update'] = enriched_fav['last_status_update'].isoformat()
                        if enriched_fav.get('created_at') and hasattr(enriched_fav['created_at'], 'isoformat'):
                            enriched_fav['created_at'] = enriched_fav['created_at'].isoformat()
                        enriched_favorites.append(enriched_fav)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps({'favorites': enriched_favorites}).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/favorites GET: {e}", exc_info=True)
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps({'error': str(e), 'favorites': []}).encode())
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/blocked':
                # GET request - return blocked users list
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from db import get_session
                    from models import BlockedUser
                    
                    with get_session() as session:
                        blocked_users = session.query(BlockedUser).filter(
                            BlockedUser.user_id == 1
                        ).all()
                        
                        enriched_blocked = []
                        for blocked in blocked_users:
                            enriched_blocked.append({
                                'id': blocked.id,
                                'employer_id': blocked.employer_id,
                                'client_username': blocked.client_username,
                                'employer_name': blocked.employer_name,
                                'employer_display_name': blocked.employer_display_name,
                                'avatar_url': blocked.avatar_url,
                                'profile_url': blocked.profile_url,
                                'created_at': blocked.created_at.isoformat() if blocked.created_at else None
                            })
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps({'blocked': enriched_blocked}).encode())
                except Exception as e:
                    logger.error(f"Error in /api/blocked GET: {e}", exc_info=True)
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps({'error': str(e), 'blocked': []}).encode())
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/profile':
                # Get user profile
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    profile = auth_service.get_user_profile(user_id)
                    if profile:
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(profile).encode())
                    else:
                        self.send_response(404)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps({'error': 'Profile not found'}).encode())
                except Exception as e:
                    logger.error(f"Error in /api/profile GET: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/notifications/settings':
                # GET request - return current notification settings
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from db import get_session
                    from models import UserSettings
                    
                    with get_session() as session:
                        settings = session.query(UserSettings).filter(UserSettings.user_id == 1).first()
                        if settings:
                            response = {
                                "discord_webhook": settings.discord_webhook or "",
                                "telegram_token": settings.telegram_token or "",
                                "telegram_chat_id": settings.telegram_chat_id or ""
                            }
                        else:
                            response = {
                                "discord_webhook": "",
                                "telegram_token": "",
                                "telegram_chat_id": ""
                            }
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps(response).encode())
                except Exception as e:
                    logger.error(f"Error in /api/notifications/settings GET: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            else:
                self.send_response(404)
                self.end_headers()
                self.safe_write(b'Not Found')
        
        except (ConnectionAbortedError, BrokenPipeError, OSError) as conn_err:
            # Client disconnected - this is normal, especially for SSE on refresh
            # Check errno to be more specific
            if hasattr(conn_err, 'errno') and conn_err.errno in (104, 32, 10053, 10054):
                # Connection reset/aborted - normal, don't log
                pass
            elif hasattr(conn_err, 'winerror') and conn_err.winerror in (10053, 10054):
                # Windows connection errors - normal
                pass
            else:
                logger.debug(f"Client connection error in do_GET: {conn_err}")
        except Exception as e:
            # Log unexpected errors but don't crash the server
            logger.error(f"❌ Unhandled error in do_GET: {e}", exc_info=True)
            try:
                self.send_error(500, f"Server error: {str(e)}")
            except (ConnectionAbortedError, BrokenPipeError, OSError):
                # Client disconnected while sending error - normal
                pass
            except Exception:
                # Even sending error can fail - don't crash
                pass

    def do_DELETE(self):
        """Handle DELETE requests"""
        self.do_POST()  # Route to do_POST which checks method
    
    def do_POST(self):
        """Handle POST requests with proper error handling and connection management"""
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            method = self.command  # GET, POST, DELETE, etc.
            
            if path == '/api/auth/login':
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    email = data.get('email', '').strip()
                    password = data.get('password', '')
                    
                    if not email or not password:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        response = {"success": False, "error": "Email and password are required"}
                        self.safe_write(json.dumps(response).encode())
                        return
                    
                    result = auth_service.login_user(email, password)
                    
                    if result['success']:
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(result).encode())
                    else:
                        self.send_response(401)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(result).encode())
                except Exception as e:
                    logger.error(f"Login error: {e}")
                    self.send_error(500, str(e))
            
            elif path == '/api/auth/register':
                # Registration disabled - single-user mode
                try:
                    self.send_response(403)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {
                        "success": False,
                        "error": "Registration is disabled. This application is in single-user mode."
                    }
                    self.safe_write(json.dumps(response).encode())
                except Exception as e:
                    logger.error(f"Register error: {e}")
                    self.send_error(500, str(e))
        
            elif path.startswith('/api/jobs/') and path.endswith('/mark-read'):
                user_id = self.require_auth()
                if user_id is None:
                    return
                job_id = path.split('/')[-2]
                try:
                    mark_job_read(job_id)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"success": True}
                    self.safe_write(json.dumps(response).encode())
                except Exception as e:
                    self.send_error(500, str(e))
            
            elif path == '/api/settings':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    # Single-user mode: always uses user_id=1
                    bot_instance.set_settings(data)
                    response_settings = bot_instance.get_settings()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"success": True, "settings": response_settings}
                    self.safe_write(json.dumps(response).encode())
                except Exception as e:
                    logger.error(f"Error in /api/settings POST: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/data/clear-bids':
                # Clear all bids from the database
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from db import get_session
                    from models import Bid
                    
                    with get_session() as session:
                        deleted_count = session.query(Bid).delete()
                        session.commit()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {
                        "success": True,
                        "message": f"Successfully deleted {deleted_count} bid(s)",
                        "deleted_count": deleted_count
                    }
                    self.safe_write(json.dumps(response).encode())
                    logger.info(f"✅ Cleared {deleted_count} bid(s) from database")
                except Exception as e:
                    logger.error(f"Error clearing bids: {e}", exc_info=True)
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/data/clear-jobs':
                # Clear all jobs from the database
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from db import get_session
                    from models import Job
                    
                    with get_session() as session:
                        deleted_count = session.query(Job).delete()
                        session.commit()
                    
                    # Also clear the bot's current jobs list
                    if bot_instance:
                        bot_instance.current_jobs = []
                        bot_instance.last_sent_job_ids.clear()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {
                        "success": True,
                        "message": f"Successfully deleted {deleted_count} job(s)",
                        "deleted_count": deleted_count
                    }
                    self.safe_write(json.dumps(response).encode())
                    logger.info(f"✅ Cleared {deleted_count} job(s) from database")
                except Exception as e:
                    logger.error(f"Error clearing jobs: {e}", exc_info=True)
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
                
            elif path == '/api/bot/start':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        post_data = self.rfile.read(content_length)
                        settings = json.loads(post_data.decode('utf-8'))
                    else:
                        # If no settings provided, use current settings (single-user mode: always user_id=1)
                        settings = get_current_settings()
                    
                    # Start bot with error handling to prevent server crash
                    # Send response first, then start bot in background to avoid blocking
                    try:
                        logger.info(f"🚀 Starting bot with settings: categories={settings.get('categories', [])}")
                        
                        # Send success response FIRST before starting bot thread
                        # This ensures client gets response even if bot start fails
                        response = {"success": True, "message": "Bot starting..."}
                        self.safe_send_json(200, response)
                        
                        # Force flush to ensure response is fully sent before starting bot
                        try:
                            import sys
                            sys.stdout.flush()
                            sys.stderr.flush()
                        except Exception:
                            pass
                        
                        # Start bot in a separate thread to avoid blocking the HTTP response
                        # Use a robust wrapper that catches ALL exceptions including system-level ones
                        def start_bot_async():
                            """Safely start bot in background thread with maximum error protection"""
                            try:
                                # Add a delay to ensure HTTP response is fully sent and connection is closed
                                import time
                                time.sleep(0.5)  # Increased delay to ensure response is sent
                                
                                # Wrap the entire bot startup in multiple layers of protection
                                try:
                                    logger.info("🔄 Attempting to start bot...")
                                    start_bot(settings)
                                    logger.info("✅ Bot started successfully")
                                except KeyboardInterrupt:
                                    # Don't catch keyboard interrupts - let them propagate
                                    logger.warning("⚠️ Bot startup interrupted by keyboard")
                                    raise
                                except SystemExit:
                                    # Don't catch system exits - let them propagate
                                    logger.warning("⚠️ Bot startup interrupted by system exit")
                                    raise
                                except BaseException as bot_error:
                                    # Catch ALL exceptions including system-level ones
                                    logger.error(f"❌ Error starting bot: {bot_error}", exc_info=True)
                                    # Error is logged, but don't crash the server
                                    try:
                                        # Try to reset bot state if possible (bot_instance is already imported at top)
                                        if hasattr(bot_instance, 'is_running'):
                                            bot_instance.is_running = False
                                            bot_instance.is_paused = False
                                            bot_instance.last_error = f"Startup failed: {str(bot_error)}"
                                        logger.info("🔄 Bot state reset after startup failure")
                                    except Exception as cleanup_error:
                                        logger.error(f"❌ Error during bot cleanup: {cleanup_error}", exc_info=True)
                                        # Continue - don't let cleanup errors crash the thread
                            except KeyboardInterrupt:
                                # Don't log keyboard interrupts
                                raise
                            except SystemExit:
                                # Don't catch system exits
                                raise
                            except BaseException as thread_error:
                                # Catch any other errors in the thread wrapper itself
                                logger.error(f"❌ Fatal error in bot start thread wrapper: {thread_error}", exc_info=True)
                                # Try to reset bot state (bot_instance is already imported at top)
                                try:
                                    if hasattr(bot_instance, 'is_running'):
                                        bot_instance.is_running = False
                                        bot_instance.is_paused = False
                                except Exception:
                                    pass  # Ignore errors in cleanup









                        
                        # Now start bot in background thread
                        try:
                            import threading
                            bot_thread = threading.Thread(target=start_bot_async, daemon=True, name="BotStartThread")
                            bot_thread.start()
                            logger.info("✅ Bot start thread launched successfully")
                        except Exception as thread_error:
                            logger.error(f"❌ Failed to create bot start thread: {thread_error}", exc_info=True)
                            # Don't crash - response already sent
                            # Try to reset bot state (bot_instance is already imported at top)
                            try:
                                if hasattr(bot_instance, 'is_running'):
                                    bot_instance.is_running = False
                                    bot_instance.is_paused = False
                            except Exception:
                                pass
                    







                    except BaseException as bot_error:
                        logger.error(f"❌ Critical error in bot start handler: {bot_error}", exc_info=True)
                        try:
                            self.safe_send_json(500, {"success": False, "message": f"Server error: {str(bot_error)}"})
                        except Exception:
                            pass  # If we can't send response, that's okay - server should continue
                            self.end_headers()
                            response = {
                                "success": False,
                                "message": f"Failed to start bot: {str(bot_error)}"
                            }
                            self.safe_write(json.dumps(response).encode())
                        except Exception:
                            pass  # Ignore errors sending error response
                        return
                except Exception as e:
                    logger.error(f"❌ Error in /api/bot/start endpoint: {e}", exc_info=True)
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass








                
            elif path == '/api/bot/stop':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    stop_bot()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"success": True, "message": "Bot stopped"}
                    self.safe_write(json.dumps(response).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log as error
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/bot/stop: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
                
            elif path == '/api/bot/pause':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    pause_bot()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"success": True, "message": "Bot paused"}
                    self.safe_write(json.dumps(response).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log as error
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/bot/pause: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
                
            elif path == '/api/bot/resume':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    resume_bot()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"success": True, "message": "Bot resumed"}
                    self.safe_write(json.dumps(response).encode())
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    # Client disconnected - normal, don't log as error
                    pass
                except Exception as e:
                    logger.error(f"Error in /api/bot/resume: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
                
            elif path.startswith('/api/bidding/generate/'):
                user_id = self.require_auth()
                if user_id is None:
                    return
                job_id = path.split('/')[-1]
                try:
                    jobs = get_bot_jobs()
                    job = next((j for j in jobs if j['id'] == job_id), None)
                    
                    if not job:
                        self.send_error(404, "Job not found")
                        return
                
                    # Read optional prompt selection
                    prompt_template = None
                    try:
                        content_length = int(self.headers.get('Content-Length') or 0)
                        if content_length > 0:
                            post_data = self.rfile.read(content_length)
                            body = json.loads(post_data.decode('utf-8'))
                            prompt_template = body.get('promptTemplate')
                            
                            # Check for custom prompt selection
                            prompt_index = body.get('promptIndex')
                            print(f"Received prompt index: {prompt_index}")
                            
                            # Get selected model
                            selected_model = body.get('model') or bot_instance.get_selected_model()
                            print(f"Using model: {selected_model}")
                            
                            if prompt_index and 1 <= prompt_index <= 3:
                                custom_prompt = bot_instance.get_custom_prompt(prompt_index)
                                print(f"Retrieved custom prompt {prompt_index}: {custom_prompt[:100] if custom_prompt else 'None'}...")
                                if custom_prompt:
                                    prompt_template = custom_prompt
                                    print(f"Using custom prompt {prompt_index} for bid generation")
                                else:
                                    print(f"Custom prompt {prompt_index} is empty, rejecting bid generation")
                                    self.send_error(400, f"Custom prompt {prompt_index} is not configured")
                                    return
                            else:
                                print("Invalid prompt index, rejecting bid generation")
                                self.send_error(400, "Only custom prompts (1-3) are allowed. Please configure your custom prompts in settings.")
                                return
                    except Exception as e:
                        print(f"Error processing prompt selection: {e}")
                        pass

                    from chatgpt_service import chatgpt_service
                    bid_result = chatgpt_service.generate_bid(job, prompt_template, selected_model)

                    if bid_result.get('success'):
                        bid_content = bid_result.get('bid_content')
                        job['bid_generated'] = True
                        job['bid_content'] = bid_content
                        job['bid_generated_by'] = bid_result.get('generated_by')
                        # Store the prompt index used for this bid
                        if prompt_index:
                            job['bid_prompt_index'] = prompt_index
                        # Store the model used for this bid
                        job['bid_model'] = selected_model

                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        response = {
                            "success": True,
                            "bid": {
                                "content": bid_content,
                                "job_id": job_id,
                                "generated_by": bid_result.get('generated_by'),
                                "model": bid_result.get('model'),
                                "prompt_index": prompt_index
                            }
                        }
                        self.safe_write(json.dumps(response).encode())
                    else:
                        self.send_error(500, "Failed to generate bid")
                except Exception as e:
                    print(f"Error in auto-bid submission: {e}")
                    self.send_error(500, str(e))
            
            elif path == '/api/auto-bid/submit':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    print(f"🔔 Received auto-bid request at path: {path}")
                    content_length = int(self.headers.get('Content-Length', 0))
                    print(f"📏 Content length: {content_length}")
                    
                    if content_length > 0:
                        post_data = self.rfile.read(content_length)
                        body = json.loads(post_data.decode('utf-8'))
                    print(f"📦 Request body: {body}")
                    
                    job_id = body.get('jobId')
                    prompt_index = body.get('promptIndex')
                    job_url = body.get('jobUrl')
                    bid_content = body.get('bidContent')  # Get bid content from request body
                    
                    print(f"🚀 Auto-bid request for job {job_id} with prompt {prompt_index}")
                    print(f"🌐 Job URL: {job_url}")
                    print(f"📝 Bid content length: {len(bid_content) if bid_content else 0} characters")
                    
                    # Get the job data
                    job = None
                    for j in bot_instance.get_jobs():
                        if j['id'] == job_id:
                            job = j
                            break
                    
                    # If job not found in bot's job list, create a mock job for testing
                    if not job:
                        print(f"⚠️ Job {job_id} not found in bot's job list, creating mock job for testing")
                        job = {
                            'id': job_id,
                            'title': 'Test Job (Mock)',
                            'client': 'Test Client',
                            'job_price': {'type': 'fixed', 'amount': 50000},
                            'description': 'This is a test job for auto-bid testing'
                        }
                    
                    # Use bid content from request body, fallback to job data
                    if not bid_content:
                        bid_content = job.get('bid_content', '')
                    
                    if not bid_content:
                        self.send_error(400, "No bid content available")
                        return
                    
                        # Submit the auto-bid
                        success = submit_auto_bid_to_crowdworks(job_url, bid_content, job)
                        
                        if success:
                            # Mark job as bid submitted
                            job['bid_submitted'] = True
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            response = {
                                "success": True,
                                "message": "Auto-bid submitted successfully"
                            }
                            self.safe_write(json.dumps(response).encode())
                        else:
                            self.send_error(500, "Failed to submit auto-bid")
                    else:
                        self.send_error(400, "No data provided")

                except Exception as e:
                    self.send_error(500, str(e))
                
            elif path == '/api/bidding/submit':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"success": True, "message": "Bid submitted successfully"}
                    self.safe_write(json.dumps(response).encode())
                except Exception as e:
                    self.send_error(500, str(e))
        
            elif path == '/api/favorites' and method == 'POST':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from favorite_clients_service import favorite_clients_service
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        # POST - Add favorite
                        post_data = self.rfile.read(content_length)
                        data = json.loads(post_data.decode('utf-8'))
                        
                        employer_id = data.get('employer_id')
                        if not employer_id:
                            self.send_error(400, "employer_id is required")
                            return
                        
                        result = favorite_clients_service.add_favorite(
                            user_id=user_id,
                            employer_id=employer_id,
                            employer_name=data.get('employer_name'),
                            employer_display_name=data.get('employer_display_name'),
                            avatar_url=data.get('avatar_url'),
                            profile_url=data.get('profile_url')
                        )
                        
                        self.send_response(200 if result.get('success') else 400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(result).encode())
                except Exception as e:
                    logger.error(f"Error in /api/favorites POST: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
        
            elif path.startswith('/api/favorites/') and len(path.split('/')) == 4 and method == 'DELETE':
                # DELETE /api/favorites/:id
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from favorite_clients_service import favorite_clients_service
                    favorite_id = int(path.split('/')[-1])
                    result = favorite_clients_service.remove_favorite(user_id, favorite_id)
                    
                    self.send_response(200 if result.get('success') else 404)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps(result).encode())
                except ValueError:
                    self.send_error(400, "Invalid favorite ID")
                except Exception as e:
                    logger.error(f"Error in /api/favorites DELETE: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/blocked' and method == 'POST':
                # POST - Add blocked user
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from db import get_session
                    from models import BlockedUser
                    
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        post_data = self.rfile.read(content_length)
                        data = json.loads(post_data.decode('utf-8'))
                        
                        employer_id = data.get('employer_id')
                        client_username = data.get('client_username')
                        
                        if not employer_id and not client_username:
                            self.send_error(400, "employer_id or client_username is required")
                            return
                        
                        with get_session() as session:
                            # Check if already blocked
                            from sqlalchemy import or_
                            query = session.query(BlockedUser).filter(
                                BlockedUser.user_id == user_id
                            )
                            
                            # Build OR conditions for matching
                            conditions = []
                            if employer_id:
                                conditions.append(BlockedUser.employer_id == employer_id)
                            if client_username:
                                conditions.append(BlockedUser.client_username == client_username)
                            
                            if conditions:
                                query = query.filter(or_(*conditions))
                            
                            existing = query.first()
                            
                            if existing:
                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self.end_headers()
                                self.safe_write(json.dumps({
                                    'success': True,
                                    'message': 'User already blocked',
                                    'id': existing.id
                                }).encode())
                                return
                            
                            blocked_user = BlockedUser(
                                user_id=user_id,
                                employer_id=employer_id,
                                client_username=client_username,
                                employer_name=data.get('employer_name'),
                                employer_display_name=data.get('employer_display_name'),
                                avatar_url=data.get('avatar_url'),
                                profile_url=data.get('profile_url')
                            )
                            session.add(blocked_user)
                            session.commit()
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.safe_write(json.dumps({
                                'success': True,
                                'message': 'User blocked successfully',
                                'id': blocked_user.id
                            }).encode())
                except Exception as e:
                    logger.error(f"Error in /api/blocked POST: {e}", exc_info=True)
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path.startswith('/api/blocked/') and len(path.split('/')) == 4 and method == 'DELETE':
                # DELETE /api/blocked/:id
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from db import get_session
                    from models import BlockedUser
                    
                    blocked_id = int(path.split('/')[-1])
                    
                    with get_session() as session:
                        blocked_user = session.query(BlockedUser).filter(
                            BlockedUser.id == blocked_id,
                            BlockedUser.user_id == user_id
                        ).first()
                        
                        if not blocked_user:
                            self.send_response(404)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.safe_write(json.dumps({
                                'success': False,
                                'message': 'Blocked user not found'
                            }).encode())
                            return
                        
                        session.delete(blocked_user)
                        session.commit()
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps({
                            'success': True,
                            'message': 'User unblocked successfully'
                        }).encode())
                except ValueError:
                    self.send_error(400, "Invalid blocked user ID")
                except Exception as e:
                    logger.error(f"Error in /api/blocked DELETE: {e}", exc_info=True)
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/profile' and method == 'POST':
                # Update profile (email, display_name)
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    email = data.get('email', '').strip() if data.get('email') else None
                    display_name = data.get('display_name', '').strip() if data.get('display_name') else None
                    
                    if not email and display_name is None:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        response = {"success": False, "error": "At least one field (email or display_name) must be provided"}
                        self.safe_write(json.dumps(response).encode())
                        return
                    
                    result = auth_service.update_profile(user_id, email=email, display_name=display_name)
                    
                    if result['success']:
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(result).encode())
                    else:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(result).encode())
                except Exception as e:
                    logger.error(f"Error updating profile: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/profile/password' and method == 'POST':
                # Change password
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    old_password = data.get('old_password', '')
                    new_password = data.get('new_password', '')
                    
                    if not old_password or not new_password:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        response = {"success": False, "error": "Both old_password and new_password are required"}
                        self.safe_write(json.dumps(response).encode())
                        return
                    
                    result = auth_service.change_password(user_id, old_password, new_password)
                    
                    if result['success']:
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(result).encode())
                    else:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(result).encode())
                except Exception as e:
                    logger.error(f"Error changing password: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/notifications/settings':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        post_data = self.rfile.read(content_length)
                        data = json.loads(post_data.decode('utf-8'))
                        
                        # Update notification settings in database
                        from db import get_session
                        from models import UserSettings
                        
                        with get_session() as session:
                            settings = session.query(UserSettings).filter(UserSettings.user_id == 1).first()
                            if not settings:
                                # Create settings if they don't exist
                                settings = UserSettings(user_id=1)
                                session.add(settings)
                            
                            if 'discord_webhook' in data:
                                settings.discord_webhook = data.get('discord_webhook') or None
                            if 'telegram_token' in data:
                                settings.telegram_token = data.get('telegram_token') or None
                            if 'telegram_chat_id' in data:
                                settings.telegram_chat_id = data.get('telegram_chat_id') or None
                            
                            session.commit()
                        
                        # Update notification service
                        from notification_service import notification_service
                        notification_service.configure(
                            telegram_token=settings.telegram_token,
                            telegram_chat_id=settings.telegram_chat_id,
                            discord_webhook=settings.discord_webhook
                        )
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        response = {
                            "success": True,
                            "message": "Notification settings updated"
                        }
                        self.safe_write(json.dumps(response).encode())
                    else:
                        # GET request - return current settings
                        from db import get_session
                        from models import UserSettings
                        
                        with get_session() as session:
                            settings = session.query(UserSettings).filter(UserSettings.user_id == 1).first()
                            if settings:
                                response = {
                                    "discord_webhook": settings.discord_webhook or "",
                                    "telegram_token": settings.telegram_token or "",
                                    "telegram_chat_id": settings.telegram_chat_id or ""
                                }
                            else:
                                response = {
                                    "discord_webhook": "",
                                    "telegram_token": "",
                                    "telegram_chat_id": ""
                                }
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.safe_write(json.dumps(response).encode())
                except Exception as e:
                    logger.error(f"Error in /api/notifications/settings: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/notifications/test/telegram':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from notification_service import notification_service
                    from db import get_session
                    from models import UserSettings
                    
                    # Load current settings
                    with get_session() as session:
                        settings = session.query(UserSettings).filter(UserSettings.user_id == 1).first()
                        if settings:
                            notification_service.configure(
                                telegram_token=settings.telegram_token,
                                telegram_chat_id=settings.telegram_chat_id
                            )
                    
                    result = notification_service.test_telegram()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps(result).encode())
                except Exception as e:
                    logger.error(f"Error testing Telegram: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            elif path == '/api/notifications/test/discord':
                user_id = self.require_auth()
                if user_id is None:
                    return
                try:
                    from notification_service import notification_service
                    from db import get_session
                    from models import UserSettings
                    
                    # Load current settings
                    with get_session() as session:
                        settings = session.query(UserSettings).filter(UserSettings.user_id == 1).first()
                        if settings:
                            notification_service.configure(
                                discord_webhook=settings.discord_webhook
                            )
                    
                    result = notification_service.test_discord()
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.safe_write(json.dumps(result).encode())
                except Exception as e:
                    logger.error(f"Error testing Discord: {e}")
                    try:
                        self.send_error(500, str(e))
                    except (ConnectionAbortedError, BrokenPipeError, OSError):
                        pass
            
            else:
                self.send_response(404)
                self.end_headers()
                self.safe_write(b'Not Found')
        except (ConnectionAbortedError, BrokenPipeError, OSError):
            pass  # Client disconnected - normal
        except Exception as e:
            logger.error(f"❌ Unhandled error in do_POST: {e}", exc_info=True)
            try:
                self.send_error(500, f"Server error: {str(e)}")
            except (ConnectionAbortedError, BrokenPipeError, OSError):
                pass
        










# Custom server class to suppress ConnectionAbortedError noise
class QuietTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threading TCPServer that suppresses ConnectionAbortedError exceptions"""
    allow_reuse_address = True  # Allow reuse of address to prevent "Address already in use" errors
    daemon_threads = True  # Allow threads to exit when main thread exits
    
    def _handle_request_noblock(self):
        """Override to catch connection errors before they're printed"""
        try:
            super()._handle_request_noblock()
        except (ConnectionAbortedError, BrokenPipeError) as e:
            # These are normal when clients disconnect - silently ignore
            # Check if it's a Windows connection error (WinError 10053, 10054)
            if hasattr(e, 'winerror'):
                if e.winerror in (10053, 10054):  # Connection aborted/reset
                    return
            # For other platforms, check errno
            if hasattr(e, 'errno') and e.errno in (104, 32, 10053, 10054):
                return
            # Re-raise if it's not a connection error we want to suppress
            raise
        except OSError as e:
            # Check for connection-related OSErrors
            if hasattr(e, 'winerror') and e.winerror in (10053, 10054):
                return
            if hasattr(e, 'errno') and e.errno in (104, 32, 10053, 10054):
                return
            # Re-raise other OSErrors
            raise
    
    def process_request(self, request, client_address):
        """Override to catch connection errors before they're logged"""
        try:
            super().process_request(request, client_address)
        except (ConnectionAbortedError, BrokenPipeError, OSError) as e:
            # These are normal when clients disconnect - silently ignore
            # Check if it's a connection error (WinError 10053, 10054, etc.)
            if hasattr(e, 'winerror'):
                if e.winerror in (10053, 10054):  # Connection aborted/reset
                    return
            # For other OSError types, check errno
            if hasattr(e, 'errno') and e.errno in (10053, 10054, 104, 32):
                return
            # Re-raise if it's not a connection error
            raise
    
    def handle_error(self, request, client_address):
        """Override to suppress ConnectionAbortedError and similar connection errors"""
        try:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_type in (ConnectionAbortedError, BrokenPipeError, OSError):
                # Check if it's a connection error
                if hasattr(exc_value, 'winerror'):
                    if exc_value.winerror in (10053, 10054):
                        return  # Silently ignore
                if hasattr(exc_value, 'errno') and exc_value.errno in (10053, 10054, 104, 32):
                    return  # Silently ignore
                
                # These are normal when clients disconnect - don't log as errors
                logger.debug(f"Client disconnected: {client_address}")
            else:
                # Log other errors normally
                super().handle_error(request, client_address)
        except Exception:
            # Even error handling can fail - don't crash the server
            pass

# Global server instance for proper shutdown
server_instance = None
shutdown_flag = threading.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("🛑 Received shutdown signal, stopping server...")
    shutdown_flag.set()
    if server_instance:
        server_instance.shutdown()
    sys.exit(0)

def run_server():
    global server_instance
    # Allow override via environment variable PORT (defaults to 8003)
    _env_port = os.environ.get('PORT')
    try:
        PORT = int(_env_port) if _env_port else 8003
    except Exception:
        PORT = 8003
    
    # Wire bot callback to broadcast new jobs to SSE clients
    def broadcast_new_jobs(jobs):
        if not jobs:
            return
        # Cap to max_jobs when sending and compress data
        try:
            # Filter out blocked users
            from db import get_session
            from models import BlockedUser
            
            blocked_employer_ids = set()
            blocked_usernames = set()
            
            try:
                with get_session() as session:
                    blocked_users = session.query(BlockedUser).filter(
                        BlockedUser.user_id == 1
                    ).all()
                    
                    for blocked in blocked_users:
                        if blocked.employer_id:
                            blocked_employer_ids.add(blocked.employer_id)
                        if blocked.client_username:
                            blocked_usernames.add(blocked.client_username)
            except Exception as e:
                logger.warning(f"⚠️ Failed to load blocked users for broadcast: {e}")
            
            # Filter jobs
            filtered_jobs = []
            for job in jobs:
                job_employer_id = job.get('employer_id')
                job_username = job.get('client_username')
                
                # Skip if employer_id or username matches blocked list
                if (job_employer_id and job_employer_id in blocked_employer_ids) or \
                   (job_username and job_username in blocked_usernames):
                    continue
                
                filtered_jobs.append(job)
            
            # Compress job data for new jobs
            max_jobs = getattr(bot_instance, 'max_jobs', 50)
            compressed_jobs = []
            for job in filtered_jobs[:max_jobs]:
                compressed_job = {
                    'id': job.get('id'),
                    'title': job.get('title'),
                    'description': job.get('description'),
                    'original_description': job.get('original_description'),
                    'client': job.get('client'),
                    'client_display_name': job.get('client_display_name'),
                    'client_username': job.get('client_username'),
                    'avatar': job.get('avatar'),
                    'employer_id': job.get('employer_id'),
                    'employer_contracts_count': job.get('employer_contracts_count'),
                    'employer_completed_count': job.get('employer_completed_count'),
                    'employer_last_activity': job.get('employer_last_activity'),
                    'link': job.get('link'),
                    'posted_time_formatted': job.get('posted_time_formatted'),
                    'posted_time_relative': job.get('posted_time_relative'),
                    'job_price': job.get('job_price'),
                    'category': job.get('category'),
                    'is_read': job.get('is_read', False),
                    'bid_generated': job.get('bid_generated', False),
                    'suitability_score': job.get('suitability_score'),
                    'auto_bid_enabled': job.get('auto_bid_enabled', False),
                    'evaluation_rate': job.get('evaluation_rate'),
                    'order_count': job.get('order_count'),
                    'evaluation_count': job.get('evaluation_count'),
                    'contract_rate': job.get('contract_rate'),
                    'identity_verified': job.get('identity_verified'),
                    'identity_status': job.get('identity_status'),
                    'budget_info': job.get('budget_info')
                }
                compressed_jobs.append(compressed_job)
            
            event = {"type": "new_jobs", "jobs": compressed_jobs}
            # Iterate over weakrefs and push to alive queues (thread-safe)
            alive = []
            with sse_clients_lock:
                # Create a snapshot of the list while holding the lock
                clients_snapshot = list(sse_clients)
            
            # Process clients outside the lock to avoid blocking other operations
            for r in clients_snapshot:
                q = r()
                if q is None:
                    continue
                alive.append(r)
                try:
                    q.put_nowait(event)
                except Exception:
                    continue
            
            # Update the list with alive clients (thread-safe)
            with sse_clients_lock:
                sse_clients[:] = alive
        except Exception:
            pass  # Ignore errors in broadcast
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Try binding to configured PORT, and fall back to next ports if needed
        bind_error = None
        chosen_port = None
        max_retries = 2
        bound = False
        
        for candidate in range(PORT, PORT + 20):
            if bound:
                break
                
            for retry in range(max_retries):
                try:
                    instance = QuietTCPServer(("", candidate), CORSHTTPRequestHandler)
                    # allow_reuse_address is already set as class attribute
                    server_instance = instance
                    chosen_port = candidate
                    bound = True
                    break
                except OSError as e:
                    if e.errno == 98:  # Address already in use
                        if retry < max_retries - 1:
                            # Wait a bit and retry (port might be in TIME_WAIT)
                            logger.debug(f"Port {candidate} in use, retrying in 1 second...")
                            time.sleep(1)
                            continue
                        else:
                            bind_error = e
                            logger.error(f"❌ Port {candidate} unavailable after {max_retries} attempts: {e}")
                            break
                    else:
                        bind_error = e
                        logger.error(f"❌ Port {candidate} unavailable: {e}")
                        break
                except Exception as e:
                    bind_error = e
                    logger.error(f"❌ Port {candidate} unavailable: {e}")
                    break

        if server_instance is None:
            raise bind_error or RuntimeError("No available TCP port found")

        PORT = chosen_port or PORT

        logger.info("🌐 Starting Crowdworks Monitor API...")
        logger.info(f"📱 API available at: http://65.108.194.239:{PORT}")
        logger.info(f"🛑 Press Ctrl+C to stop the server")
        
        # Set up unhandled exception handler to prevent crashes
        def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
            """Handle any unhandled exceptions to prevent server crash"""
            if issubclass(exc_type, KeyboardInterrupt):
                # Allow keyboard interrupts to work normally
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logger.error(f"❌ Unhandled exception: {exc_type.__name__}: {exc_value}", exc_info=(exc_type, exc_value, exc_traceback))
            # Don't exit - just log the error
        
        sys.excepthook = handle_unhandled_exception
        
        # Start favorite clients background update service
        try:
                from favorite_clients_service import favorite_clients_service
                favorite_clients_service.start_background_updates()
                favorite_clients_service.start_notification_monitoring()
                logger.info("✅ Favorite clients background update service started")
                logger.info("✅ Favorite clients notification monitoring service started")
        except Exception as e:
                logger.warning(f"⚠️ Could not start favorite clients update service: {e}")
        
        # Attach callback now that server is up
        try:
                bot_instance.on_new_jobs = broadcast_new_jobs
        except Exception:
                logger.warning("Could not attach on_new_jobs callback")

        # Record server start time for restart detection (set before server starts)
        import time
        run_server._start_time = time.time()
        server_start_time = run_server._start_time
        
        # Start server in a separate thread to allow for proper shutdown
        # Wrap serve_forever to catch any unhandled exceptions that might crash the server
        def safe_serve_forever():
            """Wrapper around serve_forever to catch and log any unhandled exceptions"""
            try:
                server_instance.serve_forever()
            except (ConnectionAbortedError, BrokenPipeError, OSError) as e:
                # Connection errors - these should be caught by request handlers, but log if they reach here
                if hasattr(e, 'errno') and e.errno in (104, 32, 10053, 10054):
                    logger.debug(f"Server connection error (normal, should be caught by handlers): {e}")
                elif hasattr(e, 'winerror') and e.winerror in (10053, 10054):
                    logger.debug(f"Server connection error (normal, should be caught by handlers): {e}")
                else:
                    logger.warning(f"⚠️ Server connection error: {e}")
                # Don't restart - just log and let the server continue
            except KeyboardInterrupt:
                # Allow keyboard interrupts to propagate
                raise
            except Exception as e:
                # Other errors - log but don't crash the entire server
                logger.error(f"❌ Unexpected server error in serve_forever: {e}", exc_info=True)
                # Don't restart - the server should continue handling other requests
                # The error has been logged, and the server will continue
        
        server_thread = threading.Thread(target=safe_serve_forever, daemon=False, name="HTTPServer")
        server_thread.start()
        
        # Wait a moment to ensure server started
        time.sleep(0.5)
        if not server_thread.is_alive():
                raise RuntimeError("Server thread failed to start")
        
        logger.info("✅ Server thread started successfully")
        
        # Log periodic status to show server is still running
        last_status_log = time.time()
        status_log_interval = 300  # Log every 5 minutes
        
        # Wait for shutdown signal
        while not shutdown_flag.is_set():
                time.sleep(0.1)
            
                # Check if server thread is still alive
                if not server_thread.is_alive():
                    logger.error("❌ Server thread died unexpectedly!")

                break
            
                # Log periodic status to show server is alive
                current_time = time.time()
                if current_time - last_status_log >= status_log_interval:
                    uptime = int(current_time - server_start_time)

                logger.info(f"✅ Server is running (uptime: {uptime}s, thread alive: {server_thread.is_alive()})")
                last_status_log = current_time
            





    except Exception as e:
        logger.error(f"❌ Error in run_server: {e}", exc_info=True)
        if server_instance:
            try:
                server_instance.server_close()
            except Exception:
                pass
        logger.info("✅ Server stopped")

def validate_bid_content(bid_content: str) -> tuple[bool, str]:
    """Validate bid content before submission"""
    if not bid_content or not bid_content.strip():
        return False, "Bid content is empty"
    
    if len(bid_content.strip()) < 50:
        return False, f"Bid content is too short ({len(bid_content)} characters, minimum 50)"
    
    if len(bid_content) > 5000:
        return False, f"Bid content is too long ({len(bid_content)} characters, maximum 5000)"
    
    # Check for basic Japanese characters (hiragana, katakana, kanji)
    has_japanese = any(ord(char) >= 0x3040 and ord(char) <= 0x9FFF for char in bid_content)
    if not has_japanese:
        return False, "Bid content should contain Japanese characters"
    
    return True, "Valid"

def submit_auto_bid_to_crowdworks(job_url, bid_content, job_data):
    """
    Submit an auto-bid to Crowdworks with intelligent pricing logic and validation
    """
    # Validate bid content first
    is_valid, validation_message = validate_bid_content(bid_content)
    if not is_valid:
        logger.error(f"❌ Bid validation failed: {validation_message}")
        return False
    
    driver = None
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
                logger.info(f"🚀 Starting auto-bid submission for job: {job_data.get('id', 'unknown')} (attempt {retry_count + 1}/{max_retries})")
                logger.info(f"📝 Bid content length: {len(bid_content)} characters")
                logger.info(f"🌐 Job URL: {job_url}")
            
                # Check if we should use simulation mode
                use_simulation = os.environ.get('AUTO_BID_SIMULATION', 'true').lower() == 'true'
            
                if not SELENIUM_AVAILABLE or use_simulation:
                    logger.info("⚠️ Using simulation mode for auto-bid submission")

                return simulate_auto_bid_submission(job_data, bid_content)
            
                # Setup Chrome WebDriver
                driver = setup_webdriver()
                if not driver:
                    logger.error("❌ Failed to setup WebDriver, falling back to simulation mode")

                return simulate_auto_bid_submission(job_data, bid_content)
            
                logger.info(f"🌐 Navigating to: {job_url}")
                driver.get(job_url)
            
                # Wait for page to load with longer timeout
                WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            
                # Additional wait for dynamic content
                time.sleep(2)
            
                # Extract pricing information from the page
                pricing_info = extract_pricing_from_page(driver)
                calculated_price = calculate_intelligent_price(pricing_info, job_data)
            
                logger.info(f"💰 Calculated price: {calculated_price} yen")
                logger.info(f"📊 Pricing info: {pricing_info}")
            
                # Fill the bid form with retry logic
                success = fill_and_submit_bid_form(driver, bid_content, calculated_price, retry_count)
            
                if success:
                    logger.info("✅ Auto-bid submitted successfully!")
                    return True
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"⚠️ Bid submission failed, retrying ({retry_count}/{max_retries})...")
                        time.sleep(2)  # Wait before retry
                        if driver:
                            try:
                                driver.quit()
                            except:
                                pass
                            driver = None
                        continue
                    else:
                        logger.error("❌ Failed to submit auto-bid after all retries, falling back to simulation mode")
                        return simulate_auto_bid_submission(job_data, bid_content)
        finally:
            if driver:
                try:
                    driver.quit()
                    logger.info("🔒 WebDriver closed")
                except:
                    pass
    
    return False

def setup_webdriver():
    """
    Setup Chrome WebDriver with appropriate options
    """
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Use webdriver-manager to automatically manage Chrome driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute script to remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.implicitly_wait(10)
        print("✅ WebDriver setup successful")
        return driver
        
    except Exception as e:
        print(f"❌ Failed to setup WebDriver: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_pricing_from_page(driver):
    """
    Extract pricing information from the Crowdworks bid page
    """
    try:
        # Try to find the pricing conditions text
        pricing_xpath = "//*[@id='new_proposal']/div/div/div[5]/div[2]/div[2]/div[1]/div[2]/text()"
        
        # Alternative selectors to try
        selectors = [
            "//*[@id='new_proposal']/div/div/div[5]/div[2]/div[2]/div[1]/div[2]",
            "//div[contains(text(), '募集条件')]",
            "//div[contains(text(), 'yen')]",
            "//div[contains(text(), 'contract amount')]"
        ]
        
        conditions_text = ""
        for selector in selectors:
            try:
                element = driver.find_element(By.XPATH, selector)
                conditions_text = element.text.strip()
                if conditions_text:
                    print(f"📋 Found pricing conditions: {conditions_text}")
                    break
            except NoSuchElementException:
                continue
        
        if not conditions_text:
            print("⚠️ Could not find pricing conditions, using fallback")
            conditions_text = "募集条件: The contract amount is discussed with the worker"
        
        return {
            'conditions_text': conditions_text,
            'type': 'unknown',
            'amount': None,
            'min_amount': None,
            'max_amount': None
        }
    except Exception as e:
        logger.warning(f"Error parsing job price: {e}")
        return {
            'conditions_text': "募集条件: The contract amount is discussed with the worker",
            'type': 'unknown',
            'amount': None,
            'min_amount': None,
            'max_amount': None
        }

def fill_and_submit_bid_form(driver, bid_content, calculated_price, attempt=0):
    """
    Fill the bid form and submit it with improved error handling
    """
    try:
        logger.info(f"📝 Filling bid form with price: {calculated_price} yen (attempt {attempt + 1})")
        
        # Fill the price field
        price_field_xpath = "//*[@id='proposal_conditions_attributes_0_milestones_attributes_0_amount_without_sales_tax']"
        try:
            price_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, price_field_xpath))
            )
            # Clear and fill price field with validation
            price_field.clear()
            time.sleep(0.5)  # Wait for clear to complete
            price_field.send_keys(str(calculated_price))
            time.sleep(0.5)  # Wait for input to register
            
            # Verify price was entered correctly
            entered_price = price_field.get_attribute('value')
            if entered_price and str(calculated_price) in entered_price.replace(',', ''):
                logger.info(f"✅ Price field filled: {calculated_price} yen")
            else:
                logger.warning(f"⚠️ Price verification failed. Expected: {calculated_price}, Got: {entered_price}")
                # Try again
                price_field.clear()
                time.sleep(0.5)
                price_field.send_keys(str(calculated_price))
                time.sleep(0.5)
        except TimeoutException:
            print("⚠️ Price field not found, trying alternative selectors")
            # Try alternative selectors
            alt_selectors = [
                "//input[contains(@id, 'amount_without_sales_tax')]",
                "//input[contains(@name, 'amount')]",
                "//input[@type='number']"
            ]
            for selector in alt_selectors:
                try:
                    price_field = driver.find_element(By.XPATH, selector)
                    price_field.clear()
                    price_field.send_keys(str(calculated_price))
                    print(f"✅ Price field filled (alternative): {calculated_price}")
                    break
                except NoSuchElementException:
                    continue
        
        # Fill the message field
        message_field_xpath = "//*[@id='proposal_conditions_attributes_0_message_attributes_body']"
        try:
            message_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, message_field_xpath))
            )
            # Clear and fill message field
            message_field.clear()
            time.sleep(0.5)  # Wait for clear to complete
            
            # Type bid content (can be slow for long content)
            message_field.send_keys(bid_content)
            time.sleep(1)  # Wait for content to be entered
            
            # Verify content was entered
            entered_content = message_field.get_attribute('value')
            if entered_content and len(entered_content) > 0:
                logger.info(f"✅ Message field filled: {len(entered_content)} characters")
            else:
                logger.warning("⚠️ Message field verification failed, trying again...")
                message_field.clear()
                time.sleep(0.5)
                message_field.send_keys(bid_content)
                time.sleep(1)
        except TimeoutException:
            print("⚠️ Message field not found, trying alternative selectors")
            # Try alternative selectors
            alt_selectors = [
                "//textarea[contains(@id, 'message')]",
                "//textarea[contains(@name, 'body')]",
                "//textarea"
            ]
            for selector in alt_selectors:
                try:
                    message_field = driver.find_element(By.XPATH, selector)
                    message_field.clear()
                    message_field.send_keys(bid_content)
                    print(f"✅ Message field filled (alternative): {len(bid_content)} characters")
                    break
                except NoSuchElementException:
                    continue
        
        # Submit the form
        submit_button_xpath = "//*[@id='new_proposal']/div/div/div[10]/div/input[2]"
        try:
            submit_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
            )
            submit_button.click()
            print("✅ Submit button clicked")
            
            # Wait a moment for submission
            time.sleep(3)
            
            # Check if submission was successful (look for success indicators)
            success_indicators = [
                "//div[contains(text(), '送信完了')]",
                "//div[contains(text(), 'proposal sent')]",
                "//div[contains(text(), 'success')]"
            ]
            
            for indicator in success_indicators:
                try:
                    success_element = driver.find_element(By.XPATH, indicator)
                    if success_element:
                        print("✅ Success indicator found")
                        return True
                except NoSuchElementException:
                    continue
            
            # If no success indicator found, assume success if we got this far
            print("✅ Form submitted (no explicit success indicator found)")
            return True
            


        except TimeoutException:
            alt_selectors = [
                "//input[@type='submit']",
                "//button[contains(text(), '送信')]",
                "//button[contains(text(), 'Submit')]",
                "//input[contains(@value, '送信')]"
            ]
            for selector in alt_selectors:
                try:
                    submit_button = driver.find_element(By.XPATH, selector)
                    submit_button.click()
                    print("✅ Submit button clicked (alternative)")
                    time.sleep(3)
                    return True
                except NoSuchElementException:
                    continue
            
            print("❌ Could not find submit button")
            return False
    except Exception as e:
        logger.error(f"Error in fill_and_submit_bid_form: {e}", exc_info=True)
        return False
            







def simulate_auto_bid_submission(job_data, bid_content):
    try:
        print("🎭 Simulating auto-bid submission...")
        print(f"📋 Job ID: {job_data.get('id', 'unknown')}")
        print(f"📝 Job Title: {job_data.get('title', 'Unknown')}")
        print(f"👤 Client: {job_data.get('client', 'Unknown')}")
        
        # Extract pricing info from job data
        pricing_info = extract_pricing_info(job_data)
        calculated_price = calculate_intelligent_price(pricing_info)
        
        print(f"💰 Simulated price calculation: {calculated_price} yen")
        print(f"📝 Simulated bid content: {bid_content[:100]}...")
        print(f"📊 Simulated pricing info: {pricing_info}")
        
        # Simulate processing steps
        print("🔄 Simulating form filling...")
        time.sleep(1)
        
        print("🔄 Simulating price field entry...")
        time.sleep(0.5)
        
        print("🔄 Simulating message field entry...")
        time.sleep(0.5)
        
        print("🔄 Simulating form submission...")
        time.sleep(1)
        
        print("✅ Simulated auto-bid submission successful")
        print("📧 In a real scenario, this would submit the bid to Crowdworks")
        print("🔧 To enable real submission, set AUTO_BID_SIMULATION=false and ensure proper Crowdworks login")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in simulation: {e}")
        return False

def extract_pricing_info(job_data):
    """
    Extract pricing information from job data
    """
    pricing_info = {
        'type': 'unknown',
        'amount': None,
        'min_amount': None,
        'max_amount': None,
        'conditions_text': ''
    }
    
    # Extract from job price info
    if 'job_price' in job_data:
        price_info = job_data['job_price']
        pricing_info['type'] = price_info.get('type', 'unknown')
        pricing_info['amount'] = price_info.get('amount')
    
    # Extract from budget info
    if 'budget_info' in job_data:
        budget_info = job_data['budget_info']
        pricing_info['min_amount'] = budget_info.get('min')
        pricing_info['max_amount'] = budget_info.get('max')
        pricing_info['conditions_text'] = budget_info.get('range', '')
    
    return pricing_info

def calculate_intelligent_price(pricing_info, job_data=None):
    """
    Calculate intelligent pricing based on the conditions and job data
    """
    conditions_text = pricing_info.get('conditions_text', '')
    
    # Case 1: "募集条件: The contract amount is discussed with the worker"
    if "The contract amount is discussed with the worker" in conditions_text or "discussed with the worker" in conditions_text.lower():
        # Use job category to estimate reasonable price
        if job_data:
            category = job_data.get('category', 'web')
            category_base_prices = {
                'web': 50000,
                'system': 80000,
                'ec': 60000,
                'app': 70000,
                'ai': 100000,
                'other': 50000
            }
            base_price = category_base_prices.get(category, 50000)
            # Add 20% margin for competitive pricing
            return int(base_price * 1.2)
        return 60000
    
    # Case 2: Range like "募集条件: 5,000 yen to 10,000 yen" or "5,000円～10,000円"
    range_patterns = [
        r'募集条件:\s*([0-9,]+)\s*yen\s*to\s*([0-9,]+)\s*yen',
        r'([0-9,]+)\s*円\s*[～〜]\s*([0-9,]+)\s*円',
        r'([0-9,]+)\s*yen\s*[～〜]\s*([0-9,]+)\s*yen',
    ]
    
    for pattern in range_patterns:
        range_match = re.search(pattern, conditions_text)
        if range_match:
            min_amount = int(range_match.group(1).replace(',', ''))
            max_amount = int(range_match.group(2).replace(',', ''))
            # Use 60% of range (competitive but not too low)
            calculated = int(min_amount + (max_amount - min_amount) * 0.6)
            return calculated
    
    # Case 3: Fixed amount like "募集条件: 11,000 yen" or "11,000円"
    fixed_patterns = [
        r'募集条件:\s*([0-9,]+)\s*yen',
        r'([0-9,]+)\s*円',
        r'固定:\s*([0-9,]+)',
    ]
    
    for pattern in fixed_patterns:
        fixed_match = re.search(pattern, conditions_text)
        if fixed_match:
            amount = int(fixed_match.group(1).replace(',', ''))
            # Offer 5% discount for competitive pricing
            return int(amount * 0.95)
    
    # Case 4: Use job price if available
    if pricing_info.get('amount'):
        amount = pricing_info['amount']
        if isinstance(amount, (int, float)):
            return int(amount * 0.95)  # 5% discount
        return int(amount)
    
    # Case 5: Use min/max from pricing info
    if pricing_info.get('min_amount') and pricing_info.get('max_amount'):
        min_amt = pricing_info['min_amount']
        max_amt = pricing_info['max_amount']
        return int((min_amt + max_amt) * 0.6)
    
    # Default fallback based on category
    if job_data:
        category = job_data.get('category', 'web')
        category_base_prices = {
            'web': 50000,
            'system': 80000,
            'ec': 60000,
            'app': 70000,
            'ai': 100000,
            'other': 50000
        }
        return category_base_prices.get(category, 50000)
    
    return 50000

if __name__ == "__main__":
    # Try to kill any existing process on port 8003 before starting
    import socket
    import subprocess
    import os
    
    PORT = 8003
    logger.info(f"🔍 Checking port {PORT}...")
    
    # Try multiple methods to kill process on port 8003
    killed = False
    try:
        # Method 1: Try lsof
        try:
            result = subprocess.run(['lsof', '-ti', f':{PORT}'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.DEVNULL, 
                                  timeout=2)
            if result.returncode == 0 and result.stdout:
                pids = result.stdout.decode().strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            os.kill(int(pid.strip()), 9)
                            logger.info(f"✅ Killed process {pid.strip()} on port {PORT} (using lsof)")
                            killed = True
                        except (ValueError, ProcessLookupError, PermissionError) as e:
                            logger.debug(f"Could not kill PID {pid}: {e}")


        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # lsof not available or timed out
        
        # Method 2: Try fuser if lsof didn't work
        if not killed:
            try:
                result = subprocess.run(['fuser', '-k', f'{PORT}/tcp'], 
                                      stderr=subprocess.DEVNULL, 
                                      timeout=2)
                if result.returncode == 0:
                    logger.info(f"✅ Freed port {PORT} using fuser")
                    killed = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        # Method 3: Try netstat/ss as last resort
        if not killed:
            try:
                # Try ss first
                result = subprocess.run(['ss', '-tlnp'], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.DEVNULL, 
                                      timeout=2)
                if result.returncode == 0:
                    for line in result.stdout.decode().split('\n'):
                        if f':{PORT} ' in line:
                            # Extract PID from line
                            parts = line.split()
                            for part in parts:
                                if 'pid=' in part:
                                    pid = part.split('pid=')[1].split(',')[0]
                                    try:
                                        os.kill(int(pid), 9)
                                        logger.info(f"✅ Killed process {pid} on port {PORT} (using ss)")
                                        killed = True
                                        break
                                    except (ValueError, ProcessLookupError, PermissionError):
                                        pass


            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass  # fuser not available or timed out
        
        # Wait a moment for port to be freed
        if killed:
            import time
            time.sleep(2)  # Wait longer for port to be fully released
        
        # Verify port is free
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', PORT))
            sock.close()
            if result == 0:
                logger.warning(f"⚠️  Port {PORT} may still be in use after kill attempt")
            else:
                logger.info(f"✅ Port {PORT} is free and ready")
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"⚠️ Error killing process on port {PORT}: {e}")
            




if __name__ == '__main__':
    # Add top-level exception handler to prevent server crashes
    try:
        run_server()
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error in server: {e}", exc_info=True)
        sys.exit(1)

