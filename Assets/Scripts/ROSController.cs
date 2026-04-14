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

    private float linearX  = 0f;
    private float angularZ = 0f;
    private float waterLevel;
    private Rigidbody rb;
    private ROSConnection ros;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        if (rb == null)
            rb = gameObject.AddComponent<Rigidbody>();

        // Capture spawn Y + offset as water level
        waterLevel = transform.position.y + waterLevelOffset;

        rb.isKinematic    = false;
        rb.useGravity     = false;
        rb.mass           = 1f;
        rb.linearDamping  = 0.5f;
        rb.angularDamping = 1f;

        // Only freeze X/Z rotation — vessel rotates on Y only
        rb.constraints = RigidbodyConstraints.FreezeRotationX
                       | RigidbodyConstraints.FreezeRotationZ;

        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<TwistMsg>(topic, OnROSCommand);

        Debug.Log($"[ROSController] '{objectId}' ready | " +
                  $"topic={topic} | " +
                  $"waterLevel={waterLevel:F2} | " +
                  $"useUpAsForward={useUpAsForward} | " +
                  $"invertForward={invertForward}");
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
        LockToWaterLevel();
    }

    void ApplyMovement()
    {
        if (rb == null) return;

        // Choose correct forward axis:
        // - Sailboat (normal prefab):          transform.forward
        // - Catamaran/Buoy (-90 X rotation):   transform.up
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

        // If stripping Y collapses the vector (vessel pointing straight up/down)
        // fall back to world forward so vessel can still move
        if (flatForward.magnitude < 0.01f)
        {
            Debug.LogWarning($"[ROSController] {objectId}: " +
                             $"forward vector collapsed after Y-strip " +
                             $"(raw forward={forward}) — using world Z as fallback");
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
        // Snap Y back to water level every physics frame
        Vector3 pos = rb.position;
        pos.y = waterLevel;
        rb.position = pos;

        // Kill vertical velocity
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