import asyncio
import json
import time
import os
from datetime import datetime
from typing import List, Dict, Set
from collections import deque
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# Robust import for local module regardless of CWD
try:
    from real_crowdworks_scraper import RealCrowdworksScraper
except ModuleNotFoundError:
    import os as _os
    import importlib.util as _importlib_util
    _here = _os.path.dirname(__file__)
    _module_path = _os.path.join(_here, 'real_crowdworks_scraper.py')
    _spec = _importlib_util.spec_from_file_location('real_crowdworks_scraper', _module_path)
    if _spec and _spec.loader:
        _module = _importlib_util.module_from_spec(_spec)
        _spec.loader.exec_module(_module)
        RealCrowdworksScraper = _module.RealCrowdworksScraper
    else:
        raise
from chatgpt_service import chatgpt_service
from logging_utils import bot_logger as logger
from db import init_db, get_session
from models import User, UserSettings

class CrowdworksBot:
    def __init__(self):
        # Initialize DB and ensure default user
        try:
            init_db()
        except Exception as e:
            logger.warning(f"⚠️ DB init failed: {e}")
        self.default_user_id = 1
        self._ensure_default_user()
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        self.jobs_found = 0
        self.unread_count = 0
        self.seen_job_ids: Set[str] = set()
        self.seen_job_order = deque()
        self.max_seen_ids = 5000  # Cap to prevent unbounded growth
        self.current_jobs: List[Dict] = []
        self.max_jobs = 50  # Limit total jobs (will be loaded from settings)
        
        # Initialize scraper with error handling
        try:
            self.scraper = RealCrowdworksScraper()
            logger.info("✅ Scraper initialized successfully")
        except Exception as scraper_init_error:
            logger.error(f"❌ Failed to initialize scraper: {scraper_init_error}", exc_info=True)
            # Set to None so we can detect and handle this later
            self.scraper = None
            logger.warning("⚠️ Bot will not be able to scrape until scraper is fixed")
        
        # Synchronization for concurrent scraping updates
        import threading
        self.state_lock = threading.Lock()
        
        # Bot settings
        self.categories = ['web']
        self.keywords = []
        self.interval = 60  # seconds
        self.past_hours = 24
        self.notifications = True
        self.sound_alert = False
        
        # Auto-bidding settings
        self.auto_bid_enabled = False
        # Load OpenAI API key from environment variable or .env file
        # Will be overridden by user settings if provided
        self.chatgpt_api_key = os.getenv('OPENAI_API_KEY', '')
        self.user_skills = ["Python", "JavaScript", "React", "Node.js", "Web Development", "API Development", "Database Design", "Git", "Linux", "AWS"]
        self.min_suitability_score = 70
        self.bid_template = ""
        # New: price rules per category and bid prompts collection
        self.category_price_rules: Dict[str, Dict[str, int]] = {}
        self.bid_prompts: List[str] = []
        self.selected_prompt_index: int = -1
        
        # Custom prompts for bid generation
        self.custom_prompts = {
            'prompt1': '',
            'prompt2': '',
            'prompt3': ''
        }
        
        # Callbacks for real-time updates
        self.on_new_jobs = None
        self.on_status_update = None
        
        # Track last sent job IDs to avoid duplicates
        self.last_sent_job_ids: Set[str] = set()
        self.max_sent_job_ids = 1000  # Keep track of last 1000 sent jobs
        
        # Job cleanup settings
        self.job_max_age_hours = 24  # Remove jobs older than 24 hours
        self.cleanup_interval = 3600  # Run cleanup every hour (in seconds)
        self.last_cleanup_time = None
        
        # Enhanced status tracking
        self.last_scrape_time = None
        self.error_count = 0
        self.last_error = None
        self.status_history = []
        
        # Attempt to load persisted settings from DB (single-user mode: always user_id=1)
        try:
            db_settings = self._load_settings_from_db()
            if db_settings:
                self.set_settings(db_settings)
            else:
                # If no settings in DB, ensure max_jobs is set to default
                self.max_jobs = 50
        except Exception as e:
            logger.warning(f"⚠️ Could not load settings from DB: {e}")
            # Ensure max_jobs has a default value even if loading fails
            self.max_jobs = 50

        logger.info(f"🤖 CrowdworksBot initialized (max_jobs: {self.max_jobs})")

    def set_settings(self, settings: Dict):
        """Update bot settings (single-user mode: always uses user_id=1)"""
        self.categories = settings.get('categories', ['web'])
        self.keywords = settings.get('keywords', '').split(',') if settings.get('keywords') else []
        self.keywords = [kw.strip() for kw in self.keywords if kw.strip()]
        self.interval = settings.get('interval', 60)
        self.past_hours = settings.get('pastTime', 24)
        self.notifications = settings.get('notifications', True)
        self.sound_alert = settings.get('soundAlert', False)
        
        # Auto-bidding settings
        self.auto_bid_enabled = settings.get('autoBid', False)
        self.chatgpt_api_key = settings.get('chatgptApiKey', '')
        self.user_skills = settings.get('userSkills', '').split(',') if settings.get('userSkills') else []
        self.user_skills = [skill.strip() for skill in self.user_skills if skill.strip()]
        self.min_suitability_score = settings.get('minSuitabilityScore', 70)
        self.bid_template = settings.get('bidTemplate', '')
        # Extended settings
        self.category_price_rules = settings.get('categoryPriceRules', {}) or {}
        self.bid_prompts = settings.get('bidPrompts', []) or []
        self.selected_prompt_index = settings.get('selectedPromptIndex', -1)
        
        # Custom prompts
        custom_prompts = settings.get('customPrompts', {})
        self.custom_prompts = {
            'prompt1': custom_prompts.get('prompt1', ''),
            'prompt2': custom_prompts.get('prompt2', ''),
            'prompt3': custom_prompts.get('prompt3', '')
        }
        
        # Selected model
        self.selected_model = settings.get('selectedModel', 'gpt-4o-mini')
        
        # Max jobs setting
        max_jobs_setting = settings.get('maxJobs', 50)
        # Ensure max_jobs is between 10 and 200
        self.max_jobs = max(10, min(200, int(max_jobs_setting)))
        
        # Update ChatGPT service with API key
        if self.chatgpt_api_key:
            chatgpt_service.set_api_key(self.chatgpt_api_key)
        
        logger.info(f"Bot settings updated: categories={self.categories}, keywords={self.keywords}, auto_bid={self.auto_bid_enabled}, max_jobs={self.max_jobs}")
        # Persist settings to DB (single-user mode: always user_id=1)
        try:
            self._save_settings_to_db()
        except Exception as e:
            logger.warning(f"⚠️ Failed to save settings to DB: {e}")

    def get_settings(self) -> Dict:
        """Return current settings in API schema"""
        return {
            'categories': self.categories,
            'keywords': ', '.join(self.keywords),
            'interval': self.interval,
            'pastTime': self.past_hours,
            'notifications': self.notifications,
            'soundAlert': self.sound_alert,
            'autoBid': self.auto_bid_enabled,
            'chatgptApiKey': self.chatgpt_api_key,
            'userSkills': ', '.join(self.user_skills),
            'minSuitabilityScore': self.min_suitability_score,
            'bidTemplate': self.bid_template,
            'categoryPriceRules': self.category_price_rules,
            'bidPrompts': self.bid_prompts,
            'selectedPromptIndex': self.selected_prompt_index,
            'customPrompts': self.custom_prompts,
            'selectedModel': self.selected_model,
            'maxJobs': self.max_jobs,
        }

    def _ensure_default_user(self):
        """Ensure user ID 1 exists (single-user mode)"""
        with get_session() as s:
            user = s.get(User, self.default_user_id)
            if not user:
                # In single-user mode, user should already exist
                # If not, something is wrong - log error but don't create
                logger.error(f"❌ User ID {self.default_user_id} not found! Single-user mode requires user to exist.")
                return
            # Ensure settings exist for user
            if not user.settings:
                us = UserSettings(user_id=user.id)
                s.add(us)
                s.commit()

    def _save_settings_to_db(self):
        """Save settings to database (single-user mode: always user_id=1)"""
        data = self.get_settings()
        with get_session() as s:
            settings = s.query(UserSettings).filter(UserSettings.user_id == self.default_user_id).one_or_none()
            if not settings:
                settings = UserSettings(user_id=self.default_user_id)
                s.add(settings)
                s.flush()
            settings.categories = json.dumps(data.get('categories', ['web']))
            settings.keywords = data.get('keywords', '')
            settings.interval = int(data.get('interval', 60))
            settings.past_time = int(data.get('pastTime', 24))
            settings.notifications = bool(data.get('notifications', True))
            settings.sound_alert = bool(data.get('soundAlert', False))
            settings.auto_bid = bool(data.get('autoBid', False))
            settings.chatgpt_api_key = data.get('chatgptApiKey') or None
            settings.user_skills = data.get('userSkills', '')
            settings.min_suitability_score = int(data.get('minSuitabilityScore', 70))
            settings.bid_template = data.get('bidTemplate') or None
            # Save custom prompts as JSON
            custom_prompts = data.get('customPrompts', {})
            settings.custom_prompts = json.dumps(custom_prompts) if custom_prompts else None
            # Save selected model
            settings.selected_model = data.get('selectedModel') or None
            # Save max jobs (ensure it's between 10 and 200)
            max_jobs_value = data.get('maxJobs', 50)
            settings.max_jobs = max(10, min(200, int(max_jobs_value)))
            # Store extended settings as JSON in text columns to avoid migration
            ext = {
                'categoryPriceRules': data.get('categoryPriceRules', {}),
                'bidPrompts': data.get('bidPrompts', []),
                'selectedPromptIndex': data.get('selectedPromptIndex', -1),
            }
            # Commit the changes
            s.commit()
            logger.info(f"✅ Settings saved to database for user_id: {self.default_user_id}")

    def _load_settings_from_db(self):
        """Load settings from database (single-user mode: always user_id=1)"""
        with get_session() as s:
            settings = s.query(UserSettings).filter(UserSettings.user_id == self.default_user_id).one_or_none()
            if not settings:
                return None
            try:
                categories = json.loads(settings.categories) if settings.categories else ['web']
            except Exception:
                categories = ['web']
            # Load custom prompts from JSON
            custom_prompts = {}
            if settings.custom_prompts:
                try:
                    custom_prompts = json.loads(settings.custom_prompts)
                except Exception:
                    custom_prompts = {}
            
            return {
                'categories': categories,
                'keywords': settings.keywords or '',
                'interval': settings.interval,
                'pastTime': settings.past_time,
                'notifications': settings.notifications,
                'soundAlert': settings.sound_alert,
                'autoBid': settings.auto_bid,
                'chatgptApiKey': settings.chatgpt_api_key or '',
                'userSkills': settings.user_skills or '',
                'minSuitabilityScore': settings.min_suitability_score,
                'bidTemplate': settings.bid_template or '',
                'customPrompts': custom_prompts,
                'selectedModel': settings.selected_model or 'gpt-4o-mini',
                'maxJobs': settings.max_jobs if hasattr(settings, 'max_jobs') else 50,
                'categoryPriceRules': self.category_price_rules,
                'bidPrompts': self.bid_prompts,
                'selectedPromptIndex': self.selected_prompt_index,
            }

    def start(self):
        """Start the bot"""
        if self.is_running:
            logger.warning("⚠️ Bot is already running")
            return
        
        try:
            # Validate scraper is available before starting
            if not self.scraper:
                raise RuntimeError("Scraper not initialized")
            
            # Test scraper with a simple operation to catch initialization issues early
            try:
                # Just verify scraper has required attributes
                if not hasattr(self.scraper, 'category_urls'):
                    raise RuntimeError("Scraper missing required attributes")
            except Exception as scraper_error:
                logger.error(f"❌ Scraper validation failed: {scraper_error}", exc_info=True)
                raise RuntimeError(f"Scraper validation failed: {scraper_error}") from scraper_error
            
            self.is_running = True
            self.is_paused = False
            self.start_time = datetime.now()
            self.jobs_found = 0
            self.unread_count = 0
            self.seen_job_ids.clear()
            self.seen_job_order.clear()
            self.error_count = 0
            self.last_error = None
            
            logger.info("🚀 Starting Crowdworks bot...")
            logger.info(f"📊 Categories: {self.categories}")
            logger.info(f"🔍 Keywords: {self.keywords}")
            logger.info(f"⏱️ Interval: {self.interval} seconds")
            logger.info(f"📅 Past hours: {self.past_hours}")
            
            # Log status change
            try:
                self._log_status_change("STARTED")
            except Exception as log_error:
                logger.warning(f"⚠️ Failed to log status change: {log_error}")
            
            # Start the scraping loop in a separate thread with robust error handling
            import threading
            def safe_scraping_wrapper():
                """Wrapper to ensure exceptions in scraping loop don't crash the server"""
                try:
                    self._scraping_loop_sync()
                except Exception as loop_error:
                    logger.error(f"❌ Critical error in scraping loop thread: {loop_error}", exc_info=True)
                    # Reset bot state on critical error
                    self.is_running = False
                    self.is_paused = False
                    self.error_count += 1
                    self.last_error = f"Critical error: {str(loop_error)}"
            
            self.scraping_thread = threading.Thread(target=safe_scraping_wrapper, daemon=True, name="BotScrapingThread")
            self.scraping_thread.start()
            
            # Don't wait or check thread - let it start asynchronously
            # The thread is daemon, so it won't prevent server shutdown
            # If it fails, the error will be logged in the wrapper
            logger.info("✅ Bot scraping thread started (running asynchronously)")
            
            logger.info("✅ Bot started successfully")
        except Exception as e:
            # Reset state on error
            self.is_running = False
            self.is_paused = False
            logger.error(f"❌ Failed to start bot: {e}", exc_info=True)
            raise

    def stop(self):
        """Stop the bot completely"""
        try:
            logger.info("🛑 Stopping bot completely...")
            
            # Set flags first to stop the loop
            self.is_running = False
            self.is_paused = False
            
            # Wait for scraping thread to finish if it exists
            try:
                if hasattr(self, 'scraping_thread') and self.scraping_thread and self.scraping_thread.is_alive():
                    logger.info("⏳ Waiting for scraping thread to finish...")
                    self.scraping_thread.join(timeout=2)  # Wait up to 2 seconds
                    if self.scraping_thread.is_alive():
                        logger.warning("⚠️ Scraping thread did not finish gracefully")
                    else:
                        logger.info("✅ Scraping thread stopped")
            except Exception as thread_error:
                logger.warning(f"⚠️ Error waiting for scraping thread: {thread_error}")
            
            # Clear all data
            try:
                self.seen_job_ids.clear()
                self.current_jobs.clear()
                self.jobs_found = 0
                self.unread_count = 0
                self.start_time = None
                self.last_scrape_time = None
            except Exception as clear_error:
                logger.warning(f"⚠️ Error clearing bot data: {clear_error}")
            
            # Log status change (after state is updated)
            try:
                self._log_status_change("STOPPED")
            except Exception as log_error:
                logger.warning(f"⚠️ Error logging status change: {log_error}")
            
            logger.info("✅ Bot stopped completely")
        except Exception as e:
            logger.error(f"❌ Error in stop(): {e}", exc_info=True)
            # Ensure flags are set even if there's an error
            try:
                self.is_running = False
                self.is_paused = False
            except Exception:
                pass

    def pause(self):
        """Pause the bot (keeps data and can be resumed)"""
        try:
            if not self.is_running:
                logger.warning("⚠️ Cannot pause bot - bot is not running")
                return
                
            self.is_paused = True
            logger.info("⏸️ Bot paused")
            try:
                self._log_status_change("PAUSED")
            except Exception as log_error:
                logger.warning(f"⚠️ Error logging status change: {log_error}")
        except Exception as e:
            logger.error(f"❌ Error in pause(): {e}", exc_info=True)
            raise

    def resume(self):
        """Resume the bot from pause"""
        try:
            if not self.is_running:
                logger.warning("⚠️ Cannot resume bot - bot is not running")
                return
                
            self.is_paused = False
            logger.info("▶️ Bot resumed")
            try:
                self._log_status_change("RESUMED")
            except Exception as log_error:
                logger.warning(f"⚠️ Error logging status change: {log_error}")
        except Exception as e:
            logger.error(f"❌ Error in resume(): {e}", exc_info=True)
            raise

    def _log_status_change(self, status: str):
        """Log status changes with timestamp"""
        try:
            timestamp = datetime.now().isoformat()
            status_entry = {
                'timestamp': timestamp,
                'status': status,
                'running': self.is_running,
                'paused': self.is_paused,
                'jobs_found': self.jobs_found,
                'unread_count': self.unread_count,
                'error_count': self.error_count
            }
            self.status_history.append(status_entry)
            
            # Keep only last 100 status entries
            if len(self.status_history) > 100:
                self.status_history = self.status_history[-100:]
            
            logger.info(f"📊 Status changed to: {status}")
        except Exception as e:
            # Don't let status logging crash the bot
            logger.warning(f"⚠️ Error in _log_status_change: {e}")

    def _scraping_loop_sync(self):
        """Main scraping loop (synchronous version)"""
        try:
            # Add initial delay to ensure bot startup completes before first scrape
            # This prevents blocking the HTTP response and allows server to stay responsive
            logger.info("⏳ Waiting 2 seconds before first scrape to ensure server is responsive...")
            time.sleep(2)
            
            while self.is_running:
                if not self.is_paused:
                    try:
                        # Wrap scrape operation in additional error handling
                        try:
                            self._scrape_and_process_sync()
                            self.last_scrape_time = datetime.now()
                            
                            # Run cleanup if needed
                            try:
                                self._cleanup_old_jobs()
                            except Exception as cleanup_error:
                                logger.error(f"❌ Error in cleanup: {cleanup_error}", exc_info=True)
                                # Don't crash - just log and continue
                        except KeyboardInterrupt:
                            # Don't catch keyboard interrupts
                            raise
                        except SystemExit:
                            # Don't catch system exits
                            raise
                        except BaseException as scrape_error:
                            # Catch ALL exceptions including system-level ones
                            self.error_count += 1
                            self.last_error = str(scrape_error)
                            logger.error(f"❌ Error in scraping loop: {str(scrape_error)}", exc_info=True)
                            logger.error(f"📊 Total errors: {self.error_count}")
                            # Don't crash - continue the loop
                            # Add a small delay before retrying
                            time.sleep(5)
                    except KeyboardInterrupt:
                        # Don't catch keyboard interrupts
                        raise
                    except SystemExit:
                        # Don't catch system exits
                        raise
                    except BaseException as e:
                        # Catch ALL other exceptions
                        self.error_count += 1
                        self.last_error = str(e)
                        logger.error(f"❌ Critical error in scraping loop: {str(e)}", exc_info=True)
                        logger.error(f"📊 Total errors: {self.error_count}")
                        # Add a delay before retrying
                        time.sleep(5)
                
                # Wait for next interval, but check is_running more frequently
                try:
                    for _ in range(self.interval):
                        if not self.is_running:
                            break
                        time.sleep(1)
                except Exception as sleep_error:
                    logger.error(f"❌ Error in sleep loop: {sleep_error}", exc_info=True)
                    # If sleep fails, just break and let the loop restart
                    break
        except KeyboardInterrupt:
            # Don't catch keyboard interrupts
            raise
        except SystemExit:
            # Don't catch system exits
            raise
        except BaseException as e:
            # Catch ALL exceptions including system-level ones
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"❌ Fatal error in scraping loop: {str(e)}", exc_info=True)
            logger.error(f"📊 Total errors: {self.error_count}")
            # Reset bot state
            self.is_running = False
            self.is_paused = False

    def _scrape_and_process_sync(self):
        """Scrape jobs and process new ones (synchronous version)"""
        # Check if scraper is available
        if not self.scraper:
            logger.error("❌ Cannot scrape: Scraper not initialized")
            self.error_count += 1
            self.last_error = "Scraper not initialized"
            return
        
        logger.info(f"Scraping jobs from categories: {self.categories}")
        
        # Concurrently scrape all categories and emit per-category results immediately
        logger.info(f"Scraping with past_hours={self.past_hours}")

        import threading
        threads: List[threading.Thread] = []
        aggregated_jobs: List[Dict] = []

        def scrape_and_emit(category: str):
            """Safely scrape a category with maximum error protection"""
            try:
                # Validate scraper is still available
                if not self.scraper:
                    logger.error(f"❌ Scraper not available for category {category}")
                    return
                
                try:
                    # Wrap scraper call in additional protection
                    try:
                        category_jobs = self.scraper.scrape_category(
                            category=category,
                            keywords=self.keywords,
                            past_hours=self.past_hours
                        )
                    except KeyboardInterrupt:
                        # Don't catch keyboard interrupts
                        raise
                    except SystemExit:
                        # Don't catch system exits
                        raise
                    except BaseException as scrape_error:
                        # Catch ALL exceptions including system-level ones
                        logger.error(f"❌ Error scraping category {category}: {scrape_error}", exc_info=True)
                        # Don't crash - just log and continue
                        return
                except KeyboardInterrupt:
                    # Don't catch keyboard interrupts
                    raise
                except SystemExit:
                    # Don't catch system exits
                    raise
                except BaseException as outer_error:
                    # Catch any other errors in the outer try block
                    logger.error(f"❌ Outer error scraping category {category}: {outer_error}", exc_info=True)
                    return
                
                if not category_jobs:
                    return

                # Determine truly new jobs for this batch
                batch_new_jobs: List[Dict] = []
                with self.state_lock:
                    for job in category_jobs:
                        job_id = job['id']
                        if job_id not in self.seen_job_ids:
                            batch_new_jobs.append(job)
                            self.seen_job_ids.add(job_id)
                            self.seen_job_order.append(job_id)
                            # Prune oldest seen ids if over cap
                            while len(self.seen_job_ids) > self.max_seen_ids and self.seen_job_order:
                                old_id = self.seen_job_order.popleft()
                                if old_id in self.seen_job_ids:
                                    self.seen_job_ids.remove(old_id)

                    if batch_new_jobs:
                        # Sort batch by posted_at descending so frontend displays in time order
                        try:
                            batch_new_jobs.sort(key=lambda x: x.get('posted_at', ''), reverse=True)
                        except Exception:
                            pass

                        logger.info(f"Found {len(batch_new_jobs)} new jobs in category '{category}'")
                        self.jobs_found += len(batch_new_jobs)
                        self.unread_count += len(batch_new_jobs)

                        # Merge into current_jobs keeping most recent first and cap
                        combined = batch_new_jobs + self.current_jobs
                        # De-duplicate by id while preserving order and read status
                        seen_ids: Set[str] = set()
                        deduped: List[Dict] = []
                        existing_jobs_map = {job['id']: job for job in self.current_jobs}
                        
                        for j in combined:
                            if j['id'] in seen_ids:
                                continue
                            seen_ids.add(j['id'])
                            
                            # Preserve read status from existing jobs
                            if j['id'] in existing_jobs_map and existing_jobs_map[j['id']].get('is_read', False):
                                j['is_read'] = True
                            
                            deduped.append(j)
                        # Also globally sort by posted_at to ensure time order across categories
                        try:
                            deduped.sort(key=lambda x: x.get('posted_at', ''), reverse=True)
                        except Exception:
                            pass
                        self.current_jobs = deduped[: self.max_jobs]

                # Emit outside the lock
                if batch_new_jobs:
                    # Filter out jobs that were already sent
                    truly_new_jobs = [job for job in batch_new_jobs if job['id'] not in self.last_sent_job_ids]
                    
                    if truly_new_jobs:
                        # Update sent job IDs tracking
                        for job in truly_new_jobs:
                            self.last_sent_job_ids.add(job['id'])
                        
                        # Clean up old sent job IDs to prevent memory bloat
                        if len(self.last_sent_job_ids) > self.max_sent_job_ids:
                            # Remove oldest 100 IDs
                            ids_to_remove = list(self.last_sent_job_ids)[:100]
                            for job_id in ids_to_remove:
                                self.last_sent_job_ids.discard(job_id)
                        
                        for job in truly_new_jobs:
                            logger.info(f"New job: {job['title']} - {job['client']} - {job.get('job_price', {}).get('formatted', 'N/A')}")
                            
                            # Save job to database and log event
                            try:
                                self._save_job_to_db(job)
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to save job to database: {e}")
                            
                        try:
                            if callable(self.on_new_jobs):
                                self.on_new_jobs(truly_new_jobs)
                        except Exception as e:
                            logger.warning(f"⚠️ on_new_jobs callback failed: {e}")

                        if self.auto_bid_enabled and self.chatgpt_api_key:
                            self._process_auto_bidding(truly_new_jobs)
                        if self.notifications:
                            self._send_notifications_sync(truly_new_jobs)

                # Collect for snapshot rebuilding
                with self.state_lock:
                    aggregated_jobs.extend(category_jobs)
            except Exception as e:
                logger.error(f"Error scraping category {category}: {e}")

        # Launch threads
        for category in self.categories:
            t = threading.Thread(target=scrape_and_emit, args=(category,), daemon=True)
            threads.append(t)
            t.start()

        # Wait for all categories to finish (bounded by interval)
        for t in threads:
            t.join()

        # Rebuild snapshot in time order, capped
        if aggregated_jobs:
            try:
                aggregated_jobs.sort(key=lambda x: x.get('posted_at', ''), reverse=True)
            except Exception:
                pass
            with self.state_lock:
                # Preserve read status when rebuilding snapshot
                existing_jobs_map = {job['id']: job for job in self.current_jobs}
                for job in aggregated_jobs:
                    if job['id'] in existing_jobs_map and existing_jobs_map[job['id']].get('is_read', False):
                        job['is_read'] = True
                
                self.current_jobs = aggregated_jobs[: self.max_jobs]

    def _process_auto_bidding(self, jobs: List[Dict]):
        """Process auto-bidding for new jobs"""
        logger.info(f"🤖 Processing auto-bidding for {len(jobs)} jobs")
        
        for job in jobs:
            try:
                # Generate bid using ChatGPT
                logger.info(f"✅ Generating bid for job {job['id']}...")
                bid_result = chatgpt_service.generate_bid(job)
                
                if bid_result['success']:
                    # Update job with bid information
                    job['bid_generated'] = True
                    job['bid_content'] = bid_result['bid_content']
                    job['bid_generated_by'] = bid_result['generated_by']
                    job['auto_bid_enabled'] = True
                    
                    logger.info(f"✅ Bid generated for job {job['id']} using {bid_result['generated_by']}")
                    
                    # Here you could add actual bid submission logic
                    # For now, we just generate and store the bid
                    
                else:
                    logger.warning(f"❌ Failed to generate bid for job {job['id']}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing auto-bidding for job {job['id']}: {e}")

    def _save_job_to_db(self, job: Dict):
        """Save a job to the database and log scraped event"""
        try:
            from db import get_session
            from models import Job as JobModel
            import json
            
            with get_session() as session:
                # Check if job already exists
                existing_job = session.query(JobModel).filter(
                    JobModel.external_id == job['id']
                ).first()
                
                if existing_job:
                    # Update existing job
                    existing_job.title = job.get('title', existing_job.title)
                    existing_job.description = job.get('description', existing_job.description)
                    existing_job.original_description = job.get('original_description', existing_job.original_description)
                    existing_job.link = job.get('link', existing_job.link)
                    existing_job.client = job.get('client', existing_job.client)
                    existing_job.client_username = job.get('client_username', existing_job.client_username)
                    existing_job.client_display_name = job.get('client_display_name', existing_job.client_display_name)
                    existing_job.avatar = job.get('avatar', existing_job.avatar)
                    existing_job.employer_id = job.get('employer_id', existing_job.employer_id)
                    existing_job.employer_contracts_count = job.get('employer_contracts_count', existing_job.employer_contracts_count)
                    existing_job.employer_completed_count = job.get('employer_completed_count', existing_job.employer_completed_count)
                    existing_job.employer_last_activity = job.get('employer_last_activity', existing_job.employer_last_activity)
                    existing_job.category = job.get('category', existing_job.category)
                    existing_job.posted_at = job.get('posted_at', existing_job.posted_at)
                    existing_job.posted_time_formatted = job.get('posted_time_formatted', existing_job.posted_time_formatted)
                    existing_job.posted_time_relative = job.get('posted_time_relative', existing_job.posted_time_relative)
                    
                    # Update job price info
                    if job.get('job_price'):
                        price = job['job_price']
                        existing_job.job_price_type = price.get('type', existing_job.job_price_type)
                        existing_job.job_price_amount = str(price.get('amount', '')) if price.get('amount') else existing_job.job_price_amount
                        existing_job.job_price_currency = price.get('currency', existing_job.job_price_currency)
                        existing_job.job_price_formatted = price.get('formatted', existing_job.job_price_formatted)
                    
                    if job.get('budget_info'):
                        existing_job.budget_info_json = json.dumps(job['budget_info'])
                    
                    # Update keywords (convert list to JSON string if needed)
                    if job.get('keywords'):
                        existing_job.keywords = json.dumps(job['keywords']) if isinstance(job['keywords'], list) else job['keywords']
                    
                    db_job = existing_job
                    is_new = False
                else:
                    # Create new job
                    job_price = job.get('job_price', {})
                    db_job = JobModel(
                        external_id=job['id'],
                        title=job.get('title', ''),
                        description=job.get('description', ''),
                        original_description=job.get('original_description', ''),
                        link=job.get('link', ''),
                        client=job.get('client'),
                        client_username=job.get('client_username'),
                        client_display_name=job.get('client_display_name'),
                        avatar=job.get('avatar'),
                        employer_id=job.get('employer_id'),
                        employer_contracts_count=job.get('employer_contracts_count'),
                        employer_completed_count=job.get('employer_completed_count'),
                        employer_last_activity=job.get('employer_last_activity'),
                        category=job.get('category'),
                        posted_at=job.get('posted_at'),
                        posted_time_formatted=job.get('posted_time_formatted'),
                        posted_time_relative=job.get('posted_time_relative'),
                        job_price_type=job_price.get('type'),
                        job_price_amount=str(job_price.get('amount', '')) if job_price.get('amount') else None,
                        job_price_currency=job_price.get('currency'),
                        job_price_formatted=job_price.get('formatted'),
                        budget_info_json=json.dumps(job.get('budget_info', {})) if job.get('budget_info') else None,
                        keywords=json.dumps(job.get('keywords')) if job.get('keywords') else None,
                        is_read=job.get('is_read', False),
                        bid_generated=job.get('bid_generated', False),
                        bid_content=job.get('bid_content'),
                        bid_generated_by=job.get('bid_generated_by'),
                        bid_submitted=job.get('bid_submitted', False),
                        auto_bid_enabled=job.get('auto_bid_enabled', False),
                        suitability_score=job.get('suitability_score')
                    )
                    session.add(db_job)
                    session.flush()  # Get the ID
                    is_new = True
                
                session.commit()
                
                # Job saved successfully
                if is_new:
                    logger.debug(f"✅ Saved new job: {job['id']} (DB ID: {db_job.id})")
                    
        except Exception as e:
            logger.error(f"❌ Error saving job to database: {e}", exc_info=True)
            # Don't raise - allow job processing to continue even if DB save fails
            pass

    def _cleanup_old_jobs(self):
        """Clean up old jobs to prevent memory leaks"""
        now = datetime.now()
        
        # Check if cleanup is needed
        if (self.last_cleanup_time is None or 
            (now - self.last_cleanup_time).total_seconds() >= self.cleanup_interval):
            
            with self.state_lock:
                original_count = len(self.current_jobs)
                
                # Filter out jobs older than max_age_hours
                cutoff_time = now.timestamp() - (self.job_max_age_hours * 3600)
                self.current_jobs = [
                    job for job in self.current_jobs 
                    if job.get('posted_at_timestamp', 0) > cutoff_time
                ]
                
                # Also clean up seen_job_ids and seen_job_order
                current_job_ids = {job['id'] for job in self.current_jobs}
                self.seen_job_ids = self.seen_job_ids.intersection(current_job_ids)
                
                # Clean up seen_job_order
                self.seen_job_order = deque(
                    [job_id for job_id in self.seen_job_order if job_id in current_job_ids]
                )
                
                # Clean up last_sent_job_ids
                self.last_sent_job_ids = self.last_sent_job_ids.intersection(current_job_ids)
                
                removed_count = original_count - len(self.current_jobs)
                if removed_count > 0:
                    logger.info(f"🧹 Cleaned up {removed_count} old jobs (kept {len(self.current_jobs)})")
                
                self.last_cleanup_time = now

    def _send_notifications_sync(self, jobs: List[Dict]):
        """Send notifications for new jobs (synchronous version)"""
        for job in jobs:
            title = f"New {job['category'].upper()} Job: {job['title']}"
            message = f"Client: {job['client']}\nBudget: {job.get('job_price', {}).get('formatted', 'Not specified')}"
            
            logger.info(f"Notification: {title}")
            
            # Here you could integrate with desktop notifications
            # For now, just log the notification

    def get_status(self) -> Dict:
        """Get current bot status"""
        uptime_seconds = 0
        if self.start_time:
            uptime_seconds = int((datetime.now() - self.start_time).total_seconds())
        
        return {
            'running': self.is_running,
            'paused': self.is_paused,
            'jobs_found': self.jobs_found,
            'unread_count': self.unread_count,
            'uptime': uptime_seconds,
            'categories': self.categories,
            'keywords': self.keywords,
            'interval': self.interval,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'last_scrape_time': self.last_scrape_time.isoformat() if self.last_scrape_time else None,
            'status_history': self.status_history[-10:] if self.status_history else [],  # Last 10 status changes
            'auto_bid_enabled': self.auto_bid_enabled,
            'chatgpt_api_key': self.chatgpt_api_key,
            'user_skills': self.user_skills,
            'min_suitability_score': self.min_suitability_score,
            'bid_template': self.bid_template
        }

    def get_jobs(self) -> List[Dict]:
        """Get all current jobs, filtered to exclude blocked users"""
        from db import get_session
        from models import BlockedUser
        
        # Get list of blocked users
        blocked_employer_ids = set()
        blocked_usernames = set()
        
        try:
            with get_session() as session:
                blocked_users = session.query(BlockedUser).filter(
                    BlockedUser.user_id == self.default_user_id
                ).all()
                
                for blocked in blocked_users:
                    if blocked.employer_id:
                        blocked_employer_ids.add(blocked.employer_id)
                    if blocked.client_username:
                        blocked_usernames.add(blocked.client_username)
        except Exception as e:
            logger.warning(f"⚠️ Failed to load blocked users: {e}")
        
        # Filter out jobs from blocked users
        filtered_jobs = []
        for job in self.current_jobs:
            job_employer_id = job.get('employer_id')
            job_username = job.get('client_username')
            
            # Skip if employer_id or username matches blocked list
            if (job_employer_id and job_employer_id in blocked_employer_ids) or \
               (job_username and job_username in blocked_usernames):
                continue
            
            filtered_jobs.append(job)
        
        return filtered_jobs

    def get_custom_prompt(self, prompt_index: int) -> str:
        """Get a custom prompt by index (1-3)"""
        if prompt_index == 1:
            return self.custom_prompts.get('prompt1', '')
        elif prompt_index == 2:
            return self.custom_prompts.get('prompt2', '')
        elif prompt_index == 3:
            return self.custom_prompts.get('prompt3', '')
        return ''

    def get_selected_model(self) -> str:
        """Get the selected GPT model"""
        return self.selected_model

    def mark_job_as_read(self, job_id: str):
        """Mark a job as read"""
        with self.state_lock:
            for job in self.current_jobs:
                if job['id'] == job_id:
                    job['is_read'] = True
                    self.unread_count = max(0, self.unread_count - 1)
                    logger.info(f"📖 Marked job {job_id} as read")
                    break

