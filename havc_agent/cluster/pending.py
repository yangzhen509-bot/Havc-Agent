"""Pending Session：多轮确认（对齐 BrainCloud pending-session）。"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PendingTicket:
    """等待用户确认的一笔推荐。"""

    ticket_id: str
    vehicle_id: str
    seat_id: str
    expect: str  # confirm | reject | adjust
    payload: dict[str, Any]
    reason: str = ""
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 120.0

    def expired(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return now > self.created_at + self.ttl_seconds


class PendingStore:
    """按 vehicle_id 索引的 pending 票证（内存实现，可换 Redis）。"""

    def __init__(self) -> None:
        self._by_vehicle: dict[str, PendingTicket] = {}

    def create(
        self,
        vehicle_id: str,
        seat_id: str,
        payload: dict[str, Any],
        reason: str = "",
        expect: str = "confirm",
        ttl_seconds: float = 120.0,
    ) -> PendingTicket:
        ticket = PendingTicket(
            ticket_id=uuid.uuid4().hex[:12],
            vehicle_id=vehicle_id,
            seat_id=seat_id,
            expect=expect,
            payload=payload,
            reason=reason,
            ttl_seconds=ttl_seconds,
        )
        self._by_vehicle[vehicle_id] = ticket
        return ticket

    def get(self, vehicle_id: str) -> Optional[PendingTicket]:
        t = self._by_vehicle.get(vehicle_id)
        if t is None:
            return None
        if t.expired():
            self._by_vehicle.pop(vehicle_id, None)
            return None
        return t

    def resolve(self, vehicle_id: str, action: str) -> Optional[PendingTicket]:
        """action: confirm | reject。返回被消费的票证。"""
        t = self.get(vehicle_id)
        if t is None:
            return None
        if action not in ("confirm", "reject"):
            return None
        self._by_vehicle.pop(vehicle_id, None)
        return t

    def clear(self, vehicle_id: str) -> None:
        self._by_vehicle.pop(vehicle_id, None)

    def active(self) -> list[PendingTicket]:
        out = []
        for vid in list(self._by_vehicle):
            t = self.get(vid)
            if t:
                out.append(t)
        return out
