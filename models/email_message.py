from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

@dataclass
class EmailMessage:
    """Data model for an email message."""
    message_id: str
    subject: str
    sender: str
    recipient: str
    body: str
    date: datetime
    raw_content: str = field(repr=False)  # Full raw email content
    cc: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    references: Optional[str] = None  # Reference to previous messages in thread
    in_reply_to: Optional[str] = None  # Direct reference to message being replied to
    thread_id: Optional[str] = None  # Thread ID for grouping conversations
    
    @property
    def sender_name(self) -> str:
        """Extract name from sender email"""
        if '<' in self.sender:
            return self.sender.split('<')[0].strip()
        return self.sender.split('@')[0]
    
    @property
    def sender_email(self) -> str:
        """Extract email address from sender"""
        if '<' in self.sender:
            return self.sender.split('<')[1].split('>')[0]
        return self.sender
    
    @property
    def is_student_email(self) -> bool:
        """Check if email is from a student based on domain"""
        from config.settings import EMAIL_CONFIG
        student_domain = EMAIL_CONFIG["student_domain"]
        return student_domain in self.sender_email