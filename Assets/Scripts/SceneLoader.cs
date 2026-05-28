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
                            default:
                                pose.rotationOffset = Vector3.zero;
                                break;
                        }

                        Debug.Log($"[SceneLoader] POSE: {obj.id} ({obj.type}) → {pose.topic} " +
                                  $"| rotationOffset: {pose.rotationOffset}");
                        break;

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

                    case ControlMode.Physics:

                        SimpleController sc = spawned.AddComponent<SimpleController>();
                        sc.waypointTopic    = $"/{obj.id}/waypoint";
                        sc.poseTopic        = $"/{obj.id}/actual_pose";
                        sc.objectId         = obj.id;

                        switch (obj.type.ToLower())
                        {
                            case "sailboat":
                                sc.mass          = 800f;
                                sc.linearDrag    = 0.5f;
                                sc.angularDrag   = 5.0f;
                                sc.maxForce      = 5000f;
                                sc.maxTurnRate   = 0.8f;
                                sc.maxSpeed      = 10f;
                                sc.driveKp       = 2000f;
                                sc.forwardOffset = new Vector3(0f, 180f, 0f);
                                break;
                            case "catamaran":
                                sc.mass          = 600f;
                                sc.linearDrag    = 0.5f;
                                sc.angularDrag   = 5.0f;
                                sc.maxForce      = 3000f;
                                sc.maxTurnRate   = 0.8f;
                                sc.maxSpeed      = 8f;
                                sc.driveKp       = 1500f;
                                break;
                            case "buoy":
                                sc.mass          = 200f;
                                sc.linearDrag    = 1.0f;
                                sc.angularDrag   = 5.0f;
                                sc.maxForce      = 800f;
                                sc.maxTurnRate   = 0.5f;
                                sc.maxSpeed      = 3f;
                                sc.driveKp       = 800f;
                                break;
                        }

                        Debug.Log($"[SceneLoader] PHYSICS: {obj.id} ({obj.type})" +
                                  $" | waypoint: {sc.waypointTopic}" +
                                  $" | mass: {sc.mass}kg" +
                                  $" | drag: {sc.linearDrag}");
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

    // Searches all children recursively — handles CameraTarget nested
    // anywhere inside the prefab hierarchy.
    Transform FindDeepChild(Transform parent, string name)
    {
        foreach (Transform child in parent.GetComponentsInChildren<Transform>())
            if (child.name == name) return child;
        return null;
    }

    void AssignCameraTarget(GameObject boat)
    {
        if (virtualCamera == null)
            virtualCamera = FindFirstObjectByType<CinemachineVirtualCamera>();

        if (virtualCamera == null)
        {
            Debug.LogError("[SceneLoader] No CinemachineVirtualCamera found!");
            return;
        }

        // Find CameraTarget anywhere in the prefab hierarchy
        Transform target = FindDeepChild(boat.transform, "Sailboat_Sail_Baked_(Skin)");

        if (target == null)
        {
            // Not found — create one above the boat root
            GameObject ct = new GameObject("CameraTarget");
            ct.transform.SetParent(boat.transform);
            ct.transform.localPosition = new Vector3(0f, 5f, 0f);
            target = ct.transform;
            Debug.Log("[SceneLoader] CameraTarget not found — created at Y+5 above boat root");
        }

        // Assign follow and look-at targets
        virtualCamera.Follow = target;
        virtualCamera.LookAt = target;
        virtualCamera.Priority = 1000;
        virtualCamera.enabled = true;

        // Transposer: offset relative to boat's local rotation
        // -Z = always behind the bow regardless of heading or start position
        var transposer = virtualCamera.GetCinemachineComponent<CinemachineTransposer>();
        if (transposer == null)
            transposer = virtualCamera.AddCinemachineComponent<CinemachineTransposer>();

        transposer.m_FollowOffset = new Vector3(0f, 3f, -15f);
        transposer.m_BindingMode  = CinemachineTransposer.BindingMode.LockToTargetWithWorldUp;
        transposer.m_XDamping     = 1f;
        transposer.m_YDamping     = 1f;
        transposer.m_ZDamping     = 10f;

        // Composer: look slightly above the target so we see the sail
        var composer = virtualCamera.GetCinemachineComponent<CinemachineComposer>();
        if (composer != null)
            composer.m_TrackedObjectOffset = new Vector3(0f, 2f, 0f);

        // Force Cinemachine to warp instantly to the boat on first frame
        virtualCamera.OnTargetObjectWarped(
            target, target.position - virtualCamera.transform.position);
        virtualCamera.InternalUpdateCameraState(Vector3.up, Time.deltaTime);

        Debug.Log($"[SceneLoader] Camera → {boat.name} | target: {target.name}" +
                  $" | offset: (0, 3, -15) | LockToTargetWithWorldUp");
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