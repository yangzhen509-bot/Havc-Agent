"""可观测与评估:日志 + request_id + 会话级修正率指标。"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s rid=%(request_id)s: %(message)s"

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()  # type: ignore[attr-defined]
        return True


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:10]
    _request_id.set(rid)
    return rid


def current_request_id() -> str:
    return _request_id.get()


def get_logger(name: str = "havc_agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        handler.addFilter(_RequestIdFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


@dataclass
class SessionMetrics:
    """代理指标:用户修正率越低,说明推荐越贴合。"""

    recommendations: int = 0
    corrections: int = 0

    def record_recommendation(self) -> None:
        self.recommendations += 1

    def record_correction(self) -> None:
        self.corrections += 1

    @property
    def correction_rate(self) -> float:
        return self.corrections / self.recommendations if self.recommendations else 0.0
