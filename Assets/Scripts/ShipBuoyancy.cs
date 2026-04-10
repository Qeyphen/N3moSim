using UnityEngine;

public class ShipBuoyancy : MonoBehaviour
{
    [Header("Buoyancy Settings")]
    public float waterLevel = 0f;
    public float buoyancyForce = 10f;
    public float damping = 0.1f;

    private Rigidbody rb;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
    }

    void FixedUpdate()
    {
        if (rb == null) return;

        float depth = waterLevel - transform.position.y;

        if (depth > 0)
        {
            rb.AddForce(Vector3.up * buoyancyForce * depth, ForceMode.Force);
            rb.linearVelocity *= (1f - damping);
        }
    }
}