using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;

public class PoseController : MonoBehaviour
{
    [Header("ROS2 Settings")]
    public string topic    = "/pose";
    public string objectId = "";

    [Header("Rotation Fix")]
    [Tooltip("Extra rotation applied after ROS pose — match to prefab forward axis")]
    public Vector3 rotationOffset = Vector3.zero;

    private ROSConnection ros;

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<PoseStampedMsg>(topic, OnPose);
        Debug.Log($"[PoseController] '{objectId}' subscribed to: {topic}");
    }

    void OnPose(PoseStampedMsg msg)
    {
        transform.position = new Vector3(
            (float)msg.pose.position.x,
            (float)msg.pose.position.y,
            (float)msg.pose.position.z
        );

        Quaternion rosRotation = new Quaternion(
            (float)msg.pose.orientation.x,
            (float)msg.pose.orientation.y,
            (float)msg.pose.orientation.z,
            (float)msg.pose.orientation.w
        );

        transform.rotation = rosRotation * Quaternion.Euler(rotationOffset);
    }
}