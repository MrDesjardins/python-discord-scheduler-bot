"""
Functions and classes about performance
"""

from dataclasses import dataclass
import time
from typing import Optional

from deps.log import print_error_log, print_log


@dataclass
class PerformanceOptions:
    """Performance options"""

    print_log: bool


class PerformanceContext:
    """Performance context"""

    def __init__(self, performance_name: str, option: Optional[PerformanceOptions]):
        self.performance_name = performance_name
        self.start = 0.0
        self.end = 0.0
        self.option = option if option is not None else PerformanceOptions(print_log=True)

    def __enter__(
        self,
    ):
        if self.option.print_log:
            print_log(f"Performance [{self.performance_name}] started")
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = time.perf_counter()
        elapsed = (self.end - self.start) * 1000  # Compute elapsed time in ms
        msg = f"Performance [{self.performance_name}] ended: {elapsed:.4f} ms"
        if exc_type is None:
            if self.option.print_log:
                print_log(msg)
        else:
            print_error_log(msg)
        return True

    def add_marker(self, marker: str):
        """Add a marker"""
        now = time.perf_counter()
        elapsed = (now - self.start) * 1000  # Compute elapsed time in ms
        if self.option.print_log:
            print_log(f"\tPerformance [{self.performance_name}/{marker}]: {elapsed:.4f} ms")
