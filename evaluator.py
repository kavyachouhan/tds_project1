import logging
import asyncio
import httpx
from models import EvaluationPayload, EvaluationFailurePayload
from config import settings

logger = logging.getLogger(__name__)


class EvaluationNotifier:
    """Service for notifying evaluation endpoint with retry logic."""
    
    def __init__(self):
        """Initialize evaluation notifier."""
        self.max_retries = settings.MAX_RETRIES
        self.initial_delay = settings.INITIAL_RETRY_DELAY
        self.max_delay = settings.MAX_RETRY_DELAY
        logger.info("Evaluation notifier initialized")
    
    async def notify(
        self,
        evaluation_url: str,
        email: str,
        task: str,
        round: int,
        nonce: str,
        repo_url: str,
        commit_sha: str,
        pages_url: str
    ) -> bool:
        """
        Notify evaluation URL with deployment details.
        
        Implements exponential backoff retry logic.
        Returns True if successful, False otherwise.
        """
        payload = EvaluationPayload(
            email=email,
            task=task,
            round=round,
            nonce=nonce,
            repo_url=repo_url,
            commit_sha=commit_sha,
            pages_url=pages_url
        )
        
        return await self._send_with_retry(
            evaluation_url,
            payload.dict(),
            task
        )
    
    async def notify_failure(
        self,
        evaluation_url: str,
        email: str,
        task: str,
        round: int,
        nonce: str,
        error: str
    ) -> bool:
        """
        Notify evaluation URL of build failure.
        
        Returns True if successful, False otherwise.
        """
        payload = EvaluationFailurePayload(
            email=email,
            task=task,
            round=round,
            nonce=nonce,
            status="failure",
            error=error
        )
        
        return await self._send_with_retry(
            evaluation_url,
            payload.dict(),
            task
        )
    
    async def _send_with_retry(
        self,
        url: str,
        payload: dict,
        task_id: str
    ) -> bool:
        """
        Send POST request with exponential backoff retry logic.
        
        Args:
            url: Target URL
            payload: JSON payload to send
            task_id: Task identifier for logging
        
        Returns:
            True if request succeeded, False if all retries exhausted
        """
        delay = self.initial_delay
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"[{task_id}] Attempting to notify evaluation URL (attempt {attempt + 1}/{self.max_retries})")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    # Check for successful response
                    if 200 <= response.status_code < 300:
                        logger.info(f"[{task_id}] Evaluation notification successful (HTTP {response.status_code})")
                        return True
                    
                    # Log non-successful response
                    logger.warning(
                        f"[{task_id}] Evaluation notification returned HTTP {response.status_code}: {response.text[:200]}"
                    )
                    
                    # If it's a client error (4xx), don't retry
                    if 400 <= response.status_code < 500:
                        logger.error(f"[{task_id}] Client error, not retrying")
                        return False
                
            except httpx.TimeoutException:
                logger.warning(f"[{task_id}] Request timeout on attempt {attempt + 1}")
            
            except httpx.RequestError as e:
                logger.warning(f"[{task_id}] Request error on attempt {attempt + 1}: {str(e)}")
            
            except Exception as e:
                logger.error(f"[{task_id}] Unexpected error on attempt {attempt + 1}: {str(e)}")
            
            # Don't sleep after the last attempt
            if attempt < self.max_retries - 1:
                logger.info(f"[{task_id}] Waiting {delay} seconds before retry...")
                await asyncio.sleep(delay)
                
                # Exponential backoff with jitter
                delay = min(delay * 2, self.max_delay)
                # Add small random jitter (±10%)
                import random
                jitter = delay * 0.1 * (random.random() * 2 - 1)
                delay = delay + jitter
        
        logger.error(f"[{task_id}] Failed to notify evaluation URL after {self.max_retries} attempts")
        return False