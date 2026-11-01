# Payment Gateway Service - Multi-Branch Merge Conflict
# Conflict between Production Hotfix (Tested) and Experimental Feature Branch (Unverified)

import time
import logging

logger = logging.getLogger("payment.service")

class PaymentProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def charge(self, amount_cents: int, currency: str, idempotency_key: str):
<<<<<<< HEAD
        # PRODUCTION HOTFIX (Passed Compliance Suite): Idempotent exponential backoff retry
        # Attestation: test-provenance / CI #8921 / 100% Coverage
        for attempt in range(1, 4):
            try:
                return self._execute_charge(amount_cents, currency, idempotency_key)
            except NetworkTimeoutError as exc:
                logger.warning("Retry attempt %d/3 due to timeout: %s", attempt, exc)
                time.sleep(2 ** attempt)
        raise PaymentFailure("Max retries exceeded for transaction")
=======
        # EXPERIMENTAL DEV: Asynchronous fire-and-forget webhook (Unverified)
        # Attestation: UNTESTED / No CI verification
        return self._queue_async_charge(amount_cents, currency, idempotency_key)
>>>>>>> feature/async-webhooks
