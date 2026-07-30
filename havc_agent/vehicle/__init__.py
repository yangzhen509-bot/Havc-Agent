"""车辆信号适配层。

提供可插拔的 VehicleSignalBus,PoC 默认走 Mock;后续可换 CAN/SOA 实现,
接口保持不变。
"""
from .adapter import (
    MockVehicleBus,
    VehicleSignalBus,
    VehicleSnapshot,
    build_vehicle_bus,
    merge_snapshot_into_cabin,
)

__all__ = [
    "MockVehicleBus",
    "VehicleSignalBus",
    "VehicleSnapshot",
    "build_vehicle_bus",
    "merge_snapshot_into_cabin",
]

