from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Dict, Any, Callable
from app.utils.logging import setup_logging
from datetime import datetime
import asyncio
from pathlib import Path

logger = setup_logging()


class ThreadManager:
    def __init__(self, max_workers: int = 10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_lock = threading.Lock()

    def add_task(self, task_id: str, endpoint: str) -> Dict[str, Any]:
        """Record new task start"""
        with self.task_lock:
            task_info = {
                'task_id': task_id,
                'endpoint': endpoint,
                'status': 'processing',
                'start_time': datetime.now().isoformat(),
                'result': None,
                'error': None
            }
            self.active_tasks[task_id] = task_info
            return task_info

    def update_task_status(self, task_id: str, status: str, result: Dict[str, Any] = None):
        """Update status of a task"""
        with self.task_lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id].update({
                    'status': status,
                    'end_time': datetime.now().isoformat() if status in ['completed', 'failed', 'error'] else None,
                    'result': result or self.active_tasks[task_id].get('result')
                })
                logger.info(f"Updated task {task_id} status to {status}")
            else:
                logger.warning(f"Attempted to update non-existent task {task_id}")

    def can_accept_task(self) -> bool:
        """Check if we can accept new task"""
        with self.task_lock:
            running_tasks = sum(1 for task in self.active_tasks.values()
                                if task['status'] == 'processing')
            return running_tasks < self.executor._max_workers

    def submit_task(self, task_id: str, func: Callable, *args, **kwargs):
        """Submit task to thread pool"""
        self.executor.submit(self._run_task, task_id, func, *args, **kwargs)

    def _run_task(self, task_id: str, func: Callable, *args, **kwargs):
        """Run task in thread"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                if asyncio.iscoroutinefunction(func):
                    result = loop.run_until_complete(func(*args, **kwargs))
                else:
                    result = func(*args, **kwargs)

                with self.task_lock:
                    if task_id in self.active_tasks:
                        self.active_tasks[task_id].update({
                            'status': 'completed',
                            'end_time': datetime.now().isoformat(),
                            'result': result
                        })
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error in task {task_id}: {str(e)}")
            with self.task_lock:
                if task_id in self.active_tasks:
                    self.active_tasks[task_id].update({
                        'status': 'failed',
                        'end_time': datetime.now().isoformat(),
                        'error': str(e)
                    })

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of specific task"""
        with self.task_lock:
            return self.active_tasks.get(task_id, {})

    def cleanup(self):
        """Cleanup old agent_tasks"""
        with self.task_lock:
            current_time = datetime.now()
            to_remove = []
            for task_id, task in self.active_tasks.items():
                if task['status'] in ['completed', 'failed']:
                    # Remove agent_tasks older than 1 hour
                    start_time = datetime.fromisoformat(task['start_time'])
                    if (current_time - start_time).total_seconds() > 3600:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self.active_tasks[task_id]



    def get_task_status_all(self) -> Dict[str, Any]:
        """Get all agent_tasks status"""
        with self.task_lock:
            return self.active_tasks.copy()


# Create singleton instance
thread_manager = ThreadManager()