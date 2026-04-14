using UnityEngine;

public class FollowCamera : MonoBehaviour
{
    [Header("Target")]
    public string targetName  = "sailboat_01";
    public Vector3 offset     = new Vector3(0, 5, 15);
    public float smoothTime   = 0.3f;

    private Transform target;
    private Vector3 velocity  = Vector3.zero;

    void Start()
    {
        Invoke(nameof(FindTarget), 1f);
    }

    void FindTarget()
    {
        GameObject obj = GameObject.Find(targetName);
        if (obj != null)
        {
            target = obj.transform;
            // Snap instantly on first find
            transform.position = target.position + offset;
            transform.LookAt(target);
            Debug.Log($"[FollowCamera] Now following: {targetName}");
        }
        else
        {
            Debug.Log($"[FollowCamera] Waiting for: {targetName}");
            Invoke(nameof(FindTarget), 0.5f);
        }
    }

    void LateUpdate()
    {
        if (target == null) return;

        Vector3 targetPos = target.position + offset;

        // SmoothDamp — like the YouTube tutorial
        transform.position = Vector3.SmoothDamp(
            transform.position,
            targetPos,
            ref velocity,
            smoothTime
        );

        transform.LookAt(target);
    }
}