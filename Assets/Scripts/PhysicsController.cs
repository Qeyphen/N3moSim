using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;
using RosMessageTypes.Std;
using RosMessageTypes.BuiltinInterfaces;

/// <summary>
/// Physics-based vessel controller.
///
/// Receives a target waypoint from ROS2 via /[id]/waypoint.
/// Uses Unity Rigidbody arrive behaviour — accelerates toward
/// the target, smoothly decelerates as it gets close, stops on arrival.
/// No oscillation. No teleportation.
///
/// Publishes actual position back to ROS2 via /[id]/actual_pose.
/// </summary>
public class PhysicsController : MonoBehaviour
{
    [Header("ROS2 Topics")]
    public string waypointTopic = "/waypoint";
    public string poseTopic     = "/actual_pose";
    public string objectId      = "";

    [Header("Physics — Vessel Properties")]
    [Tooltip("Vessel mass in kg")]
    public float mass        = 800f;
    [Tooltip("Water resistance — higher = slower top speed")]
    public float linearDrag  = 1.0f;
    [Tooltip("Rotational resistance — higher = sluggish turning")]
    public float angularDrag = 2.0f;

    [Header("Engine — Force Properties")]
    [Tooltip("Maximum force in Newtons")]
    public float maxForce  = 3000f;
    [Tooltip("Maximum turning torque")]
    public float maxTorque = 1000f;
    [Tooltip("Maximum speed in m/s")]
    public float maxSpeed  = 6f;

    [Header("Navigation")]
    [Tooltip("Distance at which boat is considered arrived")]
    public float arrivalRadius = 5f;

    [Header("Prefab Axis")]
    [Tooltip("Tick this for sailboat prefab — mesh faces -Z")]
    public bool invertForward = true;

    // ── private state ─────────────────────────────────────────
    private Rigidbody     rb;
    private ROSConnection ros;
    private Vector3       targetWaypoint;
    private bool          hasWaypoint  = false;
    private bool          arrived      = false;
    private float         publishTimer = 0f;
    private const float   PUBLISH_HZ   = 10f;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        if (rb == null)
            rb = gameObject.AddComponent<Rigidbody>();

        rb.mass           = mass;
        rb.linearDamping  = linearDrag;
        rb.angularDamping = angularDrag;
        rb.useGravity     = false;
        rb.isKinematic    = false;

        // vessel stays flat on water
        rb.constraints = RigidbodyConstraints.FreezePositionY
                       | RigidbodyConstraints.FreezeRotationX
                       | RigidbodyConstraints.FreezeRotationZ;

        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<PointStampedMsg>(waypointTopic, OnWaypointReceived);
        ros.RegisterPublisher<PoseStampedMsg>(poseTopic);

        Debug.Log($"[PhysicsController] '{objectId}' ready" +
                  $"\n  waypoint : {waypointTopic}" +
                  $"\n  pose     : {poseTopic}" +
                  $"\n  mass     : {mass}kg" +
                  $"\n  maxForce : {maxForce}N" +
                  $"\n  maxSpeed : {maxSpeed}m/s");
    }

    // ── new waypoint received from ROS2 ──────────────────────────────────────
    void OnWaypointReceived(PointStampedMsg msg)
    {
        targetWaypoint = new Vector3(
            (float)msg.point.x,
            transform.position.y,
            (float)msg.point.z
        );
        hasWaypoint = true;
        arrived     = false;  // reset arrival so boat moves to new target

        Debug.Log($"[PhysicsController] {objectId} new waypoint → " +
                  $"({targetWaypoint.x:F1}, {targetWaypoint.z:F1})");
    }

    // ── physics update ────────────────────────────────────────────────────────
    void FixedUpdate()
{
    // always publish position
    publishTimer += Time.fixedDeltaTime;
    if (publishTimer >= 1f / PUBLISH_HZ)
    {
        publishTimer = 0f;
        PublishActualPosition();
    }

    if (!hasWaypoint) return;

    Vector3 toTarget     = targetWaypoint - transform.position;
    toTarget.y           = 0f;
    float   distToTarget = toTarget.magnitude;
    Vector3 dirToTarget  = toTarget.normalized;

    // ── arrived — hard stop ───────────────────────────────────
    if (distToTarget < arrivalRadius)
    {
        if (!arrived)
        {
            arrived = true;
            Debug.Log($"[PhysicsController] {objectId} arrived");
        }
        rb.linearVelocity  = Vector3.zero;
        rb.angularVelocity = Vector3.zero;
        return;
    }

    arrived = false;

    // ── effective forward ─────────────────────────────────────
    Vector3 boatForward = invertForward ? -transform.forward : transform.forward;

    // ── steering ──────────────────────────────────────────────
    float angleToTarget = Vector3.SignedAngle(boatForward, dirToTarget, Vector3.up);
    float torqueFactor  = Mathf.Clamp(angleToTarget / 45f, -1f, 1f);
    rb.AddTorque(Vector3.up
        * (invertForward ? -torqueFactor : torqueFactor)
        * maxTorque);

    // ── propulsion — only push if slower than target speed ────
    // NO velocity subtraction — that's what caused oscillation
    float throttle      = Mathf.Clamp01(distToTarget / (arrivalRadius * 4f));
    float alignment     = Mathf.Clamp01(1f - Mathf.Abs(angleToTarget) / 90f);
    float targetSpeed   = maxSpeed * throttle;
    float currentSpeed  = new Vector3(rb.linearVelocity.x, 0, rb.linearVelocity.z).magnitude;

    // only add force if we're going slower than we should be
    // never add force if we're already at target speed
    if (currentSpeed < targetSpeed)
    {
        float forceFraction = (targetSpeed - currentSpeed) / maxSpeed;
        rb.AddForce(dirToTarget * maxForce * forceFraction * alignment);
    }

    // ── speed cap ─────────────────────────────────────────────
    Vector3 vel = rb.linearVelocity;
    vel.y = 0f;
    if (vel.magnitude > maxSpeed)
        rb.linearVelocity = vel.normalized * maxSpeed;
}

    void PublishActualPosition()
    {
        var msg = new PoseStampedMsg
        {
            header = new HeaderMsg
            {
                stamp    = new TimeMsg { sec = (int)Time.time, nanosec = 0 },
                frame_id = "world"
            },
            pose = new PoseMsg
            {
                position = new PointMsg(
                    transform.position.x,
                    transform.position.y,
                    transform.position.z),
                orientation = new QuaternionMsg(
                    transform.rotation.x,
                    transform.rotation.y,
                    transform.rotation.z,
                    transform.rotation.w)
            }
        };
        ros.Publish(poseTopic, msg);
    }

    void OnDrawGizmos()
    {
        if (!hasWaypoint) return;

        // cyan = target waypoint
        Gizmos.color = arrived ? Color.green : Color.cyan;
        Gizmos.DrawWireSphere(targetWaypoint, arrivalRadius);
        Gizmos.DrawLine(transform.position, targetWaypoint);

        // green = effective forward direction
        Vector3 fwd = invertForward ? -transform.forward : transform.forward;
        Gizmos.color = Color.green;
        Gizmos.DrawRay(transform.position, fwd * 8f);
    }
}