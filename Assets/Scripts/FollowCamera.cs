using UnityEngine;

public class FollowCamera : MonoBehaviour
{
    [Header("Settings")]
    public float height   = 10f;
    public float distance = 250f;

    private Transform target;

    void Start()
    {
        InvokeRepeating(nameof(FindTarget), 1f, 0.5f);
    }

void FindTarget()
{
    GameObject boat = GameObject.Find("sailboat_01");
    if (boat == null) return;

    // Look for CameraTarget as child of sailboat specifically
    Transform ct = boat.transform.Find("CameraTarget");
    if (ct != null)
    {
        target = ct;
        CancelInvoke(nameof(FindTarget));
        Debug.Log($"[Camera] Found CameraTarget child at {target.position}");
        return;
    }

    // No CameraTarget found — use renderer bounds
    Renderer[] renderers = boat.GetComponentsInChildren<Renderer>();
    Vector3 visualCenter = boat.transform.position + Vector3.up * 3f;

    if (renderers.Length > 0)
    {
        Bounds bounds = renderers[0].bounds;
        foreach (Renderer r in renderers)
            bounds.Encapsulate(r.bounds);
        visualCenter = bounds.center;
    }

    GameObject t = new GameObject("CameraTarget");
    t.transform.position = visualCenter;
    t.transform.SetParent(boat.transform);
    target = t.transform;

    CancelInvoke(nameof(FindTarget));
    Debug.Log($"[Camera] Created CameraTarget at {target.position}");
}

    void LateUpdate()
    {
        if (target == null) return;

        transform.position = new Vector3(
            target.position.x,
            target.position.y + height,
            target.position.z + distance
        );

        transform.LookAt(target.position + Vector3.up * 2f);
    }
}