from .topics_model import BEST_EFFORT_QOS, LATCHED_QOS, TopicSpec

# --- sim commands (physical units, from naveol_sim or test scripts) ---
SIM_CMD_RUDDER_ANGLE = TopicSpec(name="/sim/cmd/rudder_angle", qos=BEST_EFFORT_QOS)
SIM_CMD_SAIL_ANGLE = TopicSpec(name="/sim/cmd/sail_angle", qos=BEST_EFFORT_QOS)
SIM_CMD_ENGINE = TopicSpec(name="/sim/cmd/engine", qos=BEST_EFFORT_QOS)

# --- sim outputs (simple_sim publishes here, naveol_sim consumes) ---
SIM_POSE = TopicSpec(name="/sim/boat/pose", qos=BEST_EFFORT_QOS)
SIM_VELOCITY = TopicSpec(name="/sim/boat/velocity", qos=BEST_EFFORT_QOS)
SIM_SAIL_ANGLE_STATE = TopicSpec(name="/sim/boat/sail_angle", qos=BEST_EFFORT_QOS)

# --- scenario generator / detection pipeline ---
SIM_TRACKS = TopicSpec(name="/sim/tracks", qos=BEST_EFFORT_QOS)
SIM_DETECTIONS = TopicSpec(name="/sim/detections", qos=BEST_EFFORT_QOS)
SIM_TRACKS_MARKERS = TopicSpec(name="/sim/tracks/markers", qos=BEST_EFFORT_QOS)

# --- costmap ---
COSTMAP_STATIC = TopicSpec(name="/map/costmap_static", qos=LATCHED_QOS)
