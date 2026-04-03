using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;

public class ROSController : MonoBehaviour
{
    [Header("ROS2 Settings")]
    public string topic    = "/cmd_vel";
    public string objectId = "";

    [Header("Movement Settings")]
    public float moveSpeed = 10f;
    public float turnSpeed = 50f;
    public float maxSpeed  = 20f;

    private float linearX  = 0f;
    private float angularZ = 0f;
    private Rigidbody rb;
    private ROSConnection ros;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        if (rb == null)
            rb = gameObject.AddComponent<Rigidbody>();

        rb.isKinematic    = false;
        rb.useGravity     = false;
        rb.mass           = 1f;
        rb.linearDamping  = 0.5f;
        rb.angularDamping = 1f;

        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<TwistMsg>(topic, OnROSCommand);
        Debug.Log($"[ROSController] '{objectId}' subscribed to: {topic}");
    }

    void OnROSCommand(TwistMsg msg)
    {
        linearX  = (float)msg.linear.x;
        angularZ = (float)msg.angular.z;
        Debug.Log($"[ROSController] {objectId} ← " +
                  $"linear.x={linearX:F2} angular.z={angularZ:F2}");
    }

    void FixedUpdate()
    {
        ApplyMovement();
    }

    void ApplyMovement()
    {
        if (rb == null) return;

        // Direct velocity control
        Vector3 targetVelocity = transform.forward * linearX * moveSpeed;
        rb.linearVelocity = Vector3.Lerp(
            rb.linearVelocity,
            targetVelocity,
            Time.fixedDeltaTime * 5f
        );

        // Rotation
        if (Mathf.Abs(angularZ) > 0.01f)
        {
            float yaw = angularZ * turnSpeed * Time.fixedDeltaTime;
            rb.MoveRotation(rb.rotation * Quaternion.Euler(0, yaw, 0));
        }
    }

    public void SetVelocity(float forward, float turn)
    {
        linearX  = forward;
        angularZ = turn;
    }
}