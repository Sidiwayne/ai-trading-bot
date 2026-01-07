"""
Retry Utilities for FusionBot
=============================

Exponential backoff and retry decorators for resilient API calls.
"""

import time
import random
from functools import wraps
from dataclasses import dataclass
from typing import Callable, Tuple, Type, Optional, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)

from src.utils.logging import get_logger
from src.core.exceptions import (
    RateLimitError,
    ExchangeConnectionError,
    AIRateLimitError,
)

logger = get_logger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        RateLimitError,
        ExchangeConnectionError,
    )


def with_retry(config: RetryConfig = None):
    """
    Decorator to add retry logic to a function.
    
    Args:
        config: RetryConfig instance or None for defaults
    
    Usage:
        @with_retry(RetryConfig(max_attempts=5))
        def call_api():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts:
                        logger.error(
                            "Max retries exceeded",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e),
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.initial_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay,
                    )
                    
                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        "Retrying after error",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay_seconds=round(delay, 2),
                        error=str(e),
                    )
                    
                    time.sleep(delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def create_exchange_retry():
    """
    Create a tenacity retry decorator for exchange API calls.
    
    Returns:
        Configured retry decorator
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError,
            RateLimitError,
        )),
        before_sleep=before_sleep_log(logger, log_level=logging.WARNING),
        reraise=True,
    )


def create_ai_retry():
    """
    Create a tenacity retry decorator for AI API calls.
    
    Returns:
        Configured retry decorator
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError,
            AIRateLimitError,
        )),
        before_sleep=before_sleep_log(logger, log_level=logging.WARNING),
        reraise=True,
    )


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.
    
    Prevents cascading failures by temporarily blocking calls
    to a failing service.
    
    States:
        - CLOSED: Normal operation, requests flow through
        - OPEN: Service is down, requests fail immediately
        - HALF_OPEN: Testing if service recovered
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        
        @breaker
        def call_external_service():
            ...
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"
        self._half_open_calls = 0
    
    @property
    def state(self) -> str:
        """Get current circuit state."""
        if self._state == "OPEN":
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = "HALF_OPEN"
                    self._half_open_calls = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
        
        return self._state
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_state = self.state
            
            if current_state == "OPEN":
                raise ExchangeConnectionError(
                    "Circuit breaker is OPEN - service unavailable"
                )
            
            try:
                result = func(*args, **kwargs)
                
                # Success - reset on HALF_OPEN
                if current_state == "HALF_OPEN":
                    self._half_open_calls += 1
                    if self._half_open_calls >= self.half_open_max_calls:
                        self._state = "CLOSED"
                        self._failure_count = 0
                        logger.info("Circuit breaker CLOSED - service recovered")
                
                return result
            
            except Exception as e:
                self._failure_count += 1
                self._last_failure_time = time.time()
                
                if self._failure_count >= self.failure_threshold:
                    self._state = "OPEN"
                    logger.error(
                        "Circuit breaker OPEN - service failures exceeded threshold",
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold,
                    )
                
                raise
        
        return wrapper
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._failure_count = 0
        self._last_failure_time = None
        self._state = "CLOSED"
        self._half_open_calls = 0
        logger.info("Circuit breaker manually reset")


# Import logging for tenacity
import logging

