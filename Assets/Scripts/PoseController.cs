using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;

public class PoseController : MonoBehaviour
{
    [Header("ROS2 Settings")]
    public string topic    = "/pose";
    public string objectId = "";

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

        // Fix backwards-facing model — rotate 180° on Y axis
        transform.rotation = rosRotation * Quaternion.Euler(0, 180, 0);
    }
}