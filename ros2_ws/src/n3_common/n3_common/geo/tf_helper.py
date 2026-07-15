from __future__ import annotations

from rclpy.node import Node
from tf2_ros import TransformBroadcaster

import n3_common.models as pyd
import n3_common.ros as ros


class TfHelper:
    def __init__(self, node: Node) -> None:
        self._node = node
        self._broadcaster = TransformBroadcaster(node)

    def publish_tf(
        self,
        parent_frame: str,
        child_frame: str,
        translation: ros.Vector3,
        rotation: ros.Quaternion,
    ) -> None:
        """
        Helper to publish TF
        - parent_frame: parent frame of the transform
        - child_frame: frame of the transform
        - translation: Vector3 from parent origin to child origin expressed in the parent frame
        - rotation: orientation of the child frame relative to the parent frame, expressed as a quaternion
        """
        t = ros.TransformStamped()
        t.header.stamp = self._node.get_clock().now().to_msg()
        t.header.frame_id = parent_frame
        t.child_frame_id = child_frame

        t.transform.translation = translation
        t.transform.rotation = rotation

        self._broadcaster.sendTransform(t)

    def publish_tf_from_yaw_xyz(
        self,
        parent_frame: str,
        child_frame: str,
        yaw: pyd.EnuAngle,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
    ) -> None:
        """
        Helper to publish TF from EnuAngle yaw and optional x, y, z position.
        - yaw: orientation of the child x-axis relative to the parent x-axis (ENU, CCW from East)
        - x, y, z: (optional) position of the child origin in the parent frame (default: 0.0)
        """
        self.publish_tf(
            parent_frame=parent_frame,
            child_frame=child_frame,
            translation=ros.Vector3(x=x, y=y, z=z),
            rotation=yaw.to_quaternion(),
        )

    def publish_tf_from_yaw(
        self,
        parent_frame: str,
        child_frame: str,
        yaw: pyd.EnuAngle,
    ) -> None:
        """
        Helper to publish TF from EnuAngle yaw (no translation).
        - yaw: orientation of the child x-axis relative to the parent x-axis (ENU, CCW from East)
        """
        self.publish_tf_from_yaw_xyz(
            parent_frame=parent_frame,
            child_frame=child_frame,
            yaw=yaw,
        )

    def publish_tf_from_pose2d(
        self,
        parent_frame: str,
        child_frame: str,
        pose2d: pyd.Pose2D,
        z: float = 0.0,
    ) -> None:
        """
        Helper to publish TF from Pose2D.
         - parent_frame: parent frame of the transform
         - child_frame: frame of the transform
        - pose2d: Pose2D representing the child origin position and child x-axis orientation in the parent frame
        - z: (optional) z position of the child origin in the parent frame (default: 0.0)
        """
        self.publish_tf(
            parent_frame=parent_frame,
            child_frame=child_frame,
            translation=pose2d.to_ros_vector3(z=z),
            rotation=pose2d.yaw.to_quaternion(),
        )
