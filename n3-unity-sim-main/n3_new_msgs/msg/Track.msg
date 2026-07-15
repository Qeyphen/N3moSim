# A moving object: ground truth from scenario_generator or estimated state from tracker.
# Stamp is in the TrackArray header, not repeated here.

uint8 UNKNOWN=0
uint8 SAILBOAT=1
uint8 MOTORBOAT=2
uint8 JETSKI=3
uint8 KAYAK=4
uint8 PADDLEBOARD=5
uint8 SWIMMER=6
uint8 DINGHY=7
uint8 FISHING_BOAT=8
uint8 FERRY=9
uint8 CARGO=10
uint8 BUOY=11
uint8 DEBRIS=12
uint8 WINDSURF=13
uint8 KITESURF=14
uint8 PEDALO=15

uint32 id                       # unique track identifier
geometry_msgs/Pose pose         # position and orientation (ENU frame)
geometry_msgs/Twist twist       # linear and angular velocity
uint8 type                      # track type (see constants above)
