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
    gen_type_names: list[str] = Field(
        default=[],
        description="Explicit vessel types to spawn (empty = use the area preset). "
        "Assigned evenly across tracks so every type appears equally.",
    )
    gen_type_weights: list[float] = Field(
        default=[],
        description="Optional per-type weights matching gen_type_names "
        "(empty = equal). Kept for compatibility; even assignment ignores them.",
    )
    gen_type_counts_json: str = Field(
        default="",
        description="Optional JSON object mapping type name to desired count, "
        'for example {"sailboat": 4, "kayak": 2}. If set, this overrides even assignment.',
    )
    gen_autostart: bool = Field(
        default=True, description="Load and start scenario after generation."
    )
    gen_on_first_costmap: bool = Field(
        default=False,
        description="Auto-generate a scenario the first time a costmap arrives "
        "(no service call needed — for the integrated bringup).",
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
    gen_scene_object_clearance_m: float = Field(
        default=12.0,
        ge=0.0,
        description="Clearance radius from authored scene objects published on /scene/objects.",
    )
    gen_track_separation_m: float = Field(
        default=20.0,
        ge=0.0,
        description="Minimum separation between generated track spawn points.",
    )
    gen_bias_to_ego_view: bool = Field(
        default=True,
        description="Bias a portion of generated traffic to spawn ahead of the ego boat.",
    )
    gen_ego_view_fraction: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Fraction of generated tracks whose initial spawn should be near the ego view cone.",
    )
    gen_ego_view_min_range_m: float = Field(
        default=35.0,
        ge=0.0,
        description="Minimum distance from the ego boat for view-biased traffic spawns.",
    )
    gen_ego_view_max_range_m: float = Field(
        default=120.0,
        ge=1.0,
        description="Maximum distance from the ego boat for view-biased traffic spawns.",
    )
    gen_ego_view_fov_deg: float = Field(
        default=120.0,
        ge=10.0,
        le=180.0,
        description="Forward cone width used when spawning view-biased traffic.",
    )
    gen_random_seed: int = Field(
        default=0, ge=0, description="RNG seed (0 = non-reproducible)."
    )


class ScenarioGeneratorParams(PydanticParamsBase[ScenarioGeneratorModel]):
    model_class = ScenarioGeneratorModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)
