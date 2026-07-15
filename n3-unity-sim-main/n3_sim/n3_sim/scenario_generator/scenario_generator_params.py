from __future__ import annotations

from typing import Literal

from n3_common.params.pydantic_params_base import PydanticParamsBase
from pydantic import BaseModel, Field
from rclpy.node import Node

AreaType = Literal["lake", "coastal", "harbor", "open_sea"]


class ScenarioGeneratorModel(BaseModel):
    # --- Playback ---
    scenario_file: str = Field(
        default="",
        description="Path to scenario YAML to load and play. Empty = wait for service call.",
    )
    publish_rate_hz: float = Field(
        default=10.0, ge=1.0, le=100.0, description="Track publication rate in Hz."
    )
    loop: bool = Field(
        default=True, description="Loop scenario when duration is reached."
    )

    # --- Generation (used by /sim/generate_scenario service) ---
    gen_output_file: str = Field(
        default="/tmp/scenario_generated.yaml",
        description="Path to write the generated YAML.",
    )
    gen_duration_s: float = Field(
        default=600.0, gt=0.0, description="Scenario duration in seconds."
    )
    gen_track_count: int = Field(
        default=0, ge=0, description="Number of tracks (0 = use density)."
    )
    gen_density: float = Field(
        default=5.0, ge=0.0, description="Tracks per km², used if track_count == 0."
    )
    gen_area_type: AreaType = Field(
        default="lake", description="Preset: lake, coastal, harbor, open_sea."
    )
    gen_autostart: bool = Field(
        default=True, description="Load and start scenario after generation."
    )
    gen_min_speed_kts: float = Field(
        default=0.0, ge=0.0, description="Min track speed (0 = type default)."
    )
    gen_max_speed_kts: float = Field(
        default=0.0, ge=0.0, description="Max track speed (0 = type default)."
    )
    gen_min_waypoints: int = Field(
        default=2, ge=2, description="Min waypoints per track."
    )
    gen_max_waypoints: int = Field(
        default=6, ge=2, description="Max waypoints per track."
    )
    gen_spawn_spread_s: float = Field(
        default=60.0,
        ge=0.0,
        description="Tracks spawn randomly within [0, spawn_spread_s].",
    )
    gen_margin_m: float = Field(
        default=10.0,
        ge=0.0,
        description="Safety margin from costmap obstacles in meters.",
    )
    gen_random_seed: int = Field(
        default=0, ge=0, description="RNG seed (0 = non-reproducible)."
    )


class ScenarioGeneratorParams(PydanticParamsBase[ScenarioGeneratorModel]):
    model_class = ScenarioGeneratorModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)
