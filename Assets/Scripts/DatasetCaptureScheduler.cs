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
    [Tooltip("ROS topic (std_msgs/Float32): set capture rate in Hz for the next/current recording.")]
    public string captureRateTopic = "/dataset/capture_hz";
    [Tooltip("ROS topic (std_msgs/String): current scenario metadata as JSON.")]
    public string scenarioInfoTopic = "/dataset/scenario_info";
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
    private string           cameraKey;
    private int              captureRequests;
    private bool             warnedMissingSolo;

    void Awake()
    {
        perceptionCamera = GetComponent<PerceptionCamera>();
        cameraKey = RunMetadata.ResolveCameraKey(perceptionCamera);
        Debug.Log($"[DatasetCapture:{cameraKey}] Awake — PerceptionCamera found: {perceptionCamera != null}");
    }

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<BoolMsg>(controlTopic, OnControl);
        ros.Subscribe<Float32Msg>(captureRateTopic, OnCaptureRate);
        ros.Subscribe<StringMsg>(scenarioInfoTopic, OnScenarioInfo);
        ros.RegisterPublisher<Int32Msg>(framesTopic);
        UnityDefaultsDump.WriteOnce(perceptionCamera);
        Debug.Log($"[DatasetCapture:{cameraKey}] Ready. ROS '{controlTopic}' (true=start/false=stop), " +
                  $"hotkey '{toggleKey}', rate {captureHz} Hz, persistentDataPath='{Application.persistentDataPath}'.");

        if (excludeOwnVessel)
        {
            // Labeling sits on the boat root; this camera is a child of it.
            UnityEngine.Perception.GroundTruth.LabelManagement.Labeling own = GetComponentInParent<UnityEngine.Perception.GroundTruth.LabelManagement.Labeling>();
            if (own != null)
            {
                own.labels.Clear();
                own.RefreshLabeling();   // no labels -> not captured by any labeler
                Debug.Log($"[DatasetCapture:{cameraKey}] Cleared ego-vessel labels on '{own.name}' (won't self-label).");
            }
        }
    }

    void OnControl(BoolMsg msg) => SetRecording(msg.data);
    void OnScenarioInfo(StringMsg msg) => ScenarioMetadataContext.SetCurrentFromJson(msg.data);
    void OnCaptureRate(Float32Msg msg)
    {
        if (msg.data <= 0f)
        {
            Debug.LogWarning($"[DatasetCapture:{cameraKey}] Ignoring invalid capture rate {msg.data} Hz.");
            return;
        }
        captureHz = msg.data;
        Debug.Log($"[DatasetCapture:{cameraKey}] captureHz set to {captureHz:F2} Hz via ROS.");
    }

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
        captureRequests++;
        frameCount++;
        ros.Publish(framesTopic, new Int32Msg(frameCount));

        if (!warnedMissingSolo && captureRequests >= 3 && !RunMetadata.TryGetLatestSoloDir(out _))
        {
            warnedMissingSolo = true;
            Debug.LogWarning(
                $"[DatasetCapture:{cameraKey}] Requested {captureRequests} captures, but no SOLO dataset folder exists yet under " +
                $"'{Application.persistentDataPath}'. Check that this camera's PerceptionCamera is enabled and uses Capture Trigger Mode = Manual."
            );
        }
    }

    void SetRecording(bool on)
    {
        if (on == capturing) return;
        capturing = on;
        timer = 0f;
        if (on)
        {
            frameCount = 0;
            captureRequests = 0;
            warnedMissingSolo = false;
            recordStartTime = Time.time;
            UnityDefaultsDump.FlushToSolo();
            ScenarioMetadataContext.WriteSnapshot("start", perceptionCamera);
            Debug.Log($"[DatasetCapture:{cameraKey}] ▶ START recording at {captureHz} Hz.");
        }
        else
        {
            float elapsed = Mathf.Max(1e-3f, Time.time - recordStartTime);
            string soloDir = RunMetadata.TryGetLatestSoloDir(out string latestSolo) ? latestSolo : "(none)";
            Debug.Log($"[DatasetCapture:{cameraKey}] ■ STOP — {frameCount} frames in {elapsed:F1}s " +
                      $"= {frameCount / elapsed:F1} Hz actual (target {captureHz}), soloDir={soloDir}.");
            UnityDefaultsDump.FlushToSolo();
            RunMetadata.Write(perceptionCamera, captureHz, frameCount / elapsed, frameCount, elapsed);
            ScenarioMetadataContext.WriteSnapshot("end", perceptionCamera);
        }
    }
}
