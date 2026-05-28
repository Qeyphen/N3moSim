using UnityEngine;
using RosMessageTypes.Geometry;
using Unity.Robotics.ROSTCPConnector;

/// <summary>
/// PD controller with state machine: Idle → Turning → Driving → Arrived.
/// Automatically turns then drives — no manual enableDrive toggle needed.
/// Only accepts a new waypoint when Idle or Arrived.
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
    public float linearDrag  = 0.5f;
    public float angularDrag = 5.0f;

    // ── Turn ──────────────────────────────────────────────────────────────────
    [Header("Turn")]
    public float turnKp       = 80f;
    public float maxTurnRate  = 0.8f;
    public float turnDeadband = 5f;

    // ── Drive ─────────────────────────────────────────────────────────────────
    [Header("Drive")]
    public float driveKp        = 10000;
    public float maxForce       = 5000f;
    public float maxSpeed       = 10f;
    public float arrivalRadius  = 5f;
    [Tooltip("Only start driving when heading error is below this (deg)")]
    public float driveAngleGate = 20f;

    // ── Forward axis correction ───────────────────────────────────────────────
    [Header("Prefab correction")]
    [Tooltip("Set Y=180 if bow points toward -Z")]
    public Vector3 forwardOffset = Vector3.zero;

    // ── Telemetry ─────────────────────────────────────────────────────────────
    [Header("Telemetry")]
    public float posePublishHz    = 10f;
    public int   logEveryNSeconds = 5;

    // ── State machine ─────────────────────────────────────────────────────────
    public enum State { Idle, Turning, Driving, Arrived }

    [Header("State (read-only)")]
    [SerializeField] private State currentState = State.Idle;

    // ── Internals ─────────────────────────────────────────────────────────────
    private Rigidbody     rb;
    private ROSConnection ros;
    private Vector3       waypointWorld = Vector3.zero;
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

        logFrameInterval = Mathf.Max(1,
            Mathf.RoundToInt(logEveryNSeconds / Time.fixedDeltaTime));

        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<PointStampedMsg>(waypointTopic, OnWaypoint);
        ros.RegisterPublisher<PoseStampedMsg>(poseTopic);

        Debug.Log($"[SimpleController] {objectId} ready | topic: {waypointTopic}");
    }

    void OnWaypoint(PointStampedMsg msg)
    {
        // Accept new waypoint any time except while actively driving
        // (so a new command mid-drive is also honoured)
        waypointWorld = new Vector3(
            (float)msg.point.x,
            transform.position.y,
            (float)msg.point.z
        );

        prevDistError = 0f;
        SetState(State.Turning);
        Debug.Log($"[SimpleController] Waypoint → {waypointWorld}  state: Turning");
    }

    void SetState(State next)
    {
        currentState = next;

        if (next == State.Arrived)
        {
            // Kill all velocity on arrival
            rb.linearVelocity  = Vector3.zero;
            rb.angularVelocity = Vector3.zero;
            Debug.Log($"[SimpleController] {objectId} ARRIVED — velocity zeroed");
        }
    }

    void FixedUpdate()
    {
        fixedFrame++;
        float dt = Time.fixedDeltaTime;

        if (currentState == State.Idle || currentState == State.Arrived) return;

        // ── Common: vector to waypoint ───────────────────────────────────────
        Vector3 toWaypoint = waypointWorld - transform.position;
        toWaypoint.y = 0f;
        float dist = toWaypoint.magnitude;

        // ── Arrived check ────────────────────────────────────────────────────
        if (dist <= arrivalRadius)
        {
            SetState(State.Arrived);
            return;
        }

        // ── Angle error ──────────────────────────────────────────────────────
        Vector3 forward    = Quaternion.Euler(forwardOffset) * transform.forward;
        forward.y          = 0f;
        Vector3 bowForward = forward.normalized;

        float targetAngle  = Mathf.Atan2(toWaypoint.x, toWaypoint.z) * Mathf.Rad2Deg;
        float currentAngle = Mathf.Atan2(forward.x,    forward.z)    * Mathf.Rad2Deg;
        float angleError   = Mathf.DeltaAngle(currentAngle, targetAngle);

        // ── Turn ─────────────────────────────────────────────────────────────
        if (Mathf.Abs(angleError) > turnDeadband)
        {
            float angVelDelta = turnKp * angleError * Mathf.Deg2Rad * dt;
            angVelDelta = Mathf.Clamp(angVelDelta, -maxTurnRate * dt, maxTurnRate * dt);
            rb.AddTorque(Vector3.up * angVelDelta, ForceMode.VelocityChange);
        }
        else
        {
            rb.angularVelocity = Vector3.Lerp(rb.angularVelocity, Vector3.zero, 0.3f);

            // Heading settled — transition to Driving
            if (currentState == State.Turning)
                SetState(State.Driving);
        }

        // ── Drive ─────────────────────────────────────────────────────────────
        if (currentState == State.Driving && Mathf.Abs(angleError) < driveAngleGate)
        {
            float speed     = Vector3.Dot(rb.linearVelocity, bowForward);
            float desired   = Mathf.Min(dist * 0.4f, maxSpeed);
            float distError = desired - speed;
            float dDist     = (distError - prevDistError) / dt;
            float force     = Mathf.Clamp(driveKp * distError + 60f * dDist, 0f, maxForce);
            rb.AddForce(bowForward * force, ForceMode.Force);
            prevDistError = distError;
        }

        // ── Periodic log ─────────────────────────────────────────────────────
        if (fixedFrame % logFrameInterval == 0)
        {
            float heading = Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg;
            float speed   = Vector3.Dot(rb.linearVelocity, bowForward);
            Debug.Log($"[SimpleController] {objectId} [{currentState}]" +
                      $" | heading: {heading:F1}°  target: {targetAngle:F1}°  error: {angleError:F1}°" +
                      $"  angVel: {rb.angularVelocity.y * Mathf.Rad2Deg:F2}°/s" +
                      $" | dist: {dist:F1}m  speed: {speed:F2}m/s" +
                      $" | pos: ({transform.position.x:F1}, {transform.position.z:F1})");
        }

        // ── Pose telemetry ────────────────────────────────────────────────────
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
        if (currentState == State.Idle) return;
        Gizmos.color = currentState == State.Arrived ? Color.green : Color.cyan;
        Gizmos.DrawSphere(waypointWorld, 2f);
        Gizmos.DrawLine(transform.position, waypointWorld);
    }
}