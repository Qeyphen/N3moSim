from __future__ import annotations


class FrameIds:
    # EARTH: global ref frame, only used for GPS coordinates as a label. Not used for TF transformations
    EARTH = "earth"

    # MAP: local cartesian ref frame, fixed to the earth at one gps origin, used for localization and navigation
    MAP = "map"

    # TODO-after if we need precision, Boat point should be at the Metacenter (pitch & roll neutral point) and not at GPS position

    # BENU - Boat East North Up: main ref frame of the boat: centered on GPS position,
    # x-axis oriented toward East, y-axis toward North, z-axis up -> "horizontal frame"
    # MAP -- x, y --> BENU
    BENU = "benu_link"

    # BFLU - Boat Front Left Up: main ref frame of the boat: centered on GPS position,
    # x-axis oriented toward the boat heading, y-axis on port side (left), z-axis up -> "horizontal frame"
    # BENU -- yaw from east --> BFLU
    BFLU = "bflu_link"

    # BOAT = BBPM - Boat Bow Port Mast: take into account roll & pitch
    # centered on the GPS position, x-axis oriented toward the boat bow, y-axis on port side (left), z-axis toward Mast
    # This is the link physically attached to the boat
    # BFLU -- roll, pitch --> BOAT
    BOAT = "boat_link"

    # WIND: true wind frame. Origin at the boat GPS position.
    # Rotates from BENU link with the true wind angle from east
    # x-axis oriented toward the true wind direction, y-axis on left side of wind (with wind in your back), z-axis up
    # BENU -- Angle (East, TrueWindDirection) --> WIND
    WIND = "wind_link"

    # Sensors frames, static relative to the boat (BOAT link)
    GPS = "gps_link"
    ANEMO = "anemo_link"
    IMU = "imu_link"
    CAMERA = "camera_link"
    LIDAR = "lidar_link"

    # Actuator frames, moving on a rotation only move from BASE link
    SAIL = "sail_link"
    RUDDER = "rudder_link"
