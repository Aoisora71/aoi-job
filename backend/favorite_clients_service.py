#!/usr/bin/env python3
"""Service for managing favorite clients and updating their status"""
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional
from db import get_session
from models import FavoriteClient, User, UserSettings
from real_crowdworks_scraper import RealCrowdworksScraper
from logging_utils import bot_logger as logger
from notification_service import notification_service

class FavoriteClientsService:
    def __init__(self):
        self.scraper = RealCrowdworksScraper()
        self.update_thread = None
        self.notification_thread = None
        self.running = False
        self.notification_running = False
        self.update_interval = 60  # Update every 60 seconds (1 minute)
        self.notification_interval = 120  # Check notifications every 2 minutes
        self.notification_threshold_minutes = 15  # Notify if last activity < 15 minutes
    
    def add_favorite(self, user_id: int, employer_id: str, employer_name: str = None, 
                    employer_display_name: str = None, avatar_url: str = None, 
                    profile_url: str = None) -> Dict:
        """Add a client to favorites"""
        try:
            with get_session() as session:
                # Check if already exists
                existing = session.query(FavoriteClient).filter(
                    FavoriteClient.user_id == user_id,
                    FavoriteClient.employer_id == employer_id
                ).first()
                
                if existing:
                    return {
                        'success': False,
                        'message': 'Client already in favorites',
                        'id': existing.id
                    }
                
                # Create new favorite
                favorite = FavoriteClient(
                    user_id=user_id,
                    employer_id=employer_id,
                    employer_name=employer_name,
                    employer_display_name=employer_display_name,
                    avatar_url=avatar_url,
                    profile_url=profile_url or f"https://crowdworks.jp/public/employers/{employer_id}"
                )
                session.add(favorite)
                session.flush()
                
                # Fetch initial status
                try:
                    employer_details = self.scraper.extract_employer_details(employer_id)
                    favorite.last_activity_hours = employer_details.get('last_activity')
                    favorite.contracts_count = employer_details.get('contracts_count')
                    favorite.completed_count = employer_details.get('completed_count')
                    favorite.last_status_update = datetime.utcnow()
                except Exception as e:
                    logger.warning(f"⚠️ Failed to fetch initial status for employer {employer_id}: {e}")
                
                session.commit()
                
                return {
                    'success': True,
                    'message': 'Client added to favorites',
                    'id': favorite.id
                }
        except Exception as e:
            logger.error(f"❌ Error adding favorite client: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def remove_favorite(self, user_id: int, favorite_id: int) -> Dict:
        """Remove a client from favorites"""
        try:
            with get_session() as session:
                favorite = session.query(FavoriteClient).filter(
                    FavoriteClient.id == favorite_id,
                    FavoriteClient.user_id == user_id
                ).first()
                
                if not favorite:
                    return {
                        'success': False,
                        'message': 'Favorite not found'
                    }
                
                session.delete(favorite)
                session.commit()
                
                return {
                    'success': True,
                    'message': 'Client removed from favorites'
                }
        except Exception as e:
            logger.error(f"❌ Error removing favorite client: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def get_favorites(self, user_id: int) -> List[Dict]:
        """Get all favorite clients for a user"""
        try:
            with get_session() as session:
                favorites = session.query(FavoriteClient).filter(
                    FavoriteClient.user_id == user_id
                ).order_by(FavoriteClient.created_at.desc()).all()
                
                return [{
                    'id': f.id,
                    'employer_id': f.employer_id,
                    'employer_name': f.employer_name,
                    'employer_display_name': f.employer_display_name,
                    'avatar_url': f.avatar_url,
                    'profile_url': f.profile_url,
                    'last_activity_hours': f.last_activity_hours,
                    'contracts_count': f.contracts_count,
                    'completed_count': f.completed_count,
                    'last_status_update': f.last_status_update.isoformat() if f.last_status_update else None,
                    'created_at': f.created_at.isoformat()
                } for f in favorites]
        except Exception as e:
            logger.error(f"❌ Error getting favorite clients: {e}")
            return []
    
    def update_client_status(self, favorite_id: int) -> bool:
        """Update status for a single favorite client"""
        try:
            with get_session() as session:
                favorite = session.query(FavoriteClient).filter(
                    FavoriteClient.id == favorite_id
                ).first()
                
                if not favorite:
                    return False
                
                # Fetch latest status
                employer_details = self.scraper.extract_employer_details(favorite.employer_id)
                
                favorite.last_activity_hours = employer_details.get('last_activity')
                favorite.contracts_count = employer_details.get('contracts_count')
                favorite.completed_count = employer_details.get('completed_count')
                favorite.last_status_update = datetime.utcnow()
                
                session.commit()
                return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to update status for favorite {favorite_id}: {e}")
            return False
    
    def update_all_statuses(self):
        """Update status for all favorite clients"""
        try:
            with get_session() as session:
                favorites = session.query(FavoriteClient).all()
                
                if not favorites:
                    return
                
                logger.info(f"🔄 Updating status for {len(favorites)} favorite clients...")
                
                updated_count = 0
                for favorite in favorites:
                    try:
                        employer_details = self.scraper.extract_employer_details(favorite.employer_id)
                        
                        favorite.last_activity_hours = employer_details.get('last_activity')
                        favorite.contracts_count = employer_details.get('contracts_count')
                        favorite.completed_count = employer_details.get('completed_count')
                        favorite.last_status_update = datetime.utcnow()
                        updated_count += 1
                        
                        # Small delay to avoid overwhelming the server
                        time.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to update status for employer {favorite.employer_id}: {e}")
                        continue
                
                session.commit()
                logger.info(f"✅ Updated status for {updated_count}/{len(favorites)} favorite clients")
        except Exception as e:
            logger.error(f"❌ Error updating all client statuses: {e}")
    
    def start_background_updates(self):
        """Start background thread to update client statuses"""
        if self.running:
            return
        
        self.running = True
        
        def update_loop():
            logger.info("🔄 Starting background client status update service...")
            while self.running:
                try:
                    self.update_all_statuses()
                    # Wait for update interval
                    for _ in range(self.update_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Error in background update loop: {e}")
                    time.sleep(10)  # Wait a bit before retrying
        
        self.update_thread = threading.Thread(target=update_loop, daemon=True, name="FavoriteClientsUpdater")
        self.update_thread.start()
        logger.info("✅ Background client status update service started")
    
    def stop_background_updates(self):
        """Stop background update thread"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        logger.info("🛑 Background client status update service stopped")
    
    def _load_notification_settings(self) -> Dict[str, Optional[str]]:
        """Load notification settings from database"""
        try:
            with get_session() as session:
                settings = session.query(UserSettings).filter(UserSettings.user_id == 1).first()
                if settings:
                    return {
                        'discord_webhook': settings.discord_webhook,
                        'telegram_token': settings.telegram_token,
                        'telegram_chat_id': settings.telegram_chat_id
                    }
        except Exception as e:
            logger.warning(f"⚠️ Failed to load notification settings: {e}")
        return {
            'discord_webhook': None,
            'telegram_token': None,
            'telegram_chat_id': None
        }
    
    def _check_and_send_notifications(self):
        """Check favorite clients and send notifications for active ones (runs every 2 minutes)"""
        try:
            logger.debug("🔍 Checking favorite clients for notifications (status < 15 minutes)...")
            
            # Load notification settings
            settings = self._load_notification_settings()
            notification_service.configure(
                telegram_token=settings.get('telegram_token'),
                telegram_chat_id=settings.get('telegram_chat_id'),
                discord_webhook=settings.get('discord_webhook')
            )
            
            # Check if any notification method is configured
            if not settings.get('discord_webhook') and not (settings.get('telegram_token') and settings.get('telegram_chat_id')):
                logger.debug("No notification methods configured, skipping notification check")
                return
            
            with get_session() as session:
                favorites = session.query(FavoriteClient).filter(
                    FavoriteClient.user_id == 1
                ).all()
                
                if not favorites:
                    logger.debug("No favorite clients found")
                    return
                
                active_clients = []
                for favorite in favorites:
                    # Check if last_activity_hours is less than 15 minutes
                    # Note: last_activity_hours is stored in minutes despite the name
                    if favorite.last_activity_hours is not None and favorite.last_activity_hours < self.notification_threshold_minutes:
                        client_name = favorite.employer_display_name or favorite.employer_name or f"Client {favorite.employer_id}"
                        active_clients.append({
                            'name': client_name,
                            'activity_minutes': favorite.last_activity_hours,
                            'profile_url': favorite.profile_url,
                            'employer_id': favorite.employer_id
                        })
                        logger.debug(f"  ✓ {client_name}: {favorite.last_activity_hours} minutes ago (threshold: {self.notification_threshold_minutes} minutes)")
                    else:
                        if favorite.last_activity_hours is not None:
                            logger.debug(f"  ✗ {favorite.employer_display_name or favorite.employer_name or favorite.employer_id}: {favorite.last_activity_hours} minutes ago (above threshold)")
                
                if active_clients:
                    logger.info(f"📢 Found {len(active_clients)} active favorite client(s) (status < {self.notification_threshold_minutes} minutes), sending notifications...")
                    for client in active_clients:
                        result = notification_service.send_favorite_client_notification(
                            client_name=client['name'],
                            last_activity_minutes=client['activity_minutes'],
                            profile_url=client.get('profile_url')
                        )
                        if result['telegram'] or result['discord']:
                            logger.info(f"✅ Sent notification for {client['name']} ({client['activity_minutes']} minutes ago)")
                        else:
                            logger.warning(f"⚠️ Failed to send notification for {client['name']}")
                        # Small delay between notifications
                        time.sleep(0.5)
                else:
                    logger.debug("No active clients found (all clients have status >= 15 minutes)")
        except Exception as e:
            logger.error(f"❌ Error checking and sending notifications: {e}", exc_info=True)
    
    def start_notification_monitoring(self):
        """Start background thread to monitor and send notifications"""
        if self.notification_running:
            return
        
        self.notification_running = True
        
        def notification_loop():
            logger.info(f"📢 Starting favorite client notification monitoring service...")
            logger.info(f"   - Check interval: Every {self.notification_interval} seconds ({self.notification_interval // 60} minutes)")
            logger.info(f"   - Notification threshold: Status < {self.notification_threshold_minutes} minutes")
            while self.notification_running:
                try:
                    self._check_and_send_notifications()
                    # Wait for notification interval (2 minutes = 120 seconds)
                    logger.debug(f"⏳ Waiting {self.notification_interval} seconds until next notification check...")
                    for _ in range(self.notification_interval):
                        if not self.notification_running:
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ Error in notification monitoring loop: {e}")
                    time.sleep(10)  # Wait a bit before retrying
        
        self.notification_thread = threading.Thread(target=notification_loop, daemon=True, name="FavoriteClientsNotifier")
        self.notification_thread.start()
        logger.info("✅ Favorite client notification monitoring service started")
    
    def stop_notification_monitoring(self):
        """Stop notification monitoring thread"""
        self.notification_running = False
        if self.notification_thread:
            self.notification_thread.join(timeout=5)
        logger.info("🛑 Favorite client notification monitoring service stopped")

# Global service instance
favorite_clients_service = FavoriteClientsService()

