import threading
import queue
import uuid
from typing import Callable, Iterable

SEC_PER_CHECK = 2


class WorkerThread(threading.Thread):
    """A single worker that pulls callables from a queue and runs them."""

    def __init__(
        self,
        job_queue: queue.Queue,
        pause_event: threading.Event,
        abort_event: threading.Event,
        *,
        daemon: bool = True,
    ):
        super().__init__(daemon=daemon)
        self.job_queue = job_queue
        self.pause_event = pause_event
        self.abort_event = abort_event
        self.id = uuid.uuid4()

    def run(self) -> None:
        while not self.abort_event.is_set():
            # Block here if paused
            self.pause_event.wait()

            try:
                job = self.job_queue.get(timeout=SEC_PER_CHECK)
            except queue.Empty:
                continue

            try:
                if self.abort_event.is_set():
                    return

                job()  # Execute the callable
                print(f"{self.id} completed a job")

            finally:
                self.job_queue.task_done()


class QueueSystem:
    """Thread pool with pause, resume and abort support."""

    def __init__(self, max_threads: int = 4):
        self.job_queue = queue.Queue()

        self.pause_event = threading.Event()
        self.abort_event = threading.Event()

        # Start unpaused
        self.pause_event.set()

        self.workers: list[WorkerThread] = []
        for _ in range(max_threads):
            worker = WorkerThread(
                self.job_queue,
                self.pause_event,
                self.abort_event,
            )
            worker.start()
            self.workers.append(worker)

    def submit_jobs(self, jobs: Iterable[Callable]):
        if self.abort_event.is_set():
            raise RuntimeError("QueueSystem has been aborted")

        for job in jobs:
            if not callable(job):
                raise TypeError("All jobs must be callables")
            self.job_queue.put(job)

    def pause(self):
        """Pause execution of new jobs."""
        self.pause_event.clear()

    def resume(self):
        """Resume execution."""
        self.pause_event.set()

    def abort(self, clear_queue: bool = True):
        """
        Abort all workers.
        Optionally clears pending jobs.
        """
        self.abort_event.set()
        self.pause_event.set()  # wake paused workers

        if clear_queue:
            while True:
                try:
                    self.job_queue.get_nowait()
                    self.job_queue.task_done()
                except queue.Empty:
                    break

    def wait_completion(self):
        """Block until all queued jobs have finished."""
        self.job_queue.join()
