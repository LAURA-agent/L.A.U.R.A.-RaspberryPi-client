#!/usr/bin/env python3

import json
import time
import uuid
from pathlib import Path
from typing import Literal

class ClaudeTTSNotifier:
    """
    Helper class for Claude to send TTS notifications to the user.
    
    When Claude needs to ask questions, provide warnings, or draw attention
    to something important, it writes JSON files that the TTS server monitors
    and converts to speech.
    """
    
    def __init__(self, notifications_dir: str = "/home/user/RP500-Client/tts_notifications"):
        self.notifications_dir = Path(notifications_dir)
        self.notifications_dir.mkdir(exist_ok=True)
        
    def notify(self, 
               text: str, 
               notification_type: Literal["question", "warning", "error", "status", "confirmation"] = "status",
               priority: Literal["low", "medium", "high", "urgent"] = "medium") -> str:
        """
        Send a TTS notification to the user.
        
        Args:
            text: The message to be spoken via TTS
            notification_type: Type of notification (question, warning, error, status, confirmation)
            priority: Priority level (low, medium, high, urgent)
            
        Returns:
            message_id: Unique identifier for this notification
        """
        message_id = f"claude-{notification_type}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        notification_data = {
            "timestamp": time.time(),
            "message_id": message_id,
            "text": text,
            "type": notification_type,
            "priority": priority,
            "already_ttsd": False,
            "source": "claude_assistant"
        }
        
        # Write to JSON file
        notification_file = self.notifications_dir / f"{message_id}.json"
        try:
            with open(notification_file, 'w') as f:
                json.dump(notification_data, f, indent=2)
            print(f"[ClaudeTTSNotifier] Notification sent: {message_id}")
            return message_id
        except Exception as e:
            print(f"[ClaudeTTSNotifier] Error writing notification: {e}")
            return ""
    
    def ask_question(self, question: str) -> str:
        """Ask the user a question via TTS"""
        return self.notify(question, notification_type="question", priority="high")
    
    def warn_user(self, warning: str) -> str:
        """Send a warning to the user via TTS"""
        return self.notify(warning, notification_type="warning", priority="high")
    
    def report_error(self, error: str) -> str:
        """Report an error to the user via TTS"""
        return self.notify(error, notification_type="error", priority="urgent")
    
    def update_status(self, status: str) -> str:
        """Send a status update to the user via TTS"""
        return self.notify(status, notification_type="status", priority="medium")
    
    def request_confirmation(self, confirmation: str) -> str:
        """Request user confirmation via TTS"""
        return self.notify(confirmation, notification_type="confirmation", priority="high")

# Global instance for easy access
tts_notifier = ClaudeTTSNotifier()