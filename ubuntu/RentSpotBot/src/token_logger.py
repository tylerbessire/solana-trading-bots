"""
Logger for token events
"""
import logging
from typing import List, Dict
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

class TokenEventLogger:
    def __init__(self, max_events: int = 100):
        self.events = deque(maxlen=max_events)
        self.statistics: Dict = {
            'total_events': 0,
            'last_event_time': None
        }

    async def log_event(self, event_data: dict):
        """Log a new token event"""
        event = {
            'timestamp': datetime.now(),
            'data': event_data
        }
        self.events.append(event)
        self.statistics['total_events'] += 1
        self.statistics['last_event_time'] = event['timestamp']
        logger.info(f"Logged new token event: {event_data.get('mint', 'unknown')}")

    def get_event_statistics(self) -> Dict:
        """Get statistics about logged events"""
        return self.statistics

    def get_recent_events(self, count: int = 5) -> List[dict]:
        """Get most recent events"""
        return list(self.events)[-count:]
