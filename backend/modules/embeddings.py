"""
Embeddings Module: Centralized embedding generation and utilities.

This module provides unified embedding generation functions to avoid duplication
across ingestion, verified_qna, and retrieval modules.

SECURITY FIXES:
- Added timeout handling for all external API calls (HIGH Bug H2)
- Retry logic with exponential backoff
- Circuit breaker pattern for resilience
"""
from typing import List, Optional
import os
import asyncio
import time
from functools import wraps
from modules.clients import get_openai_client

# =============================================================================
# TIMEOUT AND RETRY CONFIGURATION (CRITICAL BUG FIX: H2)
# =============================================================================

# Default timeouts (seconds)
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))
EMBEDDING_RETRY_ATTEMPTS = int(os.getenv("EMBEDDING_RETRY_ATTEMPTS", "3"))
EMBEDDING_RETRY_DELAY = float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0"))
EMBEDDING_RETRY_BACKOFF = float(os.getenv("EMBEDDING_RETRY_BACKOFF", "2.0"))

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "60"))  # Seconds before reset


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Failing fast (recent failures exceeded threshold)
    - HALF_OPEN: Testing if service recovered
    """
    
    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"
    
    def __init__(self, threshold: int = CIRCUIT_BREAKER_THRESHOLD, timeout: int = CIRCUIT_BREAKER_TIMEOUT):
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = self.STATE_CLOSED
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == self.STATE_OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = self.STATE_HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN - service temporarily unavailable")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = self.STATE_CLOSED
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.threshold:
            self.state = self.STATE_OPEN


# Global circuit breaker for embeddings
_embedding_circuit_breaker = CircuitBreaker()


def with_retry_and_timeout(max_attempts: int = None, timeout_seconds: int = None):
    """
    Decorator to add retry logic with timeout to embedding operations.
    
    Args:
        max_attempts: Maximum retry attempts
        timeout_seconds: Timeout per attempt in seconds
    """
    max_attempts = max_attempts or EMBEDDING_RETRY_ATTEMPTS
    timeout_seconds = timeout_seconds or EMBEDDING_TIMEOUT
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = EMBEDDING_RETRY_DELAY
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    # Use asyncio.wait_for for timeout if in async context
                    import concurrent.futures
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(func, *args, **kwargs)
                        return future.result(timeout=timeout_seconds)
                        
                except concurrent.futures.TimeoutError:
                    last_error = TimeoutError(f"Embedding request timed out after {timeout_seconds}s")
                    print(f"[Embedding] Timeout on attempt {attempt + 1}/{max_attempts}")
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Don't retry on auth errors or invalid input
                    non_retryable = ["authentication", "invalid", "not found", "permission"]
                    if any(nr in error_msg for nr in non_retryable):
                        raise
                    
                    print(f"[Embedding] Error on attempt {attempt + 1}/{max_attempts}: {e}")
                
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                    delay *= EMBEDDING_RETRY_BACKOFF
            
            raise last_error or Exception("Embedding failed after all retries")
        
        return wrapper
    return decorator


# =============================================================================
# EMBEDDING FUNCTIONS WITH TIMEOUTS
# =============================================================================

@with_retry_and_timeout()
def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text using OpenAI.
    
    Args:
        text: Text to embed
        
    Returns:
        List of floats representing the embedding vector
        
    Raises:
        TimeoutError: If request exceeds timeout
        Exception: On API errors
    """
    client = get_openai_client()
    
    # Use circuit breaker for resilience
    def _fetch():
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-large",
            dimensions=3072
        )
        return response.data[0].embedding
    
    return _embedding_circuit_breaker.call(_fetch)


async def get_embeddings_async(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts asynchronously (batch processing).
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors (one per input text)
        
    Raises:
        TimeoutError: If request exceeds timeout
    """
    client = get_openai_client()
    loop = asyncio.get_event_loop()
    
    def _fetch():
        # Use timeout in the HTTP client level if possible
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-large",
            dimensions=3072,
            timeout=EMBEDDING_TIMEOUT  # OpenAI client supports timeout parameter
        )
        return [d.embedding for d in response.data]
    
    # Use circuit breaker
    try:
        return await loop.run_in_executor(None, lambda: _embedding_circuit_breaker.call(_fetch))
    except Exception as e:
        if "timeout" in str(e).lower():
            raise TimeoutError(f"Embedding batch request timed out after {EMBEDDING_TIMEOUT}s")
        raise


def get_embedding_with_timeout(text: str, timeout_seconds: int = None) -> Optional[List[float]]:
    """
    Generate embedding with explicit timeout, returns None on failure.
    
    Args:
        text: Text to embed
        timeout_seconds: Custom timeout (uses default if not specified)
        
    Returns:
        Embedding vector or None if failed
    """
    timeout = timeout_seconds or EMBEDDING_TIMEOUT
    
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(get_embedding, text)
            return future.result(timeout=timeout)
    except Exception as e:
        print(f"[Embedding] Failed to get embedding: {e}")
        return None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Calculate cosine similarity between two embedding vectors.
    
    Args:
        a: First embedding vector
        b: Second embedding vector
        
    Returns:
        Cosine similarity score between 0 and 1
    """
    if len(a) != len(b):
        return 0.0
    
    # Calculate dot product
    dot_product = sum(x * y for x, y in zip(a, b))
    
    # Calculate norms
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    # Avoid division by zero
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


def get_embedding_health_status() -> dict:
    """Get health status of embedding service."""
    return {
        "circuit_breaker_state": _embedding_circuit_breaker.state,
        "failure_count": _embedding_circuit_breaker.failure_count,
        "last_failure": _embedding_circuit_breaker.last_failure_time,
        "timeout_config": EMBEDDING_TIMEOUT,
        "retry_config": {
            "attempts": EMBEDDING_RETRY_ATTEMPTS,
            "delay": EMBEDDING_RETRY_DELAY,
            "backoff": EMBEDDING_RETRY_BACKOFF
        }
    }
