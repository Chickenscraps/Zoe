"""
Cross-platform process-level instance lock (Highlander Rule).

Prevents multiple Edge Factory bot processes from running simultaneously.
Uses OS-level file locking so a crash automatically releases the lock.

Usage:
    lock = InstanceLock("data/edge_factory.lock")
    lock.acquire()   # raises InstanceAlreadyRunning if another process holds it
    try:
        ... run the bot ...
    finally:
        lock.release()

Or as a context manager:
    with InstanceLock("data/edge_factory.lock"):
        ... run the bot ...
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)


class InstanceAlreadyRunning(RuntimeError):
    """Raised when another bot process already holds the lock."""
    pass


class InstanceLock:
    """OS-level file lock to enforce single-instance trading."""

    def __init__(self, lock_path: str = "data/edge_factory.lock"):
        self.lock_path = lock_path
        self._file = None
        self._locked = False

    def acquire(self) -> None:
        """Acquire the lock. Raises InstanceAlreadyRunning if held."""
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(self.lock_path) or ".", exist_ok=True)

        try:
            self._file = open(self.lock_path, "w")  # noqa: SIM115

            if sys.platform == "win32":
                import msvcrt
                try:
                    # Lock first byte exclusively, non-blocking
                    msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
                except (IOError, OSError):
                    self._file.close()
                    self._file = None
                    raise InstanceAlreadyRunning(
                        f"Another Edge Factory process is already running "
                        f"(lock: {self.lock_path}). "
                        f"Kill the other process first or delete the lock file."
                    )
            else:
                import fcntl
                try:
                    fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (IOError, OSError):
                    self._file.close()
                    self._file = None
                    raise InstanceAlreadyRunning(
                        f"Another Edge Factory process is already running "
                        f"(lock: {self.lock_path}). "
                        f"Kill the other process first or delete the lock file."
                    )

            # Write PID for debugging
            self._file.write(str(os.getpid()))
            self._file.flush()
            self._locked = True
            logger.info(
                "Instance lock acquired (PID %d, lock=%s)", os.getpid(), self.lock_path
            )

        except InstanceAlreadyRunning:
            raise
        except Exception as e:
            logger.warning("Failed to acquire instance lock: %s", e)
            # Don't block startup on lock errors (e.g. read-only FS)
            # Just warn — the launcher socket lock is a secondary guard

    def release(self) -> None:
        """Release the lock and clean up."""
        if self._file is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    try:
                        self._file.seek(0)
                        msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
                    except (IOError, OSError):
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
                    except (IOError, OSError):
                        pass

                self._file.close()
            except Exception:
                pass
            finally:
                self._file = None
                self._locked = False

            # Remove lock file
            try:
                os.remove(self.lock_path)
            except OSError:
                pass

            logger.info("Instance lock released (lock=%s)", self.lock_path)

    @property
    def is_locked(self) -> bool:
        return self._locked

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()
