from .topics_model import (
    BEST_EFFORT_QOS,
    LATCHED_QOS,
    RELIABLE_QOS,
    TopicSpec,
)

# --- map ---
MAP_ORIGIN = TopicSpec(name="/navigation/map/origin", qos=LATCHED_QOS)

# --- drivers / sensors ---
GPS_FIX = TopicSpec(name="/drivers/gps/fix", qos=BEST_EFFORT_QOS)
GPS_VELOCITY = TopicSpec(name="/drivers/gps/velocity", qos=BEST_EFFORT_QOS)
ANEMO_DATA = TopicSpec(name="/drivers/anemo/data", qos=BEST_EFFORT_QOS)
IMU_DATA = TopicSpec(name="/drivers/imu/data", qos=BEST_EFFORT_QOS)
PILOT_STATUS = TopicSpec(name="/drivers/naveol/pilot_status", qos=BEST_EFFORT_QOS)
PILOT_COMMAND = TopicSpec(name="/drivers/naveol/pilot_command", qos=RELIABLE_QOS)

# --- boat state ---
BOAT_POSE = TopicSpec(name="/boat/pose", qos=BEST_EFFORT_QOS)
BOAT_VELOCITY = TopicSpec(name="/boat/velocity", qos=BEST_EFFORT_QOS)
BOAT_SAIL_ANGLE = TopicSpec(name="/boat/sail_angle", qos=BEST_EFFORT_QOS)

# --- wind ---
WIND_APPARENT = TopicSpec(name="/wind/apparent", qos=BEST_EFFORT_QOS)
WIND_TRUE = TopicSpec(name="/wind/true", qos=BEST_EFFORT_QOS)

# --- guidance ---
TARGET_VELOCITY = TopicSpec(name="/guidance/target/velocity", qos=RELIABLE_QOS)
TARGET_SAIL_ANGLE = TopicSpec(name="/guidance/target/sail_angle", qos=RELIABLE_QOS)
MANEUVER = TopicSpec(name="/guidance/maneuver", qos=LATCHED_QOS)
RESET_PID = TopicSpec(name="/guidance/reset_pid", qos=RELIABLE_QOS)

# --- mission ---
MISSION_STATE = TopicSpec(name="/mission/state", qos=LATCHED_QOS)
MISSION_GOALS = TopicSpec(name="/mission/goals", qos=LATCHED_QOS)

# --- plan ---
PLAN_WAYPOINTS = TopicSpec(name="/plan/waypoints", qos=LATCHED_QOS)
CURRENT_WAYPOINT = TopicSpec(name="/plan/waypoint", qos=LATCHED_QOS)
PLAN_STATE = TopicSpec(name="/plan/state", qos=LATCHED_QOS)

# --- actuators ---
# RUDDER_ANGLE = TopicSpec(name="/actuators/rudder_angle", qos=RELIABLE_QOS)
# SAIL_ANGLE = TopicSpec(name="/actuators/sail_angle", qos=RELIABLE_QOS)
