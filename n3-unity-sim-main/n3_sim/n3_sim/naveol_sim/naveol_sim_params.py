from __future__ import annotations

from n3_common.params.pydantic_params_base import PydanticParamsBase
from pydantic import BaseModel, Field
from rclpy.node import Node


class NaveolSimModel(BaseModel):
    origin_lat_deg: float = Field(
        default=47.2184, description="WGS84 origin latitude in degrees."
    )
    origin_lon_deg: float = Field(
        default=-1.5536, description="WGS84 origin longitude in degrees."
    )
    origin_alt_m: float = Field(
        default=0.0, description="WGS84 origin altitude in meters."
    )
    rudder_max_angle_deg: float = Field(
        default=30.0, ge=0.0, description="Max rudder deflection in degrees."
    )
    mast_max_speed_deg_s: float = Field(
        default=17.0, ge=0.0, description="Max mast rotation speed in deg/s."
    )
    publish_rate_hz: float = Field(
        default=20.0, ge=1.0, le=100.0, description="PilotStatus publish rate in Hz."
    )


class NaveolSimParams(PydanticParamsBase[NaveolSimModel]):
    model_class = NaveolSimModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)
