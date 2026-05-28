using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Sensor;
using RosMessageTypes.Std;
using RosMessageTypes.BuiltinInterfaces;
using System;

public class CameraStreamer : MonoBehaviour
{
    [Header("ROS2 Settings")]
    public string topic     = "/unity/camera/compressed";
    public int    width     = 320;
    public int    height    = 240;
    public int    fps       = 10;
    public int    jpegQuality = 75;

    private ROSConnection  ros;
    private Camera         streamCam;
    private RenderTexture  renderTex;
    private Texture2D      tex2D;
    private float          timer;
    private float          interval;

    void Start()
    {

        AudioListener al = GetComponent<AudioListener>();
        if (al != null) Destroy(al);
        
        ros      = ROSConnection.GetOrCreateInstance();
        streamCam = GetComponent<Camera>();

        if (streamCam == null)
        {
            Debug.LogError("[CameraStreamer] No Camera component found!");
            return;
        }

        // setup render texture
        renderTex = new RenderTexture(width, height, 24);
        tex2D     = new Texture2D(width, height, TextureFormat.RGB24, false);

        streamCam.targetTexture = renderTex;
        streamCam.enabled       = true;

        interval = 1f / fps;

        ros.RegisterPublisher<CompressedImageMsg>(topic);

        Debug.Log($"[CameraStreamer] Publishing {width}x{height} @ {fps}fps → {topic}");
    }

    void Update()
    {
        timer += Time.deltaTime;
        if (timer < interval) return;
        timer = 0f;
        CaptureAndPublish();
    }

    void CaptureAndPublish()
    {
        if (streamCam == null || renderTex == null) return;

        // render camera to texture
        streamCam.Render();

        // read pixels from GPU
        RenderTexture.active = renderTex;
        tex2D.ReadPixels(new Rect(0, 0, width, height), 0, 0);
        tex2D.Apply();
        RenderTexture.active = null;

        // encode to JPEG
        byte[] jpeg = tex2D.EncodeToJPG(jpegQuality);

        // build ROS message
        var msg = new CompressedImageMsg
        {
            header = new HeaderMsg
            {
                stamp = new TimeMsg
                {
                    sec     = (int)Time.time,
                    nanosec = 0
                },
                frame_id = "camera"
            },
            format = "jpeg",
            data   = jpeg
        };

        ros.Publish(topic, msg);
    }

    void OnDestroy()
    {
        if (renderTex != null) renderTex.Release();
    }
}