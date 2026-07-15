from __future__ import annotations

from n3_common.params.pydantic_params_base import PydanticParamsBase
from pydantic import BaseModel, Field
from rclpy.node import Node


class SimpleSimModel(BaseModel):
    # --- time ---
    sim_rate_hz: float = Field(
        default=50.0, ge=10.0, le=200.0, description="Physics step rate in Hz."
    )

    # --- initial state ---
    init_heading_deg: float = Field(
        default=0.0, description="Initial heading in degrees CW from North (maritime)."
    )

    # --- hull ---
    mass_kg: float = Field(default=80.0, ge=1.0, description="Boat mass in kg.")
    inertia_z_kg_m2: float = Field(
        default=60.0, ge=1.0, description="Yaw moment of inertia in kg.m²."
    )
    hull_drag_coeff: float = Field(
        default=20.0, ge=0.0, description="Hull drag coefficient (N·s²/m²)."
    )
    yaw_damping: float = Field(
        default=200.0, ge=0.0, description="Yaw damping coefficient (N·m·s/rad)."
    )

    # --- sail ---
    sail_area_m2: float = Field(default=6.0, ge=0.0, description="Sail area in m².")
    sail_lift_coeff: float = Field(
        default=1.2, ge=0.0, description="Sail lift coefficient at optimal AoA."
    )
    sail_drag_coeff: float = Field(
        default=0.1, ge=0.0, description="Sail parasitic drag coefficient."
    )

    # --- rudder ---
    rudder_area_m2: float = Field(
        default=0.05, ge=0.0, description="Rudder area in m²."
    )
    rudder_lift_coeff: float = Field(
        default=1.0, ge=0.0, description="Rudder lift coefficient."
    )
    rudder_arm_m: float = Field(
        default=1.5, ge=0.0, description="Distance from rudder to center of mass."
    )

    # --- engine ---
    engine_max_thrust_n: float = Field(
        default=50.0, ge=0.0, description="Engine max thrust in Newtons at 100%."
    )


class SimpleSimParams(PydanticParamsBase[SimpleSimModel]):
    model_class = SimpleSimModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)
