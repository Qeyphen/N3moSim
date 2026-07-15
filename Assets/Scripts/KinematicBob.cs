using UnityEngine;

// Physics-free bob/sway for kinematic traffic (which ignores WaterFloater's forces).
// Oscillates the LOCAL pose, so put it on the model child, not the spawner-driven root.
public class KinematicBob : MonoBehaviour
{
    [Tooltip("Vertical bob height (m).")]
    public float bobHeight = 0.12f;
    [Tooltip("Bob cycles per second.")]
    public float bobSpeed = 0.6f;
    [Tooltip("Max roll/pitch sway (degrees).")]
    public float swayDegrees = 3f;
    [Tooltip("Sway cycles per second.")]
    public float swaySpeed = 0.4f;

    private Vector3 baseLocalPos;
    private Quaternion baseLocalRot;
    private float phase;   // per-instance offset so traffic doesn't bob in lockstep

    void Start()
    {
        baseLocalPos = transform.localPosition;
        baseLocalRot = transform.localRotation;
        phase = (GetInstanceID() & 0xffff) * 0.1f;
    }

    void Update()
    {
        float t = Time.time;
        float bob = Mathf.Sin((t * bobSpeed + phase) * 2f * Mathf.PI) * bobHeight;
        float roll = Mathf.Sin((t * swaySpeed + phase) * 2f * Mathf.PI) * swayDegrees;
        float pitch = Mathf.Cos((t * swaySpeed * 0.8f + phase) * 2f * Mathf.PI) * swayDegrees * 0.6f;

        transform.localPosition = baseLocalPos + Vector3.up * bob;
        transform.localRotation = baseLocalRot * Quaternion.Euler(pitch, 0f, roll);
    }
}
