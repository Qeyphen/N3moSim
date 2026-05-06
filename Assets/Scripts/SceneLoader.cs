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

public enum ControlMode { Pose, Velocity, Physics }

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
    [Tooltip("Pose = teleport exact position | Velocity = Twist commands | Physics = waypoint forces")]
    public ControlMode controlMode = ControlMode.Pose;

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

                switch (controlMode)
                {
                    // Teleports boat to exact position received from ROS2.
                    case ControlMode.Pose:

                        if (rb != null)
                        {
                            rb.isKinematic = true;
                            rb.useGravity  = false;
                        }

                        PoseController pose = spawned.AddComponent<PoseController>();
                        pose.topic          = $"/{obj.id}/pose";
                        pose.objectId       = obj.id;

                        switch (obj.type.ToLower())
                        {
                            case "sailboat":
                                pose.rotationOffset = new Vector3(0f, 180f, 0f);
                                break;
                            case "catamaran":
                                pose.rotationOffset = new Vector3(0f, 90f, 0f);
                                break;
                            case "buoy":
                                pose.rotationOffset = Vector3.zero;
                                break;
                            default:
                                pose.rotationOffset = Vector3.zero;
                                break;
                        }

                        Debug.Log($"[SceneLoader] POSE: {obj.id} ({obj.type}) → {pose.topic} " +
                                  $"| rotationOffset: {pose.rotationOffset}");
                        break;

                    // Moves boat using Twist (linear/angular velocity) commands.
                    // Physics-based but command-driven, can drift over time.
                    case ControlMode.Velocity:

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
                        break;

                    // Moves boat toward a waypoint using real Unity forces.
                    // Rigidbody handles acceleration, drag, momentum naturally.
                    // Waypoints sent from waypoint_publisher.py via ROS2.
                    case ControlMode.Physics:

                        PhysicsController phys = spawned.AddComponent<PhysicsController>();
                        phys.waypointTopic     = $"/{obj.id}/waypoint";
                        phys.poseTopic         = $"/{obj.id}/actual_pose";
                        phys.objectId          = obj.id;

                        switch (obj.type.ToLower())
                        {
                            case "sailboat":
                                phys.mass        = 800f;
                                phys.linearDrag  = 0.3f;
                                phys.angularDrag = 1.0f;
                                phys.maxForce    = 4000f;
                                phys.maxTorque   = 1000f;
                                phys.maxSpeed    = 6f;
                                break;
                            case "catamaran":
                                phys.mass        = 600f;
                                phys.linearDrag  = 2.0f;
                                phys.angularDrag = 2.5f;
                                phys.maxForce    = 1400f;
                                phys.maxTorque   = 700f;
                                phys.maxSpeed    = 5f;
                                break;
                            case "buoy":
                                phys.mass        = 200f;
                                phys.linearDrag  = 3.0f;
                                phys.angularDrag = 4.0f;
                                phys.maxForce    = 400f;
                                phys.maxTorque   = 200f;
                                phys.maxSpeed    = 2f;
                                break;
                        }

                        Debug.Log($"[SceneLoader] PHYSICS: {obj.id} ({obj.type})" +
                                  $" | waypoint: {phys.waypointTopic}" +
                                  $" | mass: {phys.mass}kg" +
                                  $" | drag: {phys.linearDrag}");
                        break;
                }

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

        Debug.Log($"[SceneLoader] Done. {spawnedObjects.Count} objects spawned." +
                  $" Control mode: {controlMode}");
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