# Global bot instance
bot_instance = CrowdworksBot()

# Bot control functions
def start_bot(settings: Dict):
    """Start the bot with given settings (single-user mode: always user_id=1)"""
    try:
        # Set settings first
        bot_instance.set_settings(settings)
        # Then start - this is where crashes might occur
        bot_instance.start()
    except KeyboardInterrupt:
        # Don't catch keyboard interrupts
        raise
    except SystemExit:
        # Don't catch system exits
        raise
    except BaseException as e:
        # Catch ALL exceptions including system-level ones
        logger.error(f"❌ Error in start_bot function: {e}", exc_info=True)
        # Reset bot state on error
        try:
            bot_instance.is_running = False
            bot_instance.is_paused = False
        except Exception:
            pass
        # Re-raise so caller knows it failed, but don't crash the server
        # The caller (main.py) will handle this gracefully
        raise

def stop_bot():
    """Stop the bot"""
    bot_instance.stop()

def pause_bot():
    """Pause the bot"""
    bot_instance.pause()

def resume_bot():
    """Resume the bot"""
    bot_instance.resume()

def get_bot_status() -> Dict:
    """Get bot status"""
    return bot_instance.get_status()

def get_bot_jobs() -> List[Dict]:
    """Get bot jobs"""
    return bot_instance.get_jobs()

def mark_job_read(job_id: str):
    """Mark job as read"""
    bot_instance.mark_job_as_read(job_id)

def get_current_settings() -> Dict:
    """Get current settings"""
    return bot_instance.get_settings()
