"""结构化回执：失败/成功一律可对前端友好展示（对齐 BrainCloud Feedback）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FeedbackCode(str, Enum):
    OK = "OK"
    REJECTED = "REJECTED"
    PENDING = "PENDING"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    LOCKED = "LOCKED"


@dataclass
class ActionFeedback:
    code: FeedbackCode
    message: str
    request_id: str = ""
    agent_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == FeedbackCode.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "details": dict(self.details),
        }

    @classmethod
    def success(cls, message: str, **kwargs) -> "ActionFeedback":
        return cls(FeedbackCode.OK, message, **kwargs)

    @classmethod
    def pending(cls, message: str, **kwargs) -> "ActionFeedback":
        return cls(FeedbackCode.PENDING, message, **kwargs)

    @classmethod
    def error(cls, message: str, **kwargs) -> "ActionFeedback":
        return cls(FeedbackCode.ERROR, message, **kwargs)
