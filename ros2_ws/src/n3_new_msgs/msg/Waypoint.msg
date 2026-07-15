# forced_tack enum values
int8 TACK_NONE       =  0
int8 TACK_PORT       =  1
int8 TACK_STARBOARD  = -1

float64 lat_deg
float64 lon_deg
float64 heading_deg         # approach heading, CW from North (used as hint by guidance)
float64 acceptance_radius_m # distance at which waypoint is considered reached
string label                # human-readable name (race mark, harbour entrance, ...)
int8 forced_tack            # forced_tack: tack constraint on approach (Foxglove will display constant names)



