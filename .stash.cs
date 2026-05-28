using UnityEngine;
using RosMessageTypes.Geometry;
using Unity.Robotics.ROSTCPConnector;

/// <summary>
/// Stage 1: Pure P turn-only controller — no derivative, no drive.
///          Boat turns to face waypoint and holds there.
/// Stage 2: Enable drive once turning is stable.
/// </summary>
public class SimpleController : MonoBehaviour
{
    // ── ROS ──────────────────────────────────────────────────────────────────
    [Header("ROS Topics (set by SceneLoader)")]
    public string waypointTopic = "/sailboat_01/waypoint";
    public string poseTopic     = "/sailboat_01/actual_pose";
    public string objectId      = "sailboat_01";

    // ── Rigidbody ─────────────────────────────────────────────────────────────
    [Header("Physics")]
    public float mass        = 800f;
    public float linearDrag  = 3.0f;
    public float angularDrag = 5.0f;

    // ── Turn (P only) ─────────────────────────────────────────────────────────
    [Header("Turn")]
    [Tooltip("Torque per degree of heading error")]
    public float turnKp       = 80f;
    [Tooltip("Max angular velocity change per FixedUpdate (rad/s) — hard speed cap on turning")]
    public float maxTurnRate  = 0.8f;
    [Tooltip("Stop applying torque when error is below this (deg) — increase if oscillating")]
    public float turnDeadband = 5f;

    // ── Drive (disabled until turning is verified) ────────────────────────────
    [Header("Drive — enable only after turn is stable")]
    public bool  enableDrive    = false;
    public float driveKp        = 400f;
    public float maxForce       = 3000f;
    public float maxSpeed       = 6f;
    public float arrivalRadius  = 3f;
    [Tooltip("Only drive when heading error is below this (deg)")]
    public float driveAngleGate = 20f;

    // ── Forward axis correction ───────────────────────────────────────────────
    [Header("Prefab correction")]
    [Tooltip("Set Y=180 if bow points toward -Z (green arrow exits stern)")]
    public Vector3 forwardOffset = Vector3.zero;

    // ── Telemetry ─────────────────────────────────────────────────────────────
    [Header("Telemetry")]
    public float posePublishHz    = 10f;
    public int   logEveryNSeconds = 5;

    // ── Internals ─────────────────────────────────────────────────────────────
    private Rigidbody     rb;
    private ROSConnection ros;
    private Vector3       waypointWorld = Vector3.zero;
    private bool          hasWaypoint   = false;
    private float         poseTimer     = 0f;
    private float         prevDistError = 0f;
    private int           fixedFrame    = 0;
    private int           logFrameInterval;

    // ─────────────────────────────────────────────────────────────────────────

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        if (rb == null) rb = gameObject.AddComponent<Rigidbody>();

        rb.mass           = mass;
        rb.linearDamping  = linearDrag;
        rb.angularDamping = angularDrag;
        rb.useGravity     = true;
        rb.isKinematic    = false;
        rb.constraints    = RigidbodyConstraints.FreezeRotationX
                          | RigidbodyConstraints.FreezeRotationZ
                          | RigidbodyConstraints.FreezePositionY;

        // How many FixedUpdate frames equal N seconds
        // (FixedUpdate runs at 1/fixedDeltaTime Hz, default 50Hz)
        logFrameInterval = Mathf.Max(1,
            Mathf.RoundToInt(logEveryNSeconds / Time.fixedDeltaTime));

        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<PointStampedMsg>(waypointTopic, OnWaypoint);
        ros.RegisterPublisher<PoseStampedMsg>(poseTopic);

