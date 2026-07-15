# Noisy sensor-like observation of an object.
# Uses PoseWithCovariance for position + uncertainty (only position block of 6x6 used).
# Stamp is in the DetectionArray header, not repeated here.

uint32 id                                         # detection identifier
geometry_msgs/PoseWithCovariance pose             # position + covariance (ENU frame)
uint8 type                                        # classified object type (same enum as Track)
