from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

@dataclass
class Course:
    """Data model for a course."""
    name: str
    code: str
    term: str
    professor: str
    description: str = ""
    syllabus: str = ""
    schedule: Dict[str, Any] = field(default_factory=dict)
    deadlines: List[Dict[str, Any]] = field(default_factory=list)
    policies: Dict[str, str] = field(default_factory=dict)
    resources: Dict[str, str] = field(default_factory=dict)
    
    def get_upcoming_deadlines(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get deadlines coming up within specified number of days."""
        now = datetime.now()
        upcoming = []
        
        for deadline in self.deadlines:
            if isinstance(deadline["date"], str):
                deadline_date = datetime.fromisoformat(deadline["date"])
            else:
                deadline_date = deadline["date"]
                
            delta = (deadline_date - now).days
            if 0 <= delta <= days:
                upcoming.append(deadline)
                
        return upcoming