        Debug.Log($"[SimpleController] {objectId} ready | topic: {waypointTopic}");
    }

    void OnWaypoint(PointStampedMsg msg)
    {
        waypointWorld = new Vector3(
            (float)msg.point.x,
            transform.position.y,
            (float)msg.point.z
        );
        hasWaypoint = true;
        Debug.Log($"[SimpleController] Waypoint received: {waypointWorld}");
    }

    void FixedUpdate()
    {
        fixedFrame++;

        if (!hasWaypoint) return;

        float dt = Time.fixedDeltaTime;

        // ── Vector to waypoint ───────────────────────────────────────────────
        Vector3 toWaypoint = waypointWorld - transform.position;
        toWaypoint.y = 0f;
        float dist = toWaypoint.magnitude;
        if (dist < 0.1f) return;

        // ── Angle error ──────────────────────────────────────────────────────
        Vector3 forward = Quaternion.Euler(forwardOffset) * transform.forward;
        forward.y = 0f;

        float targetAngle  = Mathf.Atan2(toWaypoint.x, toWaypoint.z) * Mathf.Rad2Deg;
        float currentAngle = Mathf.Atan2(forward.x,    forward.z)    * Mathf.Rad2Deg;
        float angleError   = Mathf.DeltaAngle(currentAngle, targetAngle);

        // ── P Turn ───────────────────────────────────────────────────────────
        // Using VelocityChange instead of Force means the value is a direct
        // angular velocity delta (rad/s) rather than a torque scaled by mass.
        // This makes turnKp tuning mass-independent and much more stable.
        if (Mathf.Abs(angleError) > turnDeadband)
        {
            float angVelDelta = turnKp * angleError * Mathf.Deg2Rad * dt;
            angVelDelta = Mathf.Clamp(angVelDelta, -maxTurnRate * dt, maxTurnRate * dt);
            rb.AddTorque(Vector3.up * angVelDelta, ForceMode.VelocityChange);
        }
        else
        {
            // Inside deadband — bleed off any remaining angular velocity
            rb.angularVelocity = Vector3.Lerp(rb.angularVelocity, Vector3.zero, 0.3f);
        }

        // ── Drive (gated, disabled by default) ──────────────────────────────
        if (enableDrive && dist > arrivalRadius && Mathf.Abs(angleError) < driveAngleGate)
        {
            float speed     = Vector3.Dot(rb.linearVelocity, transform.forward);
            float desired   = Mathf.Min(dist * 0.4f, maxSpeed);
            float distError = desired - speed;
            float dDist     = (distError - prevDistError) / dt;
            float force     = Mathf.Clamp(driveKp * distError + 60f * dDist, 0f, maxForce);
            Vector3 bowForward = Quaternion.Euler(forwardOffset) * transform.forward;
            rb.AddForce(bowForward * force, ForceMode.Force);
            prevDistError = distError;
        }

        // ── Periodic heading log ─────────────────────────────────────────────
        if (fixedFrame % logFrameInterval == 0)
        {
            float heading    = Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg;
            Vector3 bowForward = Quaternion.Euler(forwardOffset) * transform.forward;
            float speed      = Vector3.Dot(rb.linearVelocity, bowForward);
            float desired    = Mathf.Min(dist * 0.4f, maxSpeed);
            float distError  = desired - speed;
            Debug.Log($"[SimpleController] {objectId}" +
                      $" | heading: {heading:F1}°  target: {targetAngle:F1}°  error: {angleError:F1}°  angVel: {rb.angularVelocity.y * Mathf.Rad2Deg:F2}°/s" +
                      $" | dist: {dist:F1}m  target: 0m  error: {dist:F1}m  speed: {speed:F2}m/s" +
                      $" | pos: ({transform.position.x:F1}, {transform.position.z:F1})");
        }

        // ── Pose telemetry ───────────────────────────────────────────────────
        poseTimer += dt;
        if (poseTimer >= 1f / posePublishHz)
        {
            PublishPose();
            poseTimer = 0f;
        }
    }

    void PublishPose()
    {
        var msg = new PoseStampedMsg();
        msg.header.frame_id    = "world";
        msg.pose.position.x    = transform.position.x;
        msg.pose.position.y    = transform.position.y;
        msg.pose.position.z    = transform.position.z;
        msg.pose.orientation.x = transform.rotation.x;
        msg.pose.orientation.y = transform.rotation.y;
        msg.pose.orientation.z = transform.rotation.z;
        msg.pose.orientation.w = transform.rotation.w;
        ros.Publish(poseTopic, msg);
    }

    void OnDrawGizmosSelected()
    {
        if (!hasWaypoint) return;
        Gizmos.color = Color.cyan;
        Gizmos.DrawSphere(waypointWorld, 2f);
        Gizmos.DrawLine(transform.position, waypointWorld);
    }
}