"""
Thread pool implementation for parallel processing in RSPS Color Bot v3
"""
import logging
import threading
import queue
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Tuple, TypeVar, Generic, Union
from dataclasses import dataclass
import concurrent.futures

# Get module logger
logger = logging.getLogger('rspsbot.utils.threading.thread_pool')

# Define generic types for task input and output
T = TypeVar('T')
R = TypeVar('R')

@dataclass
class Task(Generic[T, R]):
    """
    Represents a task to be executed by the thread pool
    
    Attributes:
        id: Unique task identifier
        func: Function to execute
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        priority: Task priority (higher values = higher priority)
        timeout: Maximum execution time in seconds (None for no timeout)
    """
    id: str
    func: Callable[..., R]
    args: Tuple = ()
    kwargs: Dict[str, Any] = None
    priority: int = 0
    timeout: Optional[float] = None
    
    def __post_init__(self):
        """Initialize default values"""
        if self.kwargs is None:
            self.kwargs = {}
    
    def __lt__(self, other):
        """Compare tasks by priority for priority queue"""
        if not isinstance(other, Task):
            return NotImplemented
        return self.priority > other.priority  # Higher priority comes first

@dataclass
class TaskResult(Generic[R]):
    """
    Represents the result of a task execution
    
    Attributes:
        task_id: ID of the task that produced this result
        success: Whether the task completed successfully
        result: Result of the task (if successful)
        error: Exception that occurred (if unsuccessful)
        execution_time: Time taken to execute the task in seconds
    """
    task_id: str
    success: bool
    result: Optional[R] = None
    error: Optional[Exception] = None
    execution_time: float = 0.0

