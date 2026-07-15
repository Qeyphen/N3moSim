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

    private ROSConnection ros;
    private readonly Dictionary<uint, GameObject> spawned = new Dictionary<uint, GameObject>();
    private readonly Dictionary<byte, List<GameObject>> prefabsByType = new Dictionary<byte, List<GameObject>>();
    private readonly Dictionary<uint, Vector3> lastPos = new Dictionary<uint, Vector3>();
    private readonly HashSet<uint> seenThisMsg = new HashSet<uint>();

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
        if (msg.tracks == null) return;
        seenThisMsg.Clear();

        foreach (var t in msg.tracks)
        {
            seenThisMsg.Add(t.id);

            if (!spawned.TryGetValue(t.id, out GameObject go) || go == null)
            {
                GameObject prefab = PrefabFor(t.type);
                if (prefab == null) continue;
                go = Instantiate(prefab, container);
                go.name = $"track_{t.id}_{(TrackType)t.type}";
                MakeKinematic(go);
                spawned[t.id] = go;
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
    }

    GameObject PrefabFor(byte type)
    {
        if (prefabsByType.TryGetValue(type, out var list) && list.Count > 0)
            return list[Random.Range(0, list.Count)];
        return defaultPrefab;
    }

    static void MakeKinematic(GameObject go)
    {
        foreach (var rb in go.GetComponentsInChildren<Rigidbody>())
            rb.isKinematic = true;
    }
}
