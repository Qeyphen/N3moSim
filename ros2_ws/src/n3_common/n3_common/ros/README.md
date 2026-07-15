# List of ROS msgs we decided to use for N3mo

* in order to differentiate ros msgs structures and pydantic models we gather here all ros msgs used in n3mo
* it also help to select which ros msgs we use among all of them

## usage

```
import n3_common.ros as ros
ros.Pose
ros.GeoPose
ros.PoseStamped
ros.Point
ros.Wind
ros.SailAngle
...
```

## and for pydantic models

```
import n3_common.models as pyd
pyd.Pose2d
pyd.GeoPose2d
pyd.Wind
pyd.SailAngle
...
```

## and for pydantic models
