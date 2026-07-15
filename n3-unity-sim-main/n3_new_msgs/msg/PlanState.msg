# Waypoint tracking state (plan_node → mission_node)
int8 IDLE = 0
int8 TRACKING = 1
int8 ARRIVED = 2    # reached final waypoint of current goal segment

int8 state
