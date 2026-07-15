using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;

// Publishes the ego boat's pose to /sim/boat/pose (geometry_msgs/PoseStamped) at a fixed rate.
// Put on the ego boat prefab; uses its own transform by default.
// Map-layer convention: Unity x -> ROS x, Unity z -> ROS y, Unity y = 0; forward -> ENU yaw.
public class EgoPosePublisher : MonoBehaviour
{
    [Header("ROS")]
    public string topic   = "/sim/boat/pose";
    public string frameId = "map";
    public float  publishHz = 10f;

    [Header("Ego")]
    [Tooltip("Ego boat transform. Leave empty to use this GameObject's transform.")]
    public Transform ego;

    private ROSConnection ros;
    private float         timer;

    void Start()
    {
        if (ego == null) ego = transform;
        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<PoseStampedMsg>(topic);
        Debug.Log($"[EgoPosePublisher] Publishing ego pose to '{topic}' at {publishHz} Hz.");
    }

    void Update()
    {
        if (ego == null || publishHz <= 0f) return;
        timer += Time.deltaTime;
        float interval = 1f / publishHz;
        if (timer < interval) return;
        timer -= interval;

        Vector3 p = ego.position;
        Vector3 f = ego.forward;
        float yaw = Mathf.Atan2(f.z, f.x);   // ENU yaw (East = 0, North = +y)

        PoseStampedMsg msg = new PoseStampedMsg();
        msg.header.frame_id     = frameId;
        msg.pose.position.x     = p.x;   // Unity x -> ROS x
        msg.pose.position.y     = p.z;   // Unity z -> ROS y
        msg.pose.position.z     = 0.0;
        msg.pose.orientation.x  = 0.0;
        msg.pose.orientation.y  = 0.0;
        msg.pose.orientation.z  = Mathf.Sin(yaw / 2f);
        msg.pose.orientation.w  = Mathf.Cos(yaw / 2f);
        ros.Publish(topic, msg);
    }
}
