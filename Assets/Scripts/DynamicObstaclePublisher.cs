using System.Collections.Generic;
using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.N3New;

// Publishes every SceneBuilder-spawned object (ego boat + static buoys) as a TrackArray on
// /scene/objects: id, type, pose, velocity. Complements /sim/tracks (procedural traffic).
// Map-layer convention: Unity x -> ROS x, Unity z -> ROS y, Unity y = 0; forward -> ENU yaw.
// Scene-object ids start at 9000 so they don't collide with generator track ids.
public class DynamicObstaclePublisher : MonoBehaviour
{
    [Header("ROS")]
    public string topic   = "/scene/objects";
    public string frameId = "map";

    [Header("Rate")]
    public float publishRate = 10f;   // Hz

    private class SceneObject
    {
        public uint      id;
        public byte      type;      // n3_new_msgs/Track type constant
        public Transform tf;
        public bool      dynamic;   // compute velocity if true
        public Vector3   lastPos;
    }

    private readonly List<SceneObject> objects = new List<SceneObject>();
    private ROSConnection ros;
    private float accumulator;

    // Register every spawned object. Called by SceneBuilder.
    public void SetObjects(List<(string name, byte type, Transform tf, bool dynamic)> sceneObjects)
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<TrackArrayMsg>(topic);
        objects.Clear();

        uint nextId = 9000;
        foreach (var o in sceneObjects)
        {
            if (o.tf == null) continue;
            objects.Add(new SceneObject
            {
                id = nextId, type = o.type, tf = o.tf,
                dynamic = o.dynamic, lastPos = o.tf.position
            });
            Debug.Log($"[SceneObjects] id {nextId} = {o.name} (type {o.type})");
            nextId++;
        }
        Debug.Log($"[SceneObjects] Publishing {objects.Count} scene objects on '{topic}' " +
                  $"at {publishRate} Hz.");
    }

    void Update()
    {
        if (objects.Count == 0 || publishRate <= 0f) return;
        accumulator += Time.deltaTime;
        float interval = 1f / publishRate;
        if (accumulator < interval) return;
        float dt = accumulator;
        accumulator = 0f;
        Publish(dt);
    }

    void Publish(float dt)
    {
        List<TrackMsg> tracks = new List<TrackMsg>(objects.Count);
        foreach (SceneObject o in objects)
        {
            if (o.tf == null) continue;
            Vector3 p = o.tf.position;

            TrackMsg t = new TrackMsg();
            t.id   = o.id;
            t.type = o.type;
            t.pose.position.x = p.x;   // Unity x -> ROS x
            t.pose.position.y = p.z;   // Unity z -> ROS y
            t.pose.position.z = 0.0;

            Vector3 f = o.tf.forward;
            float yaw = Mathf.Atan2(f.z, f.x);   // ENU yaw (East = 0, North = +y)
            t.pose.orientation.z = Mathf.Sin(yaw / 2f);
            t.pose.orientation.w = Mathf.Cos(yaw / 2f);

            if (o.dynamic && dt > 0f)
            {
                Vector3 v = (p - o.lastPos) / dt;
                t.twist.linear.x = v.x;   // Unity x -> ROS x
                t.twist.linear.y = v.z;   // Unity z -> ROS y
            }
            o.lastPos = p;

            tracks.Add(t);
        }

        TrackArrayMsg msg = new TrackArrayMsg();
        msg.header.frame_id = frameId;
        msg.tracks = tracks.ToArray();
        ros.Publish(topic, msg);
    }
}
