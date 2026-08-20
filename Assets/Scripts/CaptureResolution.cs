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
    [Tooltip("Apply this resolution to every Perception camera found in the scene.")]
    public bool applyToAllPerceptionCameras = true;

    private Camera cam;
    private readonly System.Collections.Generic.Dictionary<Camera, RenderTexture> renderTargets =
        new System.Collections.Generic.Dictionary<Camera, RenderTexture>();
    private bool applied;
    private int appliedPerceptionCameraCount;

    void Start()
    {
        if (enableRos && !string.IsNullOrEmpty(resolutionTopic))
            ROSConnection.GetOrCreateInstance().Subscribe<StringMsg>(resolutionTopic, OnResolution);
        TryApply();
    }

    // Perception cameras spawn with the boat at runtime, so keep trying until they exist and
    // re-apply if the camera count changes (for multi-camera rigs).
    void Update()
    {
        if (!applyToAllPerceptionCameras)
        {
            if (!applied) TryApply();
            return;
        }

        int currentCount = FindObjectsByType<PerceptionCamera>(FindObjectsSortMode.None).Length;
        if (!applied || currentCount != appliedPerceptionCameraCount)
            TryApply();
    }

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
        if (applyToAllPerceptionCameras)
        {
            var pcs = FindObjectsByType<PerceptionCamera>(FindObjectsSortMode.None);
            if (pcs == null || pcs.Length == 0) return;
            ApplyToAll(pcs);
            appliedPerceptionCameraCount = pcs.Length;
            applied = pcs.Length > 0;
            return;
        }

        if (cam == null)
        {
            var pc = FindFirstObjectByType<PerceptionCamera>();
            if (pc != null) cam = pc.GetComponent<Camera>();
        }
        if (cam == null) return;
        ApplyToCamera(cam);
        applied = true;
    }

    [ContextMenu("Apply Resolution")]
    void Apply()
    {
        if (applyToAllPerceptionCameras)
        {
            var pcs = FindObjectsByType<PerceptionCamera>(FindObjectsSortMode.None);
            if (pcs == null || pcs.Length == 0)
            {
                Debug.LogWarning("[CaptureResolution] no PerceptionCamera found.");
                return;
            }
            ApplyToAll(pcs);
            return;
        }

        if (cam == null)
        {
            var pc = FindFirstObjectByType<PerceptionCamera>();
            cam = pc != null ? pc.GetComponent<Camera>() : null;
        }
        if (cam == null) { Debug.LogWarning("[CaptureResolution] no PerceptionCamera found."); return; }
        ApplyToCamera(cam);
    }

    void ApplyToAll(PerceptionCamera[] pcs)
    {
        foreach (var pc in pcs)
        {
            if (pc == null) continue;
            var targetCam = pc.GetComponent<Camera>();
            if (targetCam != null)
                ApplyToCamera(targetCam);
        }
        appliedPerceptionCameraCount = pcs.Length;
        applied = pcs.Length > 0;
    }

    void ApplyToCamera(Camera targetCam)
    {
        if (targetCam == null) return;

        renderTargets.TryGetValue(targetCam, out var old);
        var rt = new RenderTexture(Mathf.Max(16, width), Mathf.Max(16, height), 24)
        {
            name = $"Capture_{targetCam.name}_{width}x{height}"
        };
        rt.Create();
        targetCam.targetTexture = rt;
        renderTargets[targetCam] = rt;
        DestroyRT(old);
        Debug.Log($"[CaptureResolution] capture size = {width}x{height} on '{targetCam.name}'.");
    }

    void OnDestroy()
    {
        foreach (var kv in renderTargets)
        {
            if (kv.Key != null && kv.Key.targetTexture == kv.Value)
                kv.Key.targetTexture = null;
            DestroyRT(kv.Value);
        }
        renderTargets.Clear();
    }

    static void DestroyRT(RenderTexture t)
    {
        if (t == null) return;
        t.Release();
        if (Application.isPlaying) Destroy(t); else DestroyImmediate(t);
    }
}
