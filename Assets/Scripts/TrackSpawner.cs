using System.Collections.Generic;
using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.N3New;

// Spawns and drives the scenario generator's traffic from /sim/tracks (TrackArray).
// Tracks are ROS ground truth: spawned prefabs are made kinematic and positioned directly.
// ROS ENU (x=East, y=North) -> Unity (x, 0, z).
public class TrackSpawner : MonoBehaviour
{
    // Mirrors the n3_new_msgs/Track type constants.
    public enum TrackType : byte
    {
        Unknown = 0, Sailboat = 1, Motorboat = 2, Jetski = 3, Kayak = 4, Paddleboard = 5,
        Swimmer = 6, Dinghy = 7, FishingBoat = 8, Ferry = 9, Cargo = 10, Buoy = 11,
        Debris = 12, Windsurf = 13, Kitesurf = 14, Pedalo = 15,
    }

    [System.Serializable]
    public struct TypePrefab
    {
        public TrackType type;
        public GameObject prefab;
    }

    [Header("ROS")]
    [Tooltip("Topic the scenario generator publishes TrackArray on.")]
    public string tracksTopic = "/sim/tracks";

    [Header("Prefabs")]
    [Tooltip("Fallback prefab for types without an override.")]
    public GameObject defaultPrefab;
    [Tooltip("Per-type prefabs. Repeat a type to register variants (one picked at random per spawn).")]
    public TypePrefab[] prefabOverrides;

    [Header("Container")]
    [Tooltip("Parent for spawned tracks. Defaults to this object.")]
    public Transform container;

    [Header("Heading")]
    [Tooltip("Min movement (m) before heading follows motion; below this the heading holds.")]
    public float motionHeadingThreshold = 0.05f;

    [Header("Placement")]
    [Tooltip("If enabled, normalize instantiated prefab visuals so their renderer bounds sit near the waterline.")]
    public bool normalizePrefabVisuals = true;
    [Tooltip("Vertical offset applied after normalization. Negative values let hulls sit slightly below the water surface.")]
    public float waterlineOffset = -0.25f;

    [Header("Debug (runtime)")]
    public int totalMessagesReceived;
    public int lastMessageTrackCount;
    public int activeTrackCount;
    public bool receivedAnyTracksMessage;

    private ROSConnection ros;
    private readonly Dictionary<uint, GameObject> spawned = new Dictionary<uint, GameObject>();
    private readonly Dictionary<byte, List<GameObject>> prefabsByType = new Dictionary<byte, List<GameObject>>();
    private readonly Dictionary<uint, Vector3> lastPos = new Dictionary<uint, Vector3>();
    private readonly HashSet<uint> seenThisMsg = new HashSet<uint>();
    private readonly Dictionary<byte, GameObject> fallbackPrefabs = new Dictionary<byte, GameObject>();

