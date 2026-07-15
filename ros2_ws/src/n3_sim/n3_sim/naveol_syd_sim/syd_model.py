from __future__ import annotations

import n3_common.ros as ros
from pydantic import BaseModel


class SydStatusFrame(BaseModel):
    time: float
    phi_deg: float
    theta_deg: float
    psi_deg: float
    mast_position_pts: float
    north_speed_m_s: float
    east_speed_m_s: float
    down_speed_m_s: float
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    direction_deg: float
    speed_kts: float
    Run: int

    def to_pilot_status(self) -> ros.PilotStatus:
        status = ros.PilotStatus()
        status.position_angle_phi_deg = self.phi_deg
        status.position_angle_theta_deg = self.theta_deg
        status.position_angle_psi_deg = self.psi_deg
        status.position_angle_mast_position_pts = int(self.mast_position_pts)
        status.gps_north_speed_m_s = self.north_speed_m_s
        status.gps_east_speed_m_s = self.east_speed_m_s
        status.gps_down_speed_m_s = self.down_speed_m_s
        status.gps_latitude_deg = self.latitude_deg
        status.gps_longitude_deg = self.longitude_deg
        status.gps_altitude_m = self.altitude_m
        status.radio_tx_mode = 0
        status.radio_tx_1 = 0.0
        status.radio_tx_2 = 0.0
        status.radio_tx_3 = 0.0
        status.radio_tx_4 = 0.0
        status.radio_tx_5 = 0.0
        status.radio_tx_6 = 0.0
        status.radio_tx_7 = 0.0
        status.radio_tx_8 = 0.0
        return status


class SydCommandFrame(BaseModel):
    rudder_position_pct: float = 0.0
    engine_speed_pct: float = 0.0
    bow_thruster_pct: float = 0.0
    mast_speed_pct: float = 0.0

    @classmethod
    def from_pilot_command(cls, msg: ros.PilotCommand) -> SydCommandFrame:
        return cls(
            engine_speed_pct=msg.engine_speed_pct,
            rudder_position_pct=msg.rudder_position_pct,
            bow_thruster_pct=msg.bow_thruster_pct,
            mast_speed_pct=msg.mast_speed_pct,
        )
