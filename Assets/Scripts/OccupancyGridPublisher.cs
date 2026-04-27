using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;
using RosMessageTypes.Std;
using RosMessageTypes.BuiltinInterfaces; 
using System.Collections.Generic;

public class OccupancyGridPublisher : MonoBehaviour
{
    [Header("Config")]
    public float publishRate = 2f;
    public string topic = "/unity/all_poses";

    private ROSConnection ros;
    private float timer;
    private SceneLoader sceneLoader;

    private static readonly string[] TrackedIds = {
        "sailboat_01", "catamaran_01", "catamaran_02",
        "buoy_01", "buoy_02", "buoy_03"
    };

    void Start()
    {
        ros         = ROSConnection.GetOrCreateInstance();
        sceneLoader = FindFirstObjectByType<SceneLoader>();

        ros.RegisterPublisher<PoseArrayMsg>(topic);
        Debug.Log($"[OccupancyGridPublisher] Publishing poses → {topic}");
    }

    void Update()
    {
        timer += Time.deltaTime;
        if (timer < 1f / publishRate) return;
        timer = 0f;
        PublishPoses();
    }

    void PublishPoses()
    {
        if (sceneLoader == null) return;

        var poses = new List<PoseMsg>();

        foreach (string id in TrackedIds)
        {
            GameObject obj = sceneLoader.GetSpawnedObject(id);
            if (obj == null) continue;

            Vector3    p = obj.transform.position;
            Quaternion r = obj.transform.rotation;

            poses.Add(new PoseMsg
            {
                position    = new PointMsg(p.x, p.y, p.z),
                orientation = new QuaternionMsg(r.x, r.y, r.z, r.w)
            });
        }

        var msg = new PoseArrayMsg
        {
            header = new HeaderMsg
            {
                frame_id = "world",
                stamp    = new TimeMsg
                {
                    sec     = (int)Time.time,
                    nanosec = 0
                }
            },
            poses = poses.ToArray()
        };

        ros.Publish(topic, msg);
    }
}