import uuid
import time
from typing import List

from jarvis.core.events import Event, EventType

class Session:
    def __init__(self):
        self._session_id = str(uuid.uuid4())
        self.created_at = time.time()
        self.events: List[Event] = []
        self._is_active = True
        
        self.add_event(Event(
            type=EventType.SESSION_START,
            session_id=self._session_id,
            data={"created_at": self.created_at}
        ))
        
    def add_event(self, event: Event) -> None:
        self.events.append(event)
        
    @property
    def session_id(self) -> str:
        return self._session_id
        
    @property
    def is_active(self) -> bool:
        return self._is_active
        
    def end(self) -> None:
        if self._is_active:
            self._is_active = False
            self.add_event(Event(
                type=EventType.SESSION_END,
                session_id=self._session_id,
                data={"ended_at": time.time()}
            ))
