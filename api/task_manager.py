import queue
from typing import Dict, Any
import uuid
import threading

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, queue.Queue] = {}
        self._lock = threading.Lock()

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self.tasks[task_id] = queue.Queue()
        return task_id

    def get_queue(self, task_id: str) -> queue.Queue:
        with self._lock:
            if task_id not in self.tasks:
                self.tasks[task_id] = queue.Queue()
            return self.tasks[task_id]

    def close_task_queue(self, task_id: str):
        with self._lock:
            if task_id in self.tasks:
                # Signal the end of the stream
                self.tasks[task_id].put(None)
                del self.tasks[task_id]

task_manager = TaskManager() 