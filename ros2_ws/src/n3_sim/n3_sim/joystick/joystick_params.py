from __future__ import annotations

from n3_common.params.pydantic_params_base import PydanticParamsBase
from pydantic import BaseModel, Field
from rclpy.node import Node


class JoystickModel(BaseModel):
    # General
    mode: str = Field(
        default="guidance",
        description="'guidance' (publish targets) or 'direct' (publish pilot command).",
    )
    publish_hz: float = Field(default=10.0, gt=0.0, description="Output publish rate.")
    deadzone: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Axis values below this are zeroed."
    )
    btn_debounce_s: float = Field(
        default=0.2, ge=0.0, description="Button debounce delay in seconds."
    )

    # -- Mode / toggle buttons --
    sail_boat_ref_btn: int = Field(
        default=-1, description="Button to set sail reference to BOAT (-1=disabled)."
    )
    sail_wind_ref_btn: int = Field(
        default=-1, description="Button to set sail reference to WIND (-1=disabled)."
    )
    guidance_mode_btn: int = Field(
        default=-1, description="Button to switch to guidance mode (-1=disabled)."
    )
    direct_mode_btn: int = Field(
        default=-1, description="Button to switch to direct mode (-1=disabled)."
    )

    # -- Guidance mode: axes → rate-of-change on targets --
    # COG
    cog_axis: int = Field(default=0, ge=0, description="Joy axis index for COG rate.")
    cog_rate_deg_s: float = Field(
        default=-90.0, description="Axis ±1 → ±rate deg/s on COG."
    )
    cog_plus_btn: int = Field(
        default=-1, description="Button index for COG +step (-1=disabled)."
    )
    cog_minus_btn: int = Field(
        default=-1, description="Button index for COG -step (-1=disabled)."
    )
    cog_step_deg: float = Field(
        default=10.0, description="COG step per button press (deg)."
    )

    # SOG
    sog_axis: int = Field(default=6, ge=0, description="Joy axis index for SOG rate.")
    sog_rate_kts_s: float = Field(
        default=1.0, description="Axis ±1 → ±rate kts/s on SOG."
    )
    sog_max_kts: float = Field(default=5.0, gt=0.0, description="Max SOG clamp (kts).")
    sog_plus_btn: int = Field(
        default=-1, description="Button index for SOG +step (-1=disabled)."
    )
    sog_minus_btn: int = Field(
        default=-1, description="Button index for SOG -step (-1=disabled)."
    )
    sog_step_kts: float = Field(
        default=0.5, description="SOG step per button press (kts)."
    )

    # Sail angle
    sail_axis: int = Field(
        default=2, ge=0, description="Joy axis index for sail angle rate."
    )
    sail_rate_deg_s: float = Field(
        default=-45.0, description="Axis ±1 → ±rate deg/s on sail angle."
    )
    sail_plus_btn: int = Field(
        default=-1, description="Button index for sail +step (-1=disabled)."
    )
    sail_minus_btn: int = Field(
        default=-1, description="Button index for sail -step (-1=disabled)."
    )
    sail_step_deg: float = Field(
        default=5.0, description="Sail angle step per button press (deg)."
    )

    sail_reference: int = Field(
        default=0, ge=0, le=1, description="0 = BOAT_REF, 1 = WIND_REF."
    )

    # -- Direct mode: axes → pilot command --
    rudder_axis: int = Field(default=0, ge=0, description="Joy axis index for rudder.")
    rudder_scale_pct: float = Field(
        default=100.0, description="Axis ±1 maps to ±scale %."
    )
    engine_axis: int = Field(default=1, ge=0, description="Joy axis index for engine.")
    engine_scale_pct: float = Field(
        default=100.0, gt=0.0, description="Axis 0→1 maps to 0→scale %."
    )
    mast_axis: int = Field(
        default=3, ge=0, description="Joy axis index for mast speed."
    )
    mast_scale_pct: float = Field(
        default=100.0, description="Axis ±1 maps to ±scale %."
    )


class JoystickParams(PydanticParamsBase[JoystickModel]):
    model_class = JoystickModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)
