from __future__ import annotations

import numpy as np
from pyproj import Geod

from n3_common.math_utils.angles import Deg
from n3_common.models.angle_models import Direction
from n3_common.models.pose_models import GeoPose2D, Pose2D

_WGS84 = Geod(ellps="WGS84")


# ---------------------------------------------------------------------------
# Geographic (WGS84) helpers
# ---------------------------------------------------------------------------


def geo_distance_m(a: GeoPose2D, b: GeoPose2D) -> float:
    """Geodetic distance in meters between two geographic positions (WGS84)."""
    _, _, dist = _WGS84.inv(a.lon_deg, a.lat_deg, b.lon_deg, b.lat_deg)
    return float(dist)


def geo_bearing(a: GeoPose2D, b: GeoPose2D) -> Direction:
    """
    Initial bearing from a to b, CW from North (maritime convention).
    This is the direction you must head at point a to reach point b.
    """
    fwd_az, _, _ = _WGS84.inv(a.lon_deg, a.lat_deg, b.lon_deg, b.lat_deg)
    return Direction(deg=Deg(float(fwd_az)))


# ---------------------------------------------------------------------------
# Local ENU (Pose2D) helpers
# ---------------------------------------------------------------------------


def local_distance_m(a: Pose2D, b: Pose2D) -> float:
    """Euclidean distance in meters between two ENU poses."""
    return float(np.hypot(b.x - a.x, b.y - a.y))


def cross_track_error(pos: Pose2D, wp_from: Pose2D, wp_to: Pose2D) -> float:
    """
    Signed cross-track error in meters.

    Positive = pos is to the LEFT of the from→to track (port side).
    Negative = pos is to the RIGHT of the track (starboard side).

    Returns distance from wp_from if the track length is negligible.
    """
    dx = wp_to.x - wp_from.x
    dy = wp_to.y - wp_from.y
    track_len = np.hypot(dx, dy)
    if track_len < 1e-6:
        return float(np.hypot(pos.x - wp_from.x, pos.y - wp_from.y))
    return float(((pos.x - wp_from.x) * dy - (pos.y - wp_from.y) * dx) / track_len)


def along_track_distance(pos: Pose2D, wp_from: Pose2D, wp_to: Pose2D) -> float:
    """
    Distance along the track from wp_from to the projection of pos onto the track.

    Positive = pos is ahead of wp_from (in the direction of wp_to).
    Negative = pos is behind wp_from.
    """
    dx = wp_to.x - wp_from.x
    dy = wp_to.y - wp_from.y
    track_len = np.hypot(dx, dy)
    if track_len < 1e-6:
        return 0.0
    return float(((pos.x - wp_from.x) * dx + (pos.y - wp_from.y) * dy) / track_len)
