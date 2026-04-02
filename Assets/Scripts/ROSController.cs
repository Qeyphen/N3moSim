using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;

public class ROSController : MonoBehaviour
{
    [Header("ROS2 Settings")]
    public string topic    = "/cmd_vel";
    public string objectId = "";

    [Header("Movement Settings")]
    public float moveSpeed = 5f;
    public float turnSpeed = 90f;
    public float maxSpeed  = 10f;

    private float linearX  = 0f;
    private float angularZ = 0f;
    private Rigidbody rb;
    private ROSConnection ros;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        if (rb == null)
        {
            Debug.LogWarning($"[ROSController] '{objectId}' no Rigidbody! Adding one.");
            rb = gameObject.AddComponent<Rigidbody>();
        }

        rb.isKinematic    = false;
        rb.useGravity     = false;
        rb.linearDamping  = 0.5f;
        rb.angularDamping = 1f;

        // Subscribe to ROS2 topic via ROS TCP Connector
        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<TwistMsg>(topic, OnROSCommand);

        Debug.Log($"[ROSController] '{objectId}' subscribed to: {topic}");
    }

    // Called automatically when ROS2 sends a Twist message
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

        // Forward / backward
        Vector3 force = transform.forward * linearX * moveSpeed;
        rb.AddForce(force, ForceMode.Force);

        // Turn
        rb.AddTorque(Vector3.up * angularZ * turnSpeed, ForceMode.Force);

        // Clamp max speed
        if (rb.linearVelocity.magnitude > maxSpeed)
            rb.linearVelocity = rb.linearVelocity.normalized * maxSpeed;
    }

    // Public: set velocity directly (for testing without ROS2)
    public void SetVelocity(float forward, float turn)
    {
        linearX  = forward;
        angularZ = turn;
    }
}