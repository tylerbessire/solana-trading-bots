import asyncio
import time
from typing import Dict, Optional

class ConnectionMonitor:
    def __init__(self):
        self.last_message_time = {}
        self.connection_status = {}
        self.reconnect_attempts = {}
        self.MAX_RECONNECT_ATTEMPTS = 3
        self.TIMEOUT_SECONDS = 5

    async def monitor_connection(self, connection_id: str, check_interval: float = 1.0):
        """Monitor connection health and attempt reconnection if needed"""
        while True:
            try:
                current_time = time.time()
                last_time = self.last_message_time.get(connection_id)

                if last_time and (current_time - last_time) > self.TIMEOUT_SECONDS:
                    print(f"Connection {connection_id} may be stale. Last message: {current_time - last_time:.2f}s ago")
                    self.connection_status[connection_id] = False

                    # Attempt reconnection if needed
                    if self.reconnect_attempts.get(connection_id, 0) < self.MAX_RECONNECT_ATTEMPTS:
                        print(f"Attempting to reconnect {connection_id}...")
                        self.reconnect_attempts[connection_id] = self.reconnect_attempts.get(connection_id, 0) + 1
                        # Signal for reconnection
                        return False

                await asyncio.sleep(check_interval)

            except Exception as e:
                print(f"Error monitoring connection {connection_id}: {e}")
                return False

    def update_last_message(self, connection_id: str):
        """Update the last message time for a connection"""
        self.last_message_time[connection_id] = time.time()
        self.connection_status[connection_id] = True
        self.reconnect_attempts[connection_id] = 0

    def is_connection_healthy(self, connection_id: str) -> bool:
        """Check if a connection is currently healthy"""
        return self.connection_status.get(connection_id, False)
