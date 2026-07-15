using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

// Point-based buoyancy for the ego boat. Keeps the hull upright and floating, and gives the
// water a constant drag so the autonomous controller can stop at its target.
public class WaterFloater : MonoBehaviour
{
    public float depthBefSub     = 1f;    // depth (m) for full buoyancy
    public float displacementAmt = 3f;    // lift per point (x gravity at full submersion)
    public int   floaters        = 4;     // floater points on the hull
    [Tooltip("Water linear drag (Rigidbody.linearDamping).")]
    public float linearDrag      = 3f;
    [Tooltip("Water angular drag (Rigidbody.angularDamping); damps yaw so steering settles.")]
    public float angularDrag     = 2f;
    public WaterSurface water;

    private Rigidbody rb;

    void Awake()
    {
        rb = GetComponentInParent<Rigidbody>();
        if (water == null) water = FindFirstObjectByType<WaterSurface>();
        if (rb != null)
        {
            rb.useGravity = false;   // gravity is supplied below, per floater
            rb.constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;
            rb.linearDamping  = linearDrag;
            rb.angularDamping = angularDrag;
        }
    }

    void FixedUpdate()
    {
        if (rb == null || water == null || floaters <= 0 || depthBefSub <= 0f) return;

        rb.AddForceAtPosition(Physics.gravity / floaters, transform.position, ForceMode.Acceleration);

        WaterSearchParameters search = new WaterSearchParameters
        {
            startPositionWS    = transform.position + Vector3.up * 10f,
            targetPositionWS   = transform.position,
            error              = 0.01f,
            maxIterations      = 8,
            includeDeformation = true,
            excludeSimulation  = false
        };
        water.ProjectPointOnWaterSurface(search, out WaterSearchResult result);
        float waterHeight = result.projectedPositionWS.y;
        if (float.IsNaN(waterHeight) || float.IsInfinity(waterHeight)) return;

        if (transform.position.y < waterHeight)
        {
            float displacementMulti =
                Mathf.Clamp01((waterHeight - transform.position.y) / depthBefSub) * displacementAmt;
            rb.AddForceAtPosition(
                new Vector3(0f, Mathf.Abs(Physics.gravity.y) * displacementMulti, 0f),
                transform.position, ForceMode.Acceleration);
        }
    }
}
