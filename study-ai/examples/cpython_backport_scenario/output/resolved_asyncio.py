# CPython asyncio/proactor_events.py conflict during 3.12 backport
# Issue: gh-108278 (Disallow nested event loops on Windows)

import sys
import threading
import warnings

class BaseProactorEventLoop:
    def __init__(self, proactor=None):
        self._proactor = proactor
        self._loop_thread_id = threading.get_ident()
        # [3.12] gh-108278: Prevent race condition and reject nested runs on Windows (GH-108300)
        # (cherry picked from commit 7a82b9e6fa436c0a0c441b8a514dcf50db9011f0)
        self._closed = False
        if sys.platform == "win32" and getattr(self, "_nested_running", False):
            raise RuntimeError("Cannot run nested asyncio event loop on Windows")
        self._asyncgens = set()
