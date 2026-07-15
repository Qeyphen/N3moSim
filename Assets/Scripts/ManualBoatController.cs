using UnityEngine;
using UnityEngine.InputSystem;

public class ManualBoatController : MonoBehaviour
{
    [Header("Boat Settings")]
    public Transform       motor;
    public float           steerPower = 500f;
    public float           power      = 5f;
    public float           maxSpeed   = 10f;
    public float           drag       = 0.1f;

    private Rigidbody      rb;
    private Quaternion     startMotorRotation;
    private ParticleSystem exhaustParticles;

    void Awake()
    {
        rb                 = GetComponent<Rigidbody>();
        startMotorRotation = motor != null
            ? motor.localRotation : Quaternion.identity;
        exhaustParticles   = GetComponentInChildren<ParticleSystem>();
    }

    void FixedUpdate()
    {
        if (rb == null) return;

        float steer    = 0f;
        bool  forward  = Keyboard.current.wKey.isPressed;
        bool  backward = Keyboard.current.sKey.isPressed;

        if (Keyboard.current.aKey.isPressed) steer =  1f;
        if (Keyboard.current.dKey.isPressed) steer = -1f;

        if (motor != null)
            rb.AddForceAtPosition(
                steer * transform.right * steerPower * 0.01f,
                motor.position
            );

        Vector3 fwd = Vector3.Scale(new Vector3(1f, 0f, 1f), transform.forward);
        if (fwd.sqrMagnitude > 0f) fwd.Normalize();

        if (forward)
            ApplyForceToReachVelocity(fwd * maxSpeed);
        else if (backward)
            ApplyForceToReachVelocity(fwd * -maxSpeed);

        if (motor != null)
            motor.SetPositionAndRotation(
                motor.position,
                transform.rotation
                    * startMotorRotation
                    * Quaternion.Euler(0f, 30f * steer, 0f)
            );

        if (exhaustParticles != null)
        {
            if (forward || backward)
                exhaustParticles.Play();
            else
                exhaustParticles.Pause();
        }

        bool    movingForward = Vector3.Dot(
                                    transform.forward,
                                    rb.linearVelocity) > 0f;
        Vector3 targetDir     = movingForward
                                ? transform.forward
                                : -transform.forward;
        float   angle         = Vector3.SignedAngle(
                                    rb.linearVelocity, targetDir, Vector3.up);

        rb.linearVelocity = Quaternion.AngleAxis(angle * drag, Vector3.up)
                          * rb.linearVelocity;
    }


    void ApplyForceToReachVelocity(Vector3 targetVelocity)
    {
        Vector3 force = (targetVelocity - rb.linearVelocity) * power;
        rb.AddForce(force, ForceMode.Acceleration);
    }
}