    void Awake()
    {
        if (container == null) container = transform;
        prefabsByType.Clear();
        if (prefabOverrides != null)
            foreach (var tp in prefabOverrides)
            {
                if (tp.prefab == null) continue;
                byte key = (byte)tp.type;
                if (!prefabsByType.TryGetValue(key, out var list))
                    prefabsByType[key] = list = new List<GameObject>();
                list.Add(tp.prefab);
            }
    }

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<TrackArrayMsg>(tracksTopic, OnTracks);
        Debug.Log($"[TrackSpawner] Subscribed to '{tracksTopic}'. default=" +
                  $"{(defaultPrefab ? defaultPrefab.name : "NONE")}, types with overrides={prefabsByType.Count}");
    }

    void OnTracks(TrackArrayMsg msg)
    {
        receivedAnyTracksMessage = true;
        totalMessagesReceived++;
        lastMessageTrackCount = msg.tracks != null ? msg.tracks.Length : 0;
        if (totalMessagesReceived == 1)
        {
            Debug.Log($"[TrackSpawner] First /sim/tracks message received. tracks={lastMessageTrackCount}");
        }

        if (msg.tracks == null)
        {
            Debug.LogWarning("[TrackSpawner] Received TrackArray with null tracks.");
            return;
        }
        seenThisMsg.Clear();

        foreach (var t in msg.tracks)
        {
            seenThisMsg.Add(t.id);

            if (!spawned.TryGetValue(t.id, out GameObject go) || go == null)
            {
                GameObject prefab = PrefabFor(t.type);
                if (prefab == null)
                {
                    Debug.LogWarning($"[TrackSpawner] No prefab for track id={t.id} type={(TrackType)t.type} ({t.type}); using fallback primitive.");
                    go = CreateFallbackInstance(t.type);
                }
                else
                {
                    go = Instantiate(prefab, container);
                    if (normalizePrefabVisuals)
                        NormalizeVisualRoot(go);
                }
                go.name = $"track_{t.id}_{(TrackType)t.type}";
                MakeKinematic(go);
                spawned[t.id] = go;
                Debug.Log($"[TrackSpawner] Spawned {go.name} prefab='{(prefab ? prefab.name : "fallback")}'");
            }

            Vector3 newPos = new Vector3(
                (float)t.pose.position.x, 0f, (float)t.pose.position.y);

            // Face the direction of travel; the yaw quaternion only seeds the first frame.
            if (lastPos.TryGetValue(t.id, out Vector3 prev))
            {
                Vector3 delta = newPos - prev;
                delta.y = 0f;
                if (delta.sqrMagnitude >= motionHeadingThreshold * motionHeadingThreshold)
                    go.transform.rotation = Quaternion.LookRotation(delta.normalized, Vector3.up);
            }
            else
            {
                float qz = (float)t.pose.orientation.z;
                float qw = (float)t.pose.orientation.w;
                float headingRad = 2f * Mathf.Atan2(qz, qw);
                Vector3 fwd = new Vector3(Mathf.Cos(headingRad), 0f, Mathf.Sin(headingRad));
                if (fwd.sqrMagnitude > 1e-6f)
                    go.transform.rotation = Quaternion.LookRotation(fwd, Vector3.up);
            }

            go.transform.position = newPos;
            lastPos[t.id] = newPos;
        }

        if (spawned.Count != seenThisMsg.Count)
        {
            var toRemove = new List<uint>();
            foreach (var kv in spawned)
                if (!seenThisMsg.Contains(kv.Key)) toRemove.Add(kv.Key);
            foreach (var id in toRemove)
            {
                if (spawned[id] != null) Destroy(spawned[id]);
                spawned.Remove(id);
                lastPos.Remove(id);
            }
        }

        activeTrackCount = spawned.Count;
    }

    GameObject PrefabFor(byte type)
    {
        if (prefabsByType.TryGetValue(type, out var list) && list.Count > 0)
            return list[Random.Range(0, list.Count)];
        return defaultPrefab;
    }

    GameObject CreateFallbackInstance(byte type)
    {
        if (!fallbackPrefabs.TryGetValue(type, out GameObject prefab) || prefab == null)
        {
            prefab = BuildFallbackPrefab(type);
            fallbackPrefabs[type] = prefab;
        }
        return Instantiate(prefab, container);
    }

    GameObject BuildFallbackPrefab(byte type)
    {
        PrimitiveType primitive = PrimitiveType.Cube;
        Color color = Color.gray;
        Vector3 scale = new Vector3(3f, 1.5f, 6f);

        switch ((TrackType)type)
        {
            case TrackType.Buoy:
                primitive = PrimitiveType.Cylinder;
                color = Color.yellow;
                scale = new Vector3(1.2f, 1.5f, 1.2f);
                break;
            case TrackType.Swimmer:
                primitive = PrimitiveType.Capsule;
                color = new Color(1f, 0.2f, 0.7f);
                scale = new Vector3(0.6f, 0.8f, 0.6f);
                break;
            case TrackType.Kayak:
            case TrackType.Paddleboard:
            case TrackType.Windsurf:
            case TrackType.Kitesurf:
                primitive = PrimitiveType.Capsule;
                color = Color.green;
                scale = new Vector3(0.8f, 0.35f, 2.2f);
                break;
            case TrackType.Jetski:
                primitive = PrimitiveType.Capsule;
                color = Color.cyan;
                scale = new Vector3(1.0f, 0.5f, 1.8f);
                break;
            case TrackType.Ferry:
            case TrackType.Cargo:
                primitive = PrimitiveType.Cube;
                color = new Color(0.4f, 0.4f, 0.45f);
                scale = new Vector3(6f, 3f, 16f);
                break;
            default:
                primitive = PrimitiveType.Cube;
                color = new Color(0.2f, 0.6f, 1f);
                scale = new Vector3(2.2f, 1.2f, 5f);
                break;
        }

        var root = new GameObject($"Fallback_{(TrackType)type}");
        root.hideFlags = HideFlags.HideAndDontSave;
        var body = GameObject.CreatePrimitive(primitive);
        body.name = "model";
        body.transform.SetParent(root.transform, false);
        body.transform.localScale = scale;
        if (primitive == PrimitiveType.Capsule)
            body.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);

        var renderer = body.GetComponent<Renderer>();
        if (renderer != null)
        {
            var mat = new Material(Shader.Find("Standard"));
            mat.color = color;
            renderer.sharedMaterial = mat;
        }

        return root;
    }

    static void MakeKinematic(GameObject go)
    {
        foreach (var rb in go.GetComponentsInChildren<Rigidbody>())
            rb.isKinematic = true;
    }

    void NormalizeVisualRoot(GameObject root)
    {
        var renderers = root.GetComponentsInChildren<Renderer>();
        if (renderers == null || renderers.Length == 0)
            return;

        bool haveBounds = false;
        Bounds worldBounds = default;
        foreach (var r in renderers)
        {
            if (!r.enabled) continue;
            if (!haveBounds)
            {
                worldBounds = r.bounds;
                haveBounds = true;
            }
            else
            {
                worldBounds.Encapsulate(r.bounds);
            }
        }
        if (!haveBounds) return;

        // Convert aggregate renderer bounds to the root's local frame so prefabs with badly
        // offset visual children still sit near the waterline when the spawner moves only the root.
        Vector3 localCenter = root.transform.InverseTransformPoint(worldBounds.center);
        Vector3 ext = root.transform.InverseTransformVector(worldBounds.extents);
        float minY = localCenter.y - Mathf.Abs(ext.y);
        float dx = -localCenter.x;
        float dz = -localCenter.z;
        float dy = -(minY - waterlineOffset);

        if (Mathf.Abs(dx) < 0.01f && Mathf.Abs(dy) < 0.01f && Mathf.Abs(dz) < 0.01f)
            return;

        foreach (Transform child in root.transform)
            child.localPosition += new Vector3(dx, dy, dz);

        Debug.Log(
            $"[TrackSpawner] Normalized prefab '{root.name}' visual offset by " +
            $"({dx:F2}, {dy:F2}, {dz:F2})"
        );
    }
}
