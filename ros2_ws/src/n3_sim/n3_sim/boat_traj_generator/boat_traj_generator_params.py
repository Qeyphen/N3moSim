from __future__ import annotations

from typing import Literal

from n3_common.params.pydantic_params_base import PydanticParamsBase
from pydantic import BaseModel, Field
from rclpy.node import Node

TrajectoryType = Literal["lawnmower", "circle", "random_walk"]


class BoatTrajGeneratorModel(BaseModel):
    speed_kts: float = Field(
        default=3.0, ge=0.1, description="Boat speed along trajectory in knots."
    )
    margin_m: float = Field(
        default=20.0,
        ge=0.0,
        description="Safety margin from costmap obstacles in meters.",
    )
    publish_rate_hz: float = Field(
        default=10.0, ge=1.0, le=100.0, description="Pose publication rate in Hz."
    )
    trajectory_type: TrajectoryType = Field(
        default="lawnmower",
        description="Trajectory pattern: lawnmower, circle, or random_walk.",
    )
    random_seed: int = Field(
        default=0,
        ge=0,
        description="RNG seed for random_walk (0 = non-reproducible).",
    )
    area_center_x_m: float = Field(
        default=0.0,
        description="Center X (ENU meters) of the trajectory generation area.",
    )
    area_center_y_m: float = Field(
        default=0.0,
        description="Center Y (ENU meters) of the trajectory generation area.",
    )
    area_extent_x_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Full X extent (m) of the trajectory area. 0 = use full costmap.",
    )
    area_extent_y_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Full Y extent (m) of the trajectory area. 0 = use full costmap.",
    )
    circle_radius_m: float = Field(
        default=0.0,
        ge=0.0,
        description="Radius (m) for circle trajectory. 0 = derive from area bounds.",
    )


class BoatTrajGeneratorParams(PydanticParamsBase[BoatTrajGeneratorModel]):
    model_class = BoatTrajGeneratorModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)
