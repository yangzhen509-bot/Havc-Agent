"""车辆信号总线适配器(无闭源 SDK)。

可插拔适配层:场景输入可与总线快照合并,便于后续接 SocketCAN / SOA / 车云。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from ..schemas import CabinContext


@dataclass
class VehicleSnapshot:
    """一帧车辆状态快照(可来自 Mock / CAN / 云端)。"""

    ambient_temp: Optional[float] = None
    cabin_temp: Optional[float] = None
    humidity: Optional[float] = None
    speed: Optional[float] = None
    soc: Optional[float] = None
    windshield_glass_temp: Optional[float] = None
    windshield_air_temp: Optional[float] = None
    rain_level: Optional[str] = None
    source: str = "mock"
    extras: dict = field(default_factory=dict)


class VehicleSignalBus(Protocol):
    """车辆信号读取协议——实现方自行对接总线,本仓库只保留 Mock。"""

    def read(self) -> VehicleSnapshot: ...


class MockVehicleBus:
    """从当前 CabinContext 回显的 Mock 总线(零硬件可跑通)。"""

    def __init__(self, cabin: Optional[CabinContext] = None):
        self._cabin = cabin

    def bind(self, cabin: CabinContext) -> "MockVehicleBus":
        self._cabin = cabin
        return self

    def read(self) -> VehicleSnapshot:
        c = self._cabin
        if c is None:
            return VehicleSnapshot(source="mock-empty")
        return VehicleSnapshot(
            ambient_temp=c.ambient_temp,
            cabin_temp=c.cabin_temp,
            humidity=c.humidity,
            speed=c.speed,
            soc=c.soc,
            windshield_glass_temp=c.windshield_glass_temp,
            windshield_air_temp=c.windshield_air_temp,
            rain_level=c.rain_level,
            source="mock",
        )


def merge_snapshot_into_cabin(cabin: CabinContext, snap: VehicleSnapshot) -> CabinContext:
    """把总线快照中非空字段覆盖到 cabin(返回新模型,不原地改)。"""
    data = cabin.model_dump()
    mapping = {
        "ambient_temp": snap.ambient_temp,
        "cabin_temp": snap.cabin_temp,
        "humidity": snap.humidity,
        "speed": snap.speed,
        "soc": snap.soc,
        "windshield_glass_temp": snap.windshield_glass_temp,
        "windshield_air_temp": snap.windshield_air_temp,
        "rain_level": snap.rain_level,
    }
    for key, val in mapping.items():
        if val is not None and key in data:
            data[key] = val
    return CabinContext(**data)


def build_vehicle_bus(mode: str = "mock", cabin: Optional[CabinContext] = None) -> VehicleSignalBus:
    """工厂:目前仅 mock;预留 can/soa 扩展点(自行实现类并在此注册)。"""
    mode = (mode or "mock").lower()
    if mode == "mock":
        return MockVehicleBus(cabin)
    raise ValueError(
        f"未知车辆总线模式 {mode!r}。当前仅内置 mock;"
        "请在 vehicle/adapter.py 自行实现 CAN/SOA 并在此注册。"
    )
