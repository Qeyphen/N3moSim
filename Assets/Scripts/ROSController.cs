using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;

public class ROSController : MonoBehaviour
{
    [Header("ROS2 Settings")]
    public string topic    = "/cmd_vel";
    public string objectId = "";

    [Header("Movement Settings")]
    public float moveSpeed = 2f;
    public float turnSpeed = 15f;
    public float maxSpeed  = 10f;

    [Header("Water Settings")]
    [Tooltip("Flip movement direction if vessel moves backwards")]
    public bool  invertForward    = false;
    [Tooltip("Use for prefabs with -90 X rotation (catamaran, buoy)")]
    public bool  useUpAsForward   = false;
    [Tooltip("Fine-tune Y if vessel is submerged or floating too high")]
    public float waterLevelOffset = 0f;

    [Header("Pose Control")]
    [Tooltip("Enable to receive PoseStamped instead of Twist — perfect circles, no physics drift")]
    public bool  usePoseControl = false;
    public string poseTopic     = "/pose";

    [Header("Safety")]
    [Tooltip("Stop vessel if no command received for this many seconds. Set high to survive bridge reconnects.")]
    public float commandTimeout = 30f;

    private float linearX        = 0f;
    private float angularZ       = 0f;
    private float waterLevel;
    private float lastCommandTime = 0f;
    private Rigidbody rb;
    private ROSConnection ros;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        if (rb == null)
            rb = gameObject.AddComponent<Rigidbody>();

        // Capture spawn Y + offset as water level
        waterLevel = transform.position.y + waterLevelOffset;

        if (usePoseControl)
        {
            // Pose control — kinematic, no physics needed
            rb.isKinematic = true;
            rb.useGravity  = false;

            ros = ROSConnection.GetOrCreateInstance();
            ros.Subscribe<PoseStampedMsg>(poseTopic, OnPose);
            Debug.Log($"[ROSController] '{objectId}' POSE mode | topic={poseTopic}");
        }
        else
        {
            // Velocity control
            rb.isKinematic    = false;
            rb.useGravity     = false;
            rb.mass           = 1f;
            rb.linearDamping  = 0.5f;
            rb.angularDamping = 1f;

            rb.constraints = RigidbodyConstraints.FreezeRotationX
                           | RigidbodyConstraints.FreezeRotationZ;

            ros = ROSConnection.GetOrCreateInstance();
            ros.Subscribe<TwistMsg>(topic, OnROSCommand);

            lastCommandTime = Time.time;

            Debug.Log($"[ROSController] '{objectId}' VELOCITY mode | " +
                      $"topic={topic} | " +
                      $"waterLevel={waterLevel:F2} | " +
                      $"useUpAsForward={useUpAsForward} | " +
                      $"invertForward={invertForward}");
        }
    }

    // ── Pose control ──────────────────────────────────────────────
    void OnPose(PoseStampedMsg msg)
    {
        // Directly teleport to exact position — perfect circles, no drift
        transform.position = new Vector3(
            (float)msg.pose.position.x,
            (float)msg.pose.position.y,
            (float)msg.pose.position.z
        );

        transform.rotation = new Quaternion(
            (float)msg.pose.orientation.x,
            (float)msg.pose.orientation.y,
            (float)msg.pose.orientation.z,
            (float)msg.pose.orientation.w
        );
    }

    // ── Velocity control ──────────────────────────────────────────
    void OnROSCommand(TwistMsg msg)
    {
        linearX         = (float)msg.linear.x;
        angularZ        = (float)msg.angular.z;
        lastCommandTime = Time.time;
        Debug.Log($"[ROSController] {objectId} ← " +
                  $"linear.x={linearX:F2} angular.z={angularZ:F2}");
    }

    void FixedUpdate()
    {
        if (usePoseControl) return; // pose handled in OnPose callback
        ApplyMovement();
        LockToWaterLevel();
    }

    void ApplyMovement()
    {
        if (rb == null) return;

        // Auto-stop if no command received within timeout
        if (Time.time - lastCommandTime > commandTimeout)
        {
            linearX  = 0f;
            angularZ = 0f;
        }

        // Choose correct forward axis:
        // - Sailboat (normal prefab):            transform.forward
        // - Catamaran/Buoy (-90 X rotation):     transform.up
        Vector3 forward;
        if (useUpAsForward)
            forward = transform.up;
        else
            forward = transform.forward;

        // Flip if vessel moves backwards
        if (invertForward)
            forward = -forward;

        // Strip Y so movement stays flat on water
        Vector3 flatForward = new Vector3(forward.x, 0f, forward.z);

        // Fallback if vector collapses
        if (flatForward.magnitude < 0.01f)
        {
            Debug.LogWarning($"[ROSController] {objectId}: " +
                             "forward vector collapsed — using world Z as fallback");
            flatForward = Vector3.forward;
        }

        flatForward.Normalize();

        Vector3 targetVelocity = flatForward * linearX * moveSpeed;

        // Clamp to max speed
        if (targetVelocity.magnitude > maxSpeed)
            targetVelocity = targetVelocity.normalized * maxSpeed;

        // Smooth velocity transition
        rb.linearVelocity = Vector3.Lerp(
            rb.linearVelocity,
            targetVelocity,
            Time.fixedDeltaTime * 5f
        );

        // Rotate on Y axis only
        if (Mathf.Abs(angularZ) > 0.01f)
        {
            float yaw = angularZ * turnSpeed * Time.fixedDeltaTime;
            rb.MoveRotation(rb.rotation * Quaternion.Euler(0, yaw, 0));
        }
    }

    void LockToWaterLevel()
    {
        Vector3 pos = rb.position;
        pos.y = waterLevel;
        rb.position = pos;

        Vector3 vel = rb.linearVelocity;
        vel.y = 0f;
        rb.linearVelocity = vel;
    }

    public void SetVelocity(float forward, float turn)
    {
        linearX  = forward;
        angularZ = turn;
    }
}