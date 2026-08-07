using System.Globalization;
using System.IO;
using System.Xml;
using UnityEngine;
using UnityEngine.Perception.GroundTruth;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Std;

// Mounts the Perception camera at the URDF-defined pose (base_link -> camera_link joint origin),
// writing the camera's local transform so it still moves with the boat. Auto-targets the scene's
// PerceptionCamera (which the boat spawns at runtime); can sit on any persistent object.
// Source priority: /robot_description topic > urdfAsset > urdfFilePath.
public class UrdfCameraPose : MonoBehaviour
{
    [Header("Target")]
    [Tooltip("Camera to pose. Leave empty to auto-find the PerceptionCamera (the capture sensor).")]
    public Transform cameraTransform;
    public string cameraLinkName = "camera_link";

    // last applied mount (ROS convention), for run metadata
    [System.NonSerialized] public Vector3 MountXyz;
    [System.NonSerialized] public Vector3 MountRpy;

    private bool applied;

    [Header("URDF source")]
    [Tooltip("URDF as a TextAsset (drag config/usv.urdf renamed .txt/.xml here). Optional.")]
    public TextAsset urdfAsset;
    [Tooltip("Path to the URDF file, relative to the project root (or absolute).")]
    public string urdfFilePath = "config/usv.urdf";
    [Tooltip("Optional ROS topic (std_msgs/String) carrying the URDF — overrides the file.")]
    public string robotDescriptionTopic = "/robot_description";
    public bool subscribeRobotDescription = true;

    void Start()
    {
        if (subscribeRobotDescription && !string.IsNullOrEmpty(robotDescriptionTopic))
        {
            var ros = ROSConnection.GetOrCreateInstance();
            ros.Subscribe<StringMsg>(robotDescriptionTopic, m => { applied = false; TryApply(); });
        }
        TryApply();
    }

    // The boat (and its PerceptionCamera) spawns at runtime, so keep trying until it exists.
    void Update()
    {
        if (!applied) TryApply();
    }

    void TryApply()
    {
        Transform cam = ResolveCamera();
        if (cam == null) return;                     // sensor not spawned yet
        string urdf = LoadUrdfText();
        if (string.IsNullOrEmpty(urdf)) return;
        ApplyFromUrdf(urdf, cam);
        applied = true;
    }

    Transform ResolveCamera()
    {
        if (cameraTransform != null) return cameraTransform;
        var pc = FindFirstObjectByType<PerceptionCamera>();
        return pc != null ? pc.transform : null;
    }

    [ContextMenu("Apply URDF Now")]
    void ApplyNow()
    {
        applied = false;
        TryApply();
    }

    string LoadUrdfText()
    {
        if (urdfAsset != null) return urdfAsset.text;

        // Resolve relative to the project root (parent of Assets/).
        string path = urdfFilePath;
        if (!Path.IsPathRooted(path))
            path = Path.Combine(Application.dataPath, "..", urdfFilePath);
        if (File.Exists(path)) return File.ReadAllText(path);

        Debug.LogWarning($"[UrdfCameraPose] URDF not found (asset unset, no file at '{path}').");
        return null;
    }

    void ApplyFromUrdf(string urdfText, Transform cam)
    {
        try
        {
            var doc = new XmlDocument();
            doc.LoadXml(urdfText);

            XmlNode origin = null;
            foreach (XmlNode joint in doc.GetElementsByTagName("joint"))
            {
                var child = joint.SelectSingleNode("child") as XmlElement;
                if (child != null && child.GetAttribute("link") == cameraLinkName)
                {
                    origin = joint.SelectSingleNode("origin");
                    break;
                }
            }
            if (origin is not XmlElement o)
            {
                Debug.LogWarning($"[UrdfCameraPose] no joint with child '{cameraLinkName}' in the URDF.");
                return;
            }

            Vector3 xyz = ParseTriple(o.GetAttribute("xyz"), Vector3.zero);
            Vector3 rpy = ParseTriple(o.GetAttribute("rpy"), Vector3.zero);
            MountXyz = xyz; MountRpy = rpy;

            cam.localPosition = RosToUnityPosition(xyz);
            cam.localRotation = RosRpyToUnityRotation(rpy);
            bool isSensor = cam.GetComponent<PerceptionCamera>() != null;
            Debug.Log($"[UrdfCameraPose] posed '{cam.name}' (PerceptionCamera={isSensor}) from URDF — " +
                      $"xyz(ros)={xyz}, rpy(ros)={rpy} -> world pos={cam.position}, world rot={cam.eulerAngles}.");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[UrdfCameraPose] failed to parse URDF: {e.Message}");
        }
    }

    // ---- ROS (x fwd, y left, z up) -> Unity (x right, y up, z fwd) ----

    static Vector3 RosToUnityPosition(Vector3 ros) =>
        new Vector3(-ros.y, ros.z, ros.x);

    // rpy -> Unity rotation via a basis change that also flips handedness.
    static Quaternion RosRpyToUnityRotation(Vector3 rpy)
    {
        float[,] R = RpyToMatrix(rpy.x, rpy.y, rpy.z);          // ROS rotation matrix
        float[,] C = { { 0, -1, 0 }, { 0, 0, 1 }, { 1, 0, 0 } }; // ROS basis -> Unity basis
        float[,] Ru = Mul(Mul(C, R), Transpose(C));            // R_unity = C R C^T

        // Camera local +Z (forward) and +Y (up) as columns of R_unity.
        Vector3 fwd = new Vector3(Ru[0, 2], Ru[1, 2], Ru[2, 2]);
        Vector3 up  = new Vector3(Ru[0, 1], Ru[1, 1], Ru[2, 1]);
        return Quaternion.LookRotation(fwd, up);
    }

    static float[,] RpyToMatrix(float r, float p, float y)
    {
        float cr = Mathf.Cos(r), sr = Mathf.Sin(r);
        float cp = Mathf.Cos(p), sp = Mathf.Sin(p);
        float cy = Mathf.Cos(y), sy = Mathf.Sin(y);
        // R = Rz(y) * Ry(p) * Rx(r)
        return new float[,]
        {
            { cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr },
            { sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr },
            { -sp,     cp * sr,                cp * cr },
        };
    }

    static float[,] Mul(float[,] a, float[,] b)
    {
        var m = new float[3, 3];
        for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++)
                m[i, j] = a[i, 0] * b[0, j] + a[i, 1] * b[1, j] + a[i, 2] * b[2, j];
        return m;
    }

    static float[,] Transpose(float[,] a) =>
        new float[,] { { a[0, 0], a[1, 0], a[2, 0] },
                       { a[0, 1], a[1, 1], a[2, 1] },
                       { a[0, 2], a[1, 2], a[2, 2] } };

    static Vector3 ParseTriple(string s, Vector3 fallback)
    {
        if (string.IsNullOrWhiteSpace(s)) return fallback;
        var p = s.Split(new[] { ' ', '\t' }, System.StringSplitOptions.RemoveEmptyEntries);
        if (p.Length != 3) return fallback;
        return new Vector3(
            float.Parse(p[0], CultureInfo.InvariantCulture),
            float.Parse(p[1], CultureInfo.InvariantCulture),
            float.Parse(p[2], CultureInfo.InvariantCulture));
    }
}
