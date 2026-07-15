# Sail angle — used for both current state (/boat/sail_angle) and target (/guidance/cmd/sail_angle")
int8 BOAT_REF = 0   # angle relative to boat centreline from bow to stern
int8 WIND_REF = 1   # angle relative to apparent wind

float32 angle_deg   # sail angle in degrees CCW (positive when sail on Starboard side - right side)
int8 reference      # WIND_REF or BOAT_REF