class ThreadPoolManager:
    """
    Manages a pool of worker threads for parallel task execution
    
    This class provides a high-level interface for submitting tasks to be
    executed in parallel and collecting their results.
    """
    
    def __init__(self, num_workers: int = None, queue_size: int = 100):
        """
        Initialize the thread pool manager
        
        Args:
            num_workers: Number of worker threads (None for CPU count)
            queue_size: Maximum size of the task queue
        """
        # Use CPU count if num_workers is None
        if num_workers is None:
            import multiprocessing
            num_workers = max(1, multiprocessing.cpu_count() - 1)
        
        self.num_workers = num_workers
        self.queue_size = queue_size
        
        # Create thread pool executor
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=num_workers,
            thread_name_prefix="BotWorker"
        )
        
        # Task queue (priority queue)
        self.task_queue = queue.PriorityQueue(maxsize=queue_size)
        
        # Results dictionary
        self._results_lock = threading.RLock()
        self._results: Dict[str, TaskResult] = {}
        
        # Control flags
        self._shutdown_event = threading.Event()
        self._workers_initialized = False
        
        logger.info(f"Thread pool manager initialized with {num_workers} workers")
    
    def start(self):
        """Start the worker threads"""
        if self._workers_initialized:
            logger.warning("Worker threads already started")
            return
        
        # Submit worker function to executor
        for _ in range(self.num_workers):
            self.executor.submit(self._worker_loop)
        
        self._workers_initialized = True
        logger.info(f"Started {self.num_workers} worker threads")
    
    def shutdown(self, wait: bool = True):
        """
        Shutdown the thread pool
        
        Args:
            wait: Whether to wait for tasks to complete
        """
        logger.info("Shutting down thread pool")
        self._shutdown_event.set()
        
        # Clear the queue to unblock any waiting workers
        try:
            while True:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
        except queue.Empty:
            pass
        
        # Shutdown the executor
        self.executor.shutdown(wait=wait)
        self._workers_initialized = False
        logger.info("Thread pool shutdown complete")
    
    def submit_task(self, func: Callable[..., R], *args, **kwargs) -> str:
        """
        Submit a task to the thread pool
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        
        Returns:
            Task ID
        
        Special kwargs:
            priority: Task priority (higher values = higher priority)
            timeout: Maximum execution time in seconds
        """
        # Extract special kwargs
        priority = kwargs.pop('priority', 0)
        timeout = kwargs.pop('timeout', None)
        
        # Create task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        task = Task(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout
        )
        
        # Add task to queue
        try:
            self.task_queue.put(task)
            logger.debug(f"Submitted task {task_id} with priority {priority}")
            return task_id
        except queue.Full:
            logger.error("Task queue is full, could not submit task")
            raise RuntimeError("Task queue is full")
    
    def submit_tasks(self, tasks: List[Tuple[Callable[..., R], List, Dict[str, Any]]]) -> List[str]:
        """
        Submit multiple tasks to the thread pool
        
        Args:
            tasks: List of (func, args, kwargs) tuples
        
        Returns:
            List of task IDs
        """
        task_ids = []
        for func, args, kwargs in tasks:
            task_id = self.submit_task(func, *args, **kwargs)
            task_ids.append(task_id)
        return task_ids
    
    def get_result(self, task_id: str, block: bool = True, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """
        Get the result of a task
        
        Args:
            task_id: Task ID
            block: Whether to block until the result is available
            timeout: Maximum time to wait for the result in seconds
        
        Returns:
            Task result or None if not available and not blocking
        """
        start_time = time.time()
        
        while True:
            # Check if result is available
            with self._results_lock:
                if task_id in self._results:
                    result = self._results[task_id]
                    del self._results[task_id]
                    return result
            
            # If not blocking, return None
            if not block:
                return None
            
            # Check timeout
            if timeout is not None and time.time() - start_time > timeout:
                logger.warning(f"Timeout waiting for result of task {task_id}")
                return None
            
            # Wait a bit before checking again
            time.sleep(0.01)
    
    def get_results(self, task_ids: List[str], block: bool = True, timeout: Optional[float] = None) -> Dict[str, TaskResult]:
        """
        Get the results of multiple tasks
        
        Args:
            task_ids: List of task IDs
            block: Whether to block until all results are available
            timeout: Maximum time to wait for all results in seconds
        
        Returns:
            Dictionary mapping task IDs to results
        """
        results = {}
        start_time = time.time()
        remaining_ids = set(task_ids)
        
        while remaining_ids:
            # Check if results are available
            with self._results_lock:
                for task_id in list(remaining_ids):
                    if task_id in self._results:
                        results[task_id] = self._results[task_id]
                        del self._results[task_id]
                        remaining_ids.remove(task_id)
            
            # If all results are available or not blocking, return results
            if not remaining_ids or not block:
                return results
            
            # Check timeout
            if timeout is not None and time.time() - start_time > timeout:
                logger.warning(f"Timeout waiting for results of {len(remaining_ids)} tasks")
                return results
            
            # Wait a bit before checking again
            time.sleep(0.01)
        
        return results
    
    def wait_for_tasks(self, task_ids: List[str], timeout: Optional[float] = None) -> bool:
        """
        Wait for tasks to complete
        
        Args:
            task_ids: List of task IDs
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if all tasks completed, False if timeout occurred
        """
        start_time = time.time()
        remaining_ids = set(task_ids)
        
        while remaining_ids:
            # Check if results are available
            with self._results_lock:
                for task_id in list(remaining_ids):
                    if task_id in self._results:
                        remaining_ids.remove(task_id)
            
            # If all results are available, return True
            if not remaining_ids:
                return True
            
            # Check timeout
            if timeout is not None and time.time() - start_time > timeout:
                logger.warning(f"Timeout waiting for {len(remaining_ids)} tasks")
                return False
            
            # Wait a bit before checking again
            time.sleep(0.01)
        
        return True
    
    def clear_results(self):
        """Clear all stored results"""
        with self._results_lock:
            self._results.clear()
    
    def _worker_loop(self):
        """Main worker thread loop"""
        thread_name = threading.current_thread().name
        logger.debug(f"Worker thread {thread_name} started")
        
        while not self._shutdown_event.is_set():
            try:
                # Get task from queue with timeout
                try:
                    task = self.task_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Execute task
                start_time = time.time()
                try:
                    if task.timeout is not None:
                        # Use a future with timeout
                        future = self.executor.submit(task.func, *task.args, **task.kwargs)
                        result = future.result(timeout=task.timeout)
                        success = True
                        error = None
                    else:
                        # Execute directly in this worker thread
                        result = task.func(*task.args, **task.kwargs)
                        success = True
                        error = None
                except concurrent.futures.TimeoutError:
                    success = False
                    result = None
                    error = TimeoutError(f"Task {task.id} timed out after {task.timeout} seconds")
                    logger.warning(f"Task {task.id} timed out")
                except Exception as e:
                    success = False
                    result = None
                    error = e
                    logger.error(f"Error executing task {task.id}: {e}")
                
                execution_time = time.time() - start_time
                
                # Store result
                task_result = TaskResult(
                    task_id=task.id,
                    success=success,
                    result=result,
                    error=error,
                    execution_time=execution_time
                )
                
                with self._results_lock:
                    self._results[task.id] = task_result
                
                # Mark task as done
                self.task_queue.task_done()
                
                logger.debug(f"Task {task.id} completed in {execution_time:.3f}s (success={success})")
            
            except Exception as e:
                logger.error(f"Unexpected error in worker thread: {e}")
        
        logger.debug(f"Worker thread {thread_name} stopped")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()