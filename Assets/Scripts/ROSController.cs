using UnityEngine;

public class ROSController : MonoBehaviour
{
    [Header("ROS2 Settings")]
    public string topic    = "/cmd_vel";
    public string objectId = "";

    [Header("Movement Settings")]
    public float moveSpeed = 5f;
    public float turnSpeed = 90f;
    public float maxSpeed  = 10f;

    // Velocity inputs — set by ROS2 or keyboard fallback
    private float linearX  = 0f;
    private float angularZ = 0f;

    private Rigidbody rb;

    void Start()
    {
        rb = GetComponent<Rigidbody>();

        if (rb != null)
        {
            rb.isKinematic    = false;
            rb.useGravity     = false;
            rb.linearDamping  = 0.5f;
            rb.angularDamping = 1f;
        }
        else
        {
            Debug.LogWarning($"[ROSController] '{objectId}' has no Rigidbody! Adding one.");
            rb                = gameObject.AddComponent<Rigidbody>();
            rb.isKinematic    = false;
            rb.useGravity     = false;
            rb.linearDamping  = 0.5f;
            rb.angularDamping = 1f;
        }

        Debug.Log($"[ROSController] '{objectId}' ready. Topic: {topic}");
    }

    void FixedUpdate()
    {
        // Reset inputs each frame
        // ROS2 will call SetVelocity() every frame to override
        // Until ROS2 connected — nothing moves, no errors!
        ApplyMovement();
    }

    // Called by ROS2 TCP bridge when Twist message arrives
    public void SetVelocity(float forward, float turn)
    {
        linearX  = forward;
        angularZ = turn;
    }

    void ApplyMovement()
    {
        if (rb == null) return;

        // Forward / backward force
        Vector3 force = transform.forward * linearX * moveSpeed;
        rb.AddForce(force, ForceMode.Force);

        // Turn torque
        rb.AddTorque(Vector3.up * angularZ * turnSpeed, ForceMode.Force);

        // Clamp max speed
        if (rb.linearVelocity.magnitude > maxSpeed)
            rb.linearVelocity = rb.linearVelocity.normalized * maxSpeed;
    }
}