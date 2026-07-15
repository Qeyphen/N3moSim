using UnityEngine;
using Unity.Cinemachine;
using System.IO;
using System.Collections.Generic;

[System.Serializable]
public class EnvironmentConfig
{
    public float  wind_speed;
    public float  wave_height;
    public string time_of_day;
}

public enum ControlMode { Manual, Auto }

[System.Serializable]
public class ObjectConfig
{
    public string  id;
    public string  type;
    public bool    dynamic;
    public string  ros2_topic;
    public string  control_mode;   // "manual" | "auto" (dynamic objects only)
    public float[] position;
    public float[] rotation;
}

[System.Serializable]
public class SceneConfig
{
    public EnvironmentConfig  environment;
    public List<ObjectConfig> objects;
}

public class SceneBuilder : MonoBehaviour
{
    [Header("Config")]
    public string configFileName = "Scene.json";

    [Header("Prefabs")]
    public GameObject boatPrefab;
    public GameObject buoyPrefab;

    [Header("Camera")]
    public CinemachineCamera followCamera;

    [Header("Map")]
    public OccupancyGridPublisher   gridPublisher;
    public DynamicObstaclePublisher dynamicPublisher;

    private SceneConfig                    config;
    private Dictionary<string, GameObject> spawnedObjects
        = new Dictionary<string, GameObject>();
    // Non-dynamic spawned objects (buoys) — fed to the occupancy grid as obstacles.
    private List<GameObject>               staticObstacles = new List<GameObject>();
    // Dynamic spawned objects (boats) — fed to the dynamic obstacle publisher.
    private Dictionary<string, GameObject> dynamicAgents
        = new Dictionary<string, GameObject>();

    void Start()
    {
        LoadConfig();
        if (config == null) return;
        SpawnObjects();
    }

    void LoadConfig()
    {
        string[] searchPaths = {
            Path.GetFullPath(Path.Combine(
                Application.dataPath, "..", "config", configFileName)),
        };

        string json      = null;
        string foundPath = null;

        foreach (string path in searchPaths)
        {
            if (File.Exists(path))
            {
                json      = File.ReadAllText(path);
                foundPath = path;
                break;
            }
        }

        if (json == null)
        {
            Debug.LogError("[SceneLoader] scene.json not found! Searched:\n" +
                string.Join("\n", searchPaths));
            return;
        }

        config = JsonUtility.FromJson<SceneConfig>(json);
        Debug.Log($"[SceneLoader] Loaded {config.objects.Count} objects from:\n{foundPath}");
    }

    void SpawnObjects()
    {
        var allObjects = new List<(string name, byte type, Transform tf, bool dynamic)>();
        foreach (ObjectConfig obj in config.objects)
        {
            GameObject prefab = GetPrefab(obj.type);
            if (prefab == null)
            {
                Debug.LogWarning($"[SceneLoader] No prefab for type '{obj.type}'" +
                                 $" — skipping {obj.id}");
                continue;
            }

            Vector3 pos = new Vector3(
                obj.position[0],
                obj.position[1],
                obj.position[2]
            );
            Quaternion rot = Quaternion.Euler(
                obj.rotation[0],
                obj.rotation[1],
                obj.rotation[2]
            );

            GameObject spawned = Instantiate(prefab, pos, rot);
            spawned.name       = obj.id;

            // if (obj.type.ToLower() == "boat" && followCamera != null)
            // {
            //     // Cinemachine 3: the unified "Tracking Target" is the Follow target.
            //     followCamera.Follow = spawned.transform;
            //     Debug.Log($"[SceneLoader] Camera now tracking {obj.id}");
            // }
            if (obj.type.ToLower() == "boat")
            {
                if (followCamera != null)
                {
                    followCamera.Follow = spawned.transform;
                    Debug.Log($"[SceneLoader] Camera now tracking {obj.id}");
                }

                // Rain follows the ego boat
                var env = FindAnyObjectByType<EnvironmentController>();
                if (env != null)
                {
                    var pov = spawned.GetComponentInChildren<Camera>(true);
                    env.rainFollowTarget = pov != null ? pov.transform : spawned.transform;
                    Debug.Log($"[SceneLoader] Rain following {(pov != null ? pov.name : spawned.name)}");
                }
                            }

            if (obj.dynamic)
            {
                ActivateController(spawned, obj);
                dynamicAgents[obj.id] = spawned;
            }
            else
            {
                Rigidbody rb = spawned.GetComponent<Rigidbody>();
                if (rb != null) rb.isKinematic = true;
                staticObstacles.Add(spawned);
                Debug.Log($"[SceneLoader] STATIC: {obj.id} ({obj.type}) at {pos}");
            }

            spawnedObjects[obj.id] = spawned;
            allObjects.Add((obj.id, TypeToTrackType(obj.type), spawned.transform, obj.dynamic));
        }

        Debug.Log($"[SceneLoader] Done — {spawnedObjects.Count} objects spawned.");

        // Hand the static obstacles to the occupancy grid publisher (if present).
        if (gridPublisher == null) gridPublisher = FindAnyObjectByType<OccupancyGridPublisher>();
        if (gridPublisher != null) gridPublisher.Publish(staticObstacles);

        // Hand ALL spawned objects (ego + buoys) to the scene-objects publisher (/scene/objects).
        if (dynamicPublisher == null) dynamicPublisher = FindAnyObjectByType<DynamicObstaclePublisher>();
        if (dynamicPublisher != null) dynamicPublisher.SetObjects(allObjects);
    }

    // Map a Scene.json object type to an n3_new_msgs/Track type byte (for /scene/objects).
    static byte TypeToTrackType(string type)
    {
        switch (type.ToLower())
        {
            case "boat": return RosMessageTypes.N3New.TrackMsg.SAILBOAT;
            case "buoy": return RosMessageTypes.N3New.TrackMsg.BUOY;
            default:     return RosMessageTypes.N3New.TrackMsg.UNKNOWN;
        }
    }

    // Seed control mode from config; BoatControlSwitcher owns activation.
    void ActivateController(GameObject spawned, ObjectConfig obj)
    {
        ControlMode mode = ControlMode.Manual;
        if (!string.IsNullOrEmpty(obj.control_mode) &&
            !System.Enum.TryParse(obj.control_mode, true, out mode))
        {
            Debug.LogWarning($"[SceneLoader] Unknown control_mode " +
                             $"'{obj.control_mode}' for {obj.id} — defaulting to Manual.");
            mode = ControlMode.Manual;
        }

        BoatControlSwitcher switcher = spawned.GetComponent<BoatControlSwitcher>();
        if (switcher == null) switcher = spawned.AddComponent<BoatControlSwitcher>();
        switcher.Configure(mode, $"/{obj.id}/target_pose");

        Debug.Log($"[SceneLoader] {obj.id}: control_mode seeded to {mode}");
    }

    GameObject GetPrefab(string type)
    {
        switch (type.ToLower())
        {
            case "boat": return boatPrefab;
            case "buoy": return buoyPrefab;
            default:     return null;
        }
    }

    public GameObject GetSpawnedObject(string id)
    {
        return spawnedObjects.ContainsKey(id) ? spawnedObjects[id] : null;
    }
}