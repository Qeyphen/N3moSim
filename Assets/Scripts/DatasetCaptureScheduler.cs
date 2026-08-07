using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Perception.GroundTruth;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Std;

// Records a Perception dataset on demand: captures at a fixed real-time rate (e.g. 3 Hz)
// only while recording, started/stopped via ROS (controlTopic, std_msgs/Bool) or hotkey.
// Manual capture (not Perception's Scheduled mode) is deliberate: Scheduled mode fixes the
// sim timestep and decouples from real time, which would wreck the physics-driven boat.
// Requires "Capture Trigger Mode = Manual" set on the Perception Camera in the Inspector.
[RequireComponent(typeof(PerceptionCamera))]
public class DatasetCaptureScheduler : MonoBehaviour
{
    [Header("Capture")]
    public float captureHz = 10f;   // match the scenario generator's 10 Hz
    [Tooltip("Recording right now? Toggle live in the Inspector, or via ROS / hotkey.")]
    public bool capturing = false;

    [Header("Control")]
    [Tooltip("ROS topic (std_msgs/Bool): true = start recording, false = stop.")]
    public string controlTopic = "/dataset/control";
    [Tooltip("ROS topic (std_msgs/Int32): frames captured this recording (for the sweep to stop at a target).")]
    public string framesTopic = "/dataset/frames";
    [Tooltip("Keyboard key that toggles recording on/off.")]
    public Key toggleKey = Key.R;

    [Header("Ego vessel")]
    [Tooltip("Clear the Labeling on this camera's own vessel so the boat doesn't " +
             "label its own hull as an obstacle in its captures.")]
    public bool excludeOwnVessel = true;

    private PerceptionCamera perceptionCamera;
    private ROSConnection    ros;
    private float            timer;
    private int              frameCount;
    private float            recordStartTime;

    void Awake()
    {
        perceptionCamera = GetComponent<PerceptionCamera>();
        Debug.Log($"[DatasetCapture] Awake — PerceptionCamera found: {perceptionCamera != null}");
    }

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<BoolMsg>(controlTopic, OnControl);
        ros.RegisterPublisher<Int32Msg>(framesTopic);
        Debug.Log($"[DatasetCapture] Ready. ROS '{controlTopic}' (true=start/false=stop), " +
                  $"hotkey '{toggleKey}', rate {captureHz} Hz.");

        if (excludeOwnVessel)
        {
            // Labeling sits on the boat root; this camera is a child of it.
            UnityEngine.Perception.GroundTruth.LabelManagement.Labeling own = GetComponentInParent<UnityEngine.Perception.GroundTruth.LabelManagement.Labeling>();
            if (own != null)
            {
                own.labels.Clear();
                own.RefreshLabeling();   // no labels -> not captured by any labeler
                Debug.Log($"[DatasetCapture] Cleared ego-vessel labels on '{own.name}' (won't self-label).");
            }
        }
    }

    void OnControl(BoolMsg msg) => SetRecording(msg.data);

    void Update()
    {
        if (Keyboard.current != null && Keyboard.current[toggleKey].wasPressedThisFrame)
            SetRecording(!capturing);

        if (!capturing || captureHz <= 0f || perceptionCamera == null) return;

        timer += Time.deltaTime;
        float interval = 1f / captureHz;
        if (timer < interval) return;
        timer -= interval;

        perceptionCamera.RequestCapture();
        frameCount++;
        ros.Publish(framesTopic, new Int32Msg(frameCount));
    }

    void SetRecording(bool on)
    {
        if (on == capturing) return;
        capturing = on;
        timer = 0f;
        if (on)
        {
            frameCount = 0;
            recordStartTime = Time.time;
            Debug.Log($"[DatasetCapture] ▶ START recording at {captureHz} Hz.");
        }
        else
        {
            float elapsed = Mathf.Max(1e-3f, Time.time - recordStartTime);
            Debug.Log($"[DatasetCapture] ■ STOP — {frameCount} frames in {elapsed:F1}s " +
                      $"= {frameCount / elapsed:F1} Hz actual (target {captureHz}).");
            RunMetadata.Write(perceptionCamera, captureHz, frameCount / elapsed, frameCount, elapsed);
        }
    }
}
