from __future__ import annotations

from pyproj import Transformer
from pyproj.enums import TransformDirection

import n3_common.models as pyd
import n3_common.ros as ros


class LocalCartesianProjector:
    """
    Project geodetic WGS84 coordinates into a local Cartesian ENU frame.

    Assumptions:
    - input coordinates are WGS84 geodetic coordinates
    - input date in seconds since epoch (useful later to deal with a sliding local map for large distance travel)
    - output frame is local ENU:
        - x = East
        - y = North
        - z = Up

    The local ENU frame is centered on the chosen init origin (origin_lat_deg, origin_lon_deg).
    """

    def __init__(
        self,
        origin_lat_deg: float,
        origin_lon_deg: float,
        origin_alt: float = 0.0,
        origin_date: float = 0.0,
    ) -> None:
        self._origin_lat_deg = origin_lat_deg
        self._origin_lon_deg = origin_lon_deg
        self._origin_alt = origin_alt
        self._origin_date = origin_date

        pipeline = (
            f"+proj=pipeline "
            f"+step +proj=cart +ellps=WGS84 "
            f"+step +proj=topocentric +ellps=WGS84 "
            f"+lon_0={origin_lon_deg} +lat_0={origin_lat_deg} +h_0={origin_alt}"
        )
        self._transformer = Transformer.from_pipeline(pipeline)

    @classmethod
    def from_ros_geopoint(
        cls, geopoint: ros.GeoPointStamped
    ) -> LocalCartesianProjector:
        return cls(
            origin_lat_deg=geopoint.position.latitude,
            origin_lon_deg=geopoint.position.longitude,
            origin_alt=geopoint.position.altitude,
            origin_date=float(geopoint.header.stamp.sec),
        )

    def geopose2d_to_pose2d(
        self,
        geopose2d: pyd.GeoPose2D,
        alt: float = 0.0,
    ) -> pyd.Pose2D:
        # pyproj expects (lon, lat, alt)
        x, y, _ = self._transformer.transform(
            geopose2d.lon_deg,
            geopose2d.lat_deg,
            alt,
        )

        return pyd.Pose2D(
            x=float(x),
            y=float(y),
            yaw=geopose2d.heading.to_enu_angle(),
        )

    def pose2d_to_geopose2d(
        self,
        pose: pyd.Pose2D,
        z: float = 0.0,
    ) -> pyd.GeoPose2D:
        lon_deg, lat_deg, _ = self._transformer.transform(
            pose.x,
            pose.y,
            z,
            direction=TransformDirection.INVERSE,
        )

        return pyd.GeoPose2D(
            lat_deg=float(lat_deg),
            lon_deg=float(lon_deg),
            heading=pose.yaw.to_direction(),
        )

    @property
    def origin_date(self) -> float:
        return self._origin_date
