from __future__ import annotations

from typing import Literal

from n3_common.params.pydantic_params_base import PydanticParamsBase
from pydantic import BaseModel, Field
from rclpy.node import Node

VariationMode = Literal["none", "sinusoidal", "turbulent"]


class AnemoSimModel(BaseModel):
    # --- Base (mean) true wind ---
    twd_deg: float = Field(
        default=0.0, description="True wind direction (mean) in degrees CW from North."
    )
    tws_ms: float = Field(
        default=5.0, ge=0.0, description="True wind speed (mean) in m/s."
    )
    publish_rate_hz: float = Field(
        default=10.0, ge=1.0, le=100.0, description="Publish rate in Hz."
    )

    # --- Wind direction variation ---
    twd_variation_mode: VariationMode = Field(
        default="none",
        description="Direction variation mode: none, sinusoidal or turbulent (Ornstein-Uhlenbeck).",
    )
    twd_sinus_period_s: float = Field(
        default=60.0,
        gt=0.0,
        description="Sinusoidal direction variation period in seconds.",
    )
    twd_sinus_amplitude_deg: float = Field(
        default=10.0,
        ge=0.0,
        description="Sinusoidal direction variation amplitude in degrees (peak).",
    )
    twd_turb_std_deg: float = Field(
        default=8.0,
        ge=0.0,
        description="Turbulent direction: stationary std deviation in degrees (1-sigma).",
    )
    twd_turb_time_constant_s: float = Field(
        default=30.0,
        gt=0.0,
        description="Turbulent direction: correlation time in seconds (higher = slower drift).",
    )

    # --- Wind speed variation ---
    tws_variation_mode: VariationMode = Field(
        default="none",
        description="Speed variation mode: none, sinusoidal or turbulent (Ornstein-Uhlenbeck).",
    )
    tws_sinus_period_s: float = Field(
        default=60.0, gt=0.0, description="Sinusoidal speed variation period in seconds."
    )
    tws_sinus_amplitude_ms: float = Field(
        default=1.5,
        ge=0.0,
        description="Sinusoidal speed variation amplitude in m/s (peak).",
    )
    tws_turb_std_ms: float = Field(
        default=1.2,
        ge=0.0,
        description="Turbulent speed: stationary std deviation in m/s (1-sigma).",
    )
    tws_turb_time_constant_s: float = Field(
        default=15.0,
        gt=0.0,
        description="Turbulent speed: correlation time in seconds (higher = slower drift).",
    )

    # --- Cross-channel turbulence coupling ---
    wind_turb_correlation: float = Field(
        default=0.3,
        ge=-1.0,
        le=1.0,
        description="Correlation between direction and speed turbulent noise, in [-1, 1].",
    )

    # --- Reproducibility ---
    random_seed: int = Field(
        default=0,
        ge=0,
        description="RNG seed for turbulent noise. 0 = non-reproducible (time-based).",
    )


class AnemoSimParams(PydanticParamsBase[AnemoSimModel]):
    model_class = AnemoSimModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)
