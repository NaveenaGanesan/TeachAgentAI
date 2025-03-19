from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from .email_message import EmailMessage

@dataclass
class Student:
    """Data model for a student."""
    email: str
    name: str = ""
    student_id: Optional[str] = None
    enrolled_sections: List[str] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    last_interaction: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_conversation(self, message: EmailMessage, response: str, intent: str = None):
        """Add a message and response to the conversation history."""
        interaction = {
            "timestamp": datetime.now(),
            "message": {
                "subject": message.subject,
                "body": message.body
            },
            "response": response,
            "intent": intent
        }
        
        self.conversation_history.append(interaction)
        self.last_interaction = datetime.now()
    
    def get_recent_conversations(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent conversation history, limited to specified number."""
        return self.conversation_history[-limit:] if self.conversation_history else []
