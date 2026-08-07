using UnityEngine;
using UnityEngine.Perception.GroundTruth;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Std;

// Sets the Perception capture resolution (output image pixels) by giving the POV camera a
// RenderTexture of that size. Configurable in the Inspector and over ROS on /camera/resolution
// (either "WxH" like "1920x1080", or a preset: 360p/720p/1080p/4k — all 16:9, so FOV is kept).
public class CaptureResolution : MonoBehaviour
{
    [Header("Resolution (pixels)")]
    public int width = 1280;
    public int height = 720;

    [Header("ROS")]
    public bool enableRos = true;
    public string resolutionTopic = "/camera/resolution";

    private Camera cam;
    private RenderTexture rt;
    private bool applied;

    void Start()
    {
        if (enableRos && !string.IsNullOrEmpty(resolutionTopic))
            ROSConnection.GetOrCreateInstance().Subscribe<StringMsg>(resolutionTopic, OnResolution);
        TryApply();
    }

    // The camera spawns with the boat at runtime, so keep trying until it exists.
    void Update() { if (!applied) TryApply(); }

    void OnResolution(StringMsg m)
    {
        if (!Parse(m.data, out int w, out int h))
        {
            Debug.LogWarning($"[CaptureResolution] bad '{m.data}' — use WxH (1920x1080) or 360p/720p/1080p/4k.");
            return;
        }
        width = w; height = h;
        applied = false;
        TryApply();
    }

    static bool Parse(string s, out int w, out int h)
    {
        w = h = 0;
        switch ((s ?? "").Trim().ToLower())
        {
            case "360p": w = 640;  h = 360;  return true;
            case "720p": w = 1280; h = 720;  return true;
            case "1080p": w = 1920; h = 1080; return true;
            case "4k": w = 3840; h = 2160; return true;
        }
        var p = (s ?? "").ToLower().Split('x');
        return p.Length == 2 && int.TryParse(p[0], out w) && int.TryParse(p[1], out h) && w > 0 && h > 0;
    }

    void TryApply()
    {
        if (cam == null)
        {
            var pc = FindFirstObjectByType<PerceptionCamera>();
            if (pc != null) cam = pc.GetComponent<Camera>();
        }
        if (cam == null) return;
        Apply();
        applied = true;
    }

    [ContextMenu("Apply Resolution")]
    void Apply()
    {
        if (cam == null)
        {
            var pc = FindFirstObjectByType<PerceptionCamera>();
            cam = pc != null ? pc.GetComponent<Camera>() : null;
        }
        if (cam == null) { Debug.LogWarning("[CaptureResolution] no PerceptionCamera found."); return; }

        var old = rt;
        rt = new RenderTexture(Mathf.Max(16, width), Mathf.Max(16, height), 24) { name = $"Capture_{width}x{height}" };
        rt.Create();
        cam.targetTexture = rt;
        DestroyRT(old);
        Debug.Log($"[CaptureResolution] capture size = {width}x{height} on '{cam.name}'.");
    }

    void OnDestroy()
    {
        if (cam != null && cam.targetTexture == rt) cam.targetTexture = null;
        DestroyRT(rt);
    }

    static void DestroyRT(RenderTexture t)
    {
        if (t == null) return;
        t.Release();
        if (Application.isPlaying) Destroy(t); else DestroyImmediate(t);
    }
}
