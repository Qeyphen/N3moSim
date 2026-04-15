using UnityEngine;
using System.IO;
using System.Collections.Generic;
using N3mo.Weather;
using Cinemachine;

[System.Serializable]
public class EnvironmentConfig
{
    public float wind_speed;
    public float wave_height;
    public string time_of_day;
}

[System.Serializable]
public class ObjectConfig
{
    public string id;
    public string type;
    public bool dynamic;
    public string ros2_topic;
    public float[] position;
    public float[] rotation;
}

[System.Serializable]
public class SceneConfig
{
    public EnvironmentConfig environment;
    public List<ObjectConfig> objects;
}

public class SceneLoader : MonoBehaviour
{
    [Header("Config")]
    public string configFileName = "scene_config.json";

    [Header("Prefabs")]
    public GameObject sailboatPrefab;
    public GameObject buoyPrefab;
    public GameObject catamaranPrefab;

    [Header("Camera")]
    [Tooltip("Optional: drag Virtual Camera here. If empty, SceneLoader finds it automatically.")]
    public CinemachineVirtualCamera virtualCamera;

    [Header("Control Mode")]
    [Tooltip("Use Pose control (perfect circles) or Velocity control (physics-based)")]
    public bool usePoseControl = true;

    private SceneConfig config;
    private Dictionary<string, GameObject> spawnedObjects
        = new Dictionary<string, GameObject>();

    void Start()
    {
        if (virtualCamera == null)
            virtualCamera = FindFirstObjectByType<CinemachineVirtualCamera>();

        LoadConfig();
        if (config == null) return;
        ApplyEnvironment();
        SpawnObjects();
        InstallWeather();
    }

    void LoadConfig()
    {
        string[] searchPaths = {
            Path.GetFullPath(Path.Combine(
                Application.dataPath, "..", "..", "config", configFileName)),
            Path.Combine(Application.dataPath, "Config", configFileName),
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
            Debug.LogError("[SceneLoader] Config not found! Searched:\n" +
                string.Join("\n", searchPaths));
            return;
        }

        config = JsonUtility.FromJson<SceneConfig>(json);
        Debug.Log($"[SceneLoader] Loaded {config.objects.Count} objects from:\n{foundPath}");
    }

    void ApplyEnvironment()
    {
        WindZone wind = FindFirstObjectByType<WindZone>();
        if (wind != null)
            wind.windMain = config.environment.wind_speed;

        Debug.Log($"[SceneLoader] Environment applied. Wind: {config.environment.wind_speed}");
    }

    void InstallWeather()
    {
        GameObject followTarget = GetPrimaryWeatherTarget();
        RuntimeWeatherInstaller.Install(config, followTarget);
        Debug.Log("[SceneLoader] Runtime weather installed.");
    }

    void SpawnObjects()
    {
        foreach (ObjectConfig obj in config.objects)
        {
            GameObject prefab = GetPrefab(obj.type);
            if (prefab == null)
            {
                Debug.LogWarning($"[SceneLoader] No prefab for type: {obj.type}. Skipping {obj.id}.");
                continue;
            }

            Vector3    pos     = new Vector3(obj.position[0], obj.position[1], obj.position[2]);
            Quaternion rot     = Quaternion.Euler(obj.rotation[0], obj.rotation[1], obj.rotation[2]);
            GameObject spawned = Instantiate(prefab, pos, rot);
            spawned.name       = obj.id;

            if (obj.dynamic)
            {
                Rigidbody rb = spawned.GetComponent<Rigidbody>();

                if (usePoseControl)
                {
                    // ── POSE CONTROL ──────────────────────────────
                    // Boat teleports to exact ROS position
                    // Perfect circles, no physics drift, no backwards movement
                    if (rb != null)
                    {
                        rb.isKinematic = true;
                        rb.useGravity  = false;
                    }

                    PoseController pose = spawned.AddComponent<PoseController>();
                    pose.topic          = $"/{obj.id}/pose";
                    pose.objectId       = obj.id;

                    Debug.Log($"[SceneLoader] POSE: {obj.id} → {pose.topic}");
                }
                else
                {
                    // ── VELOCITY CONTROL ──────────────────────────
                    // Physics-based movement via Twist commands
                    ROSController ros = spawned.AddComponent<ROSController>();
                    ros.topic         = obj.ros2_topic;
                    ros.objectId      = obj.id;

                    switch (obj.type.ToLower())
                    {
                        case "sailboat":
                            ros.useUpAsForward = false;
                            ros.invertForward  = false;
                            ros.moveSpeed      = 2f;
                            ros.turnSpeed      = 15f;
                            break;
                        case "catamaran":
                            ros.useUpAsForward = true;
                            ros.invertForward  = false;
                            ros.moveSpeed      = 2f;
                            ros.turnSpeed      = 15f;
                            break;
                        case "buoy":
                            ros.useUpAsForward = true;
                            ros.invertForward  = false;
                            ros.moveSpeed      = 1.5f;
                            ros.turnSpeed      = 10f;
                            break;
                    }

                    Debug.Log($"[SceneLoader] VELOCITY: {obj.id} ({obj.type}) → {obj.ros2_topic}");
                }

                // Assign first sailboat as Cinemachine target
                if (obj.id == "sailboat_01")
                    AssignCameraTarget(spawned);
            }
            else
            {
                Rigidbody rb = spawned.GetComponent<Rigidbody>();
                if (rb != null) rb.isKinematic = true;
                Debug.Log($"[SceneLoader] STATIC: {obj.id} at {pos}");
            }

            spawnedObjects[obj.id] = spawned;
        }

        Debug.Log($"[SceneLoader] Done. {spawnedObjects.Count} objects spawned.");
    }

    void AssignCameraTarget(GameObject boat)
    {
        if (virtualCamera == null)
        {
            Debug.LogWarning("[SceneLoader] No CinemachineVirtualCamera found!");
            return;
        }

        Transform cameraTarget = boat.transform.Find("CameraTarget");

        if (cameraTarget == null)
        {
            GameObject ct = new GameObject("CameraTarget");
            ct.transform.SetParent(boat.transform);
            ct.transform.localPosition = new Vector3(0f, 5f, 0f);
            cameraTarget = ct.transform;
            Debug.Log("[SceneLoader] Created CameraTarget at Y+5 above boat");
        }

        virtualCamera.Follow = cameraTarget;
        virtualCamera.LookAt = cameraTarget;

        Debug.Log($"[SceneLoader] Cinemachine → {boat.name} " +
                  $"(target at world pos: {cameraTarget.position})");
    }

    GameObject GetPrefab(string type)
    {
        switch (type.ToLower())
        {
            case "sailboat":  return sailboatPrefab;
            case "buoy":      return buoyPrefab;
            case "catamaran": return catamaranPrefab;
            default:          return null;
        }
    }

    public GameObject GetSpawnedObject(string id)
    {
        return spawnedObjects.ContainsKey(id) ? spawnedObjects[id] : null;
    }

    GameObject GetPrimaryWeatherTarget()
    {
        string[] preferredTargets = { "sailboat_01", "catamaran_01", "catamaran_02" };
        foreach (string id in preferredTargets)
            if (spawnedObjects.TryGetValue(id, out GameObject target) && target != null)
                return target;
        return null;
    }
}