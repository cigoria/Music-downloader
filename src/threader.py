import multiprocessing as mp
import queue
import uuid
import time
from typing import Callable, Iterable

SEC_PER_CHECK = 2


def worker_process(job_queue: mp.Queue, pause_event: mp.Event):
    worker_id = uuid.uuid4()

    while True:
        pause_event.wait()  # pause support

        try:
            job = job_queue.get(timeout=SEC_PER_CHECK)
        except queue.Empty:
            continue

        if job is None:
            # shutdown signal
            break

        try:
            job()
            print(f"{worker_id} completed a job")
        finally:
            job_queue.task_done()


class QueueSystem:
    def __init__(self, max_processes: int = 4):
        self.job_queue = mp.JoinableQueue()
        self.pause_event = mp.Event()
        self.pause_event.set()

        self.workers: list[mp.Process] = []
        for _ in range(max_processes):
            p = mp.Process(
                target=worker_process,
                args=(self.job_queue, self.pause_event),
                daemon=True,
            )
            p.start()
            self.workers.append(p)

    def submit_jobs(self, jobs: Iterable[Callable]):
        for job in jobs:
            self.job_queue.put(job)

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()

    def abort(self, clear_queue: bool = True):
        """
        Force-terminate all worker processes.
        This WILL kill running jobs immediately.
        """
        # Kill workers
        for p in self.workers:
            if p.is_alive():
                p.terminate()
                p.join()

        self.workers.clear()

        if clear_queue:
            while True:
                try:
                    self.job_queue.get_nowait()
                    self.job_queue.task_done()
                except queue.Empty:
                    break

    def shutdown_graceful(self):
        """Let workers exit cleanly after finishing current jobs."""
        for _ in self.workers:
            self.job_queue.put(None)

        self.job_queue.join()

        for p in self.workers:
            p.join()

    def wait_completion(self):
        self.job_queue.join()
