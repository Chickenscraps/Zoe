
import time
import functools
import random
from notification_router import route_attention

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit Breaker is OPEN. Gemini is currently unavailable.")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure(e)
            raise e

    def on_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def on_failure(self, error):
        self.failures += 1
        self.last_failure_time = time.time()
        print(f"DEBUG: Circuit Breaker Failure {self.failures}/{self.failure_threshold}: {error}")
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            route_attention("Gemini Outage detected", "I've lost connection to my primary brain. Switching to offline mode until things stabilize.", urgency="critical")

# Global instances
gemini_breaker = CircuitBreaker()

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        raise e
                    sleep_time = (backoff_in_seconds * 2 ** x + random.uniform(0, 1))
                    print(f"DEBUG: Retrying in {sleep_time:.2f}s due to error: {e}")
                    time.sleep(sleep_time)
                    x += 1
        return wrapper
    return decorator

def resilient_call(func, *args, **kwargs):
    """
    Main entry point for resilient Gemini calls.
    """
    try:
        return gemini_breaker.call(func, *args, **kwargs)
    except Exception as e:
        # If open or final failure, we could return a 'degraded mode' response here
        if "Circuit Breaker is OPEN" in str(e):
            return "I'm currently in offline mode. I can't think deeply right now, but I'm still watching your deck!"
        raise e
