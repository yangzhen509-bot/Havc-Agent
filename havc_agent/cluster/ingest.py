"""入站合并：高频场景信号 coalesce（对齐 BrainCloud ingest lease）。"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IngestLease:
    merge_key: str
    fingerprint: str
    last_accepted_at: float = 0.0
    deferred_count: int = 0


@dataclass
class IngestCoalescer:
    """同 merge_key 在 lease 内若指纹未变则跳过；变则接受并刷新租约。"""

    lease_seconds: float = 3.0
    _leases: dict[str, IngestLease] = field(default_factory=dict)

    @staticmethod
    def fingerprint(payload: Any) -> str:
        raw = payload if isinstance(payload, (str, bytes)) else repr(payload)
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        return hashlib.sha1(raw).hexdigest()[:16]

    def should_process(
        self,
        merge_key: str,
        payload: Any,
        now: Optional[float] = None,
    ) -> tuple[bool, str]:
        """返回 (是否处理, 原因)。"""
        now = time.time() if now is None else now
        fp = self.fingerprint(payload)
        lease = self._leases.get(merge_key)
        if lease is None:
            self._leases[merge_key] = IngestLease(merge_key, fp, now)
            return True, "first"
        if fp == lease.fingerprint and (now - lease.last_accepted_at) < self.lease_seconds:
            lease.deferred_count += 1
            return False, f"coalesced(deferred={lease.deferred_count})"
        lease.fingerprint = fp
        lease.last_accepted_at = now
        lease.deferred_count = 0
        return True, "accepted"
