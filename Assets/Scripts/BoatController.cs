using UnityEngine;
using UnityEngine.InputSystem;

[RequireComponent(typeof(Rigidbody))]
public class BoatController : MonoBehaviour
{
    [Header("Movement")]
    public float thrustForce = 10f;
    public float turnTorque = 2f;
    public float maxSpeed = 8f;

    [Header("Damping")]
    public float linearDrag = 0.5f;
    public float angularDrag = 1.5f;

    private Rigidbody rb;
    private float thrustInput;
    private float turnInput;

    private void Awake()
    {
        rb = GetComponent<Rigidbody>();
        rb.linearDamping = linearDrag;
        rb.angularDamping = angularDrag;

        // Boat only yaws (turns) — never rolls or pitches over.
        rb.constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;
    }

    private void Update()
    {
        var kb = Keyboard.current;
        if (kb == null) return;

        thrustInput = 0f;
        turnInput = 0f;

        if (kb.wKey.isPressed) thrustInput += 1f;
        if (kb.sKey.isPressed) thrustInput -= 1f;
        if (kb.dKey.isPressed) turnInput += 1f;
        if (kb.aKey.isPressed) turnInput -= 1f;
    }

    private void FixedUpdate()
    {
        // Thrust along the boat's forward, flattened to horizontal so tilt doesn't push it down.
        Vector3 flatForward = Vector3.ProjectOnPlane(transform.forward, Vector3.up).normalized;
        rb.AddForce(flatForward * thrustInput * thrustForce, ForceMode.Acceleration);

        // Yaw around WORLD up, so it always turns flat regardless of boat tilt.
        rb.AddTorque(Vector3.up * turnInput * turnTorque, ForceMode.Acceleration);

        // Clamp horizontal speed, leave vertical (buoyancy) untouched.
        Vector3 horizVel = new Vector3(rb.linearVelocity.x, 0f, rb.linearVelocity.z);
        if (horizVel.magnitude > maxSpeed)
        {
            Vector3 clamped = horizVel.normalized * maxSpeed;
            rb.linearVelocity = new Vector3(clamped.x, rb.linearVelocity.y, clamped.z);
        }
    }
}