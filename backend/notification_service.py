#!/usr/bin/env python3
"""
Notification service for sending messages via Telegram and Discord
"""

import requests
import json
from typing import Optional, Dict
from logging_utils import get_logger

logger = get_logger('notification_service')


class NotificationService:
    """Service for sending notifications via Telegram and Discord"""
    
    def __init__(self):
        self.telegram_token: Optional[str] = None
        self.telegram_chat_id: Optional[str] = None
        self.discord_webhook: Optional[str] = None
    
    def configure(self, telegram_token: Optional[str] = None, 
                  telegram_chat_id: Optional[str] = None,
                  discord_webhook: Optional[str] = None):
        """Configure notification settings"""
        if telegram_token:
            self.telegram_token = telegram_token
        if telegram_chat_id:
            self.telegram_chat_id = telegram_chat_id
        if discord_webhook:
            self.discord_webhook = discord_webhook
    
    def send_telegram_message(self, message: str) -> bool:
        """Send a message via Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.debug("Telegram not configured (missing token or chat_id)")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.debug("✅ Telegram message sent successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending Telegram message: {e}")
            return False
    
    def send_discord_message(self, message: str, username: Optional[str] = None) -> bool:
        """Send a message via Discord webhook"""
        if not self.discord_webhook:
            logger.debug("Discord not configured (missing webhook)")
            return False
        
        try:
            payload = {
                'content': message
            }
            if username:
                payload['username'] = username
            
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.debug("✅ Discord message sent successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send Discord message: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending Discord message: {e}")
            return False
    
    def send_favorite_client_notification(self, client_name: str, last_activity_minutes: int, 
                                         profile_url: Optional[str] = None) -> Dict[str, bool]:
        """Send notification about a favorite client with recent activity"""
        # Format the message
        activity_text = f"{last_activity_minutes} minute{'s' if last_activity_minutes != 1 else ''} ago"
        
        telegram_message = (
            f"🔔 <b>Favorite Client Active!</b>\n\n"
            f"👤 <b>{client_name}</b>\n"
            f"⏰ Last activity: {activity_text}\n"
        )
        if profile_url:
            telegram_message += f"🔗 <a href='{profile_url}'>View Profile</a>"
        
        discord_message = (
            f"🔔 **Favorite Client Active!**\n\n"
            f"👤 **{client_name}**\n"
            f"⏰ Last activity: {activity_text}\n"
        )
        if profile_url:
            discord_message += f"🔗 {profile_url}"
        
        # Send to both services
        telegram_sent = self.send_telegram_message(telegram_message)
        discord_sent = self.send_discord_message(discord_message, username="Crowdworks Monitor")
        
        return {
            'telegram': telegram_sent,
            'discord': discord_sent
        }
    
    def test_telegram(self) -> Dict[str, any]:
        """Test Telegram configuration"""
        if not self.telegram_token or not self.telegram_chat_id:
            return {
                'success': False,
                'error': 'Telegram token or chat ID not configured'
            }
        
        test_message = "🧪 Test message from Crowdworks Monitor"
        success = self.send_telegram_message(test_message)
        
        return {
            'success': success,
            'message': 'Test message sent successfully' if success else 'Failed to send test message'
        }
    
    def test_discord(self) -> Dict[str, any]:
        """Test Discord configuration"""
        if not self.discord_webhook:
            return {
                'success': False,
                'error': 'Discord webhook not configured'
            }
        
        test_message = "🧪 Test message from Crowdworks Monitor"
        success = self.send_discord_message(test_message, username="Crowdworks Monitor")
        
        return {
            'success': success,
            'message': 'Test message sent successfully' if success else 'Failed to send test message'
        }


# Global notification service instance
notification_service = NotificationService()

