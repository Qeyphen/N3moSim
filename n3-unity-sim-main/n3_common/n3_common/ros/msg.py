import geographic_msgs.msg as _geo
import geometry_msgs.msg as _geom
import n3_new_msgs.msg as _n3
import n3_new_msgs.srv as _n3_srv
import nav_msgs.msg as _nav
import sensor_msgs.msg as _sensor
import std_msgs.msg as _std
import visualization_msgs.msg as _viz

Header = _std.Header  # timestamp + frame_id
Float = _std.Float32
Int = _std.Int32
Bool = _std.Bool

Point = _geom.Point  # x,y,z
PointStamped = _geom.PointStamped  # Point + Header
Pose = _geom.Pose  # Point + Quaternion
PoseArray = _geom.PoseArray  # sequence of Pose
PoseStamped = _geom.PoseStamped  # Pose + Header
PoseWithCovarianceStamped = _geom.PoseWithCovarianceStamped  # PoseStamped + Covariance

Quaternion = _geom.Quaternion  # x,y,z,w
Transform = _geom.Transform  # translation (Vector3) + rotation (Quaternion)
TransformStamped = _geom.TransformStamped

GeoPoint = _geo.GeoPoint  # lon, lat, alt
GeoPointStamped = _geo.GeoPointStamped  # GeoPoint + Header
GeoPose = _geo.GeoPose  # GeoPoint + Quaternion
GeoPoseStamped = _geo.GeoPoseStamped  # GeoPose + Header

Waypoint = _n3.Waypoint
WaypointList = _n3.WaypointList

# Domain messages (n3_new_msgs)
Anemometer = _n3.Anemometer
Maneuver = _n3.Maneuver
MissionState = _n3.MissionState
PilotCommand = _n3.PilotCommand
PilotStatus = _n3.PilotStatus
PlanState = _n3.PlanState
ResetPID = _n3.ResetPID
SailAngle = _n3.SailAngle
Velocity = _n3.Velocity
Wind = _n3.Wind

# Simulation / detection messages (n3_new_msgs)
Track = _n3.Track
TrackArray = _n3.TrackArray
Detection = _n3.Detection
DetectionArray = _n3.DetectionArray

# Services (n3_new_msgs)
ScenarioCommand = _n3_srv.ScenarioCommand

# Pas sur qu'on utilise ceux ci # TODO-after supprimer ceux qu'on utilise pas

Twist = _geom.Twist  # linear (Vector3) + angular (Vector3)
TwistStamped = _geom.TwistStamped
Vector3 = _geom.Vector3

NavSatFix = _sensor.NavSatFix
NavSatStatus = _sensor.NavSatStatus
ImuData = _sensor.Imu
JointState = _sensor.JointState

Path = _nav.Path  # sequence of PoseStamped + Header
OccupancyGrid = _nav.OccupancyGrid  # 2D costmap grid
MapMetaData = _nav.MapMetaData  # OccupancyGrid header (size, resolution, origin)

# Visualization messages (visualization_msgs)
Marker = _viz.Marker
MarkerArray = _viz.MarkerArray
