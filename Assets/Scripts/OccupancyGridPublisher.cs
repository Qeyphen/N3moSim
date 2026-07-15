using System.Collections.Generic;
using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Nav;

// Rasterises the scene's static obstacles (buoys) into a nav_msgs/OccupancyGrid, published
// once latched on /map (so late subscribers still receive it). Uses renderer bounds, no colliders.
// Convention: Unity x -> grid column, Unity z -> grid row; data row-major (index = row*width + col).
public class OccupancyGridPublisher : MonoBehaviour
{
    [Header("ROS")]
    public string topic   = "/map";
    public string frameId = "map";

    [Header("Grid (match occupancy_grid_server params)")]
    public float originX      = -500f;   // Unity x of cell (0,0) corner -> origin_x
    public float originZ      = -500f;   // Unity z of cell (0,0) corner -> origin_y
    public float widthMeters  = 1000f;   // -> width_m
    public float heightMeters = 1000f;   // -> height_m
    public float resolution   = 1f;      // m per cell

    [Header("Rasterisation")]
    [Tooltip("Optional costmap inflation in metres (0 = off).")]
    public float inflationRadius = 0f;

    [Header("Extra static obstacles")]
    [Tooltip("Scene objects to ALSO rasterise into /map (e.g. the island) — things not " +
             "spawned by SceneBuilder. Drag them here so the scenario generator avoids them.")]
    public List<GameObject> extraObstacles = new List<GameObject>();

    private ROSConnection      ros;
    private List<GameObject>   obstacles = new List<GameObject>();

    // Rasterise + publish the given static obstacles. Called by SceneBuilder.
    public void Publish(List<GameObject> staticObstacles)
    {
        obstacles = staticObstacles ?? new List<GameObject>();
        BuildAndPublish();
    }

    [ContextMenu("Rebuild & Publish")]
    public void BuildAndPublish()
    {
        if (ros == null) ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<OccupancyGridMsg>(topic, latch: true);

        int cols = Mathf.Max(1, Mathf.CeilToInt(widthMeters  / resolution));
        int rows = Mathf.Max(1, Mathf.CeilToInt(heightMeters / resolution));
        sbyte[] data = new sbyte[cols * rows];   // 0 = free

        var all = new List<GameObject>(obstacles);
        if (extraObstacles != null) all.AddRange(extraObstacles);

        int occupied = 0;
        foreach (GameObject go in all)
        {
            if (go == null) continue;

            Bounds? bounds = WorldBounds(go);
            if (bounds == null) continue;
            Bounds b = bounds.Value;

            // Skip obstacles entirely outside the grid extent.
            if (b.max.x < originX || b.min.x > originX + widthMeters ||
                b.max.z < originZ || b.min.z > originZ + heightMeters)
                continue;

            int cx0 = Mathf.Clamp(ColOf(b.min.x), 0, cols - 1);
            int cx1 = Mathf.Clamp(ColOf(b.max.x), 0, cols - 1);
            int cy0 = Mathf.Clamp(RowOf(b.min.z), 0, rows - 1);
            int cy1 = Mathf.Clamp(RowOf(b.max.z), 0, rows - 1);

            for (int cy = cy0; cy <= cy1; cy++)
                for (int cx = cx0; cx <= cx1; cx++)
                {
                    int idx = cy * cols + cx;
                    if (data[idx] != 100) { data[idx] = 100; occupied++; }
                }
        }

        if (inflationRadius > 0f)
            data = Inflate(data, cols, rows, Mathf.RoundToInt(inflationRadius / resolution));

        ros.Publish(topic, BuildMessage(cols, rows, data));
        Debug.Log($"[OccupancyGridPublisher] Published {cols}x{rows} grid on '{topic}' " +
                  $"(res={resolution}m, {all.Count} obstacles, {occupied} occupied cells).");
    }

    // Combined world-space AABB of all renderers under the object (null if none).
    static Bounds? WorldBounds(GameObject go)
    {
        Renderer[] rends = go.GetComponentsInChildren<Renderer>();
        if (rends.Length == 0) return null;
        Bounds b = rends[0].bounds;
        for (int i = 1; i < rends.Length; i++) b.Encapsulate(rends[i].bounds);
        return b;
    }

    int ColOf(float x) => Mathf.FloorToInt((x - originX) / resolution);
    int RowOf(float z) => Mathf.FloorToInt((z - originZ) / resolution);

    OccupancyGridMsg BuildMessage(int cols, int rows, sbyte[] data)
    {
        OccupancyGridMsg msg = new OccupancyGridMsg();
        msg.header.frame_id  = frameId;
        msg.info.resolution  = resolution;
        msg.info.width       = (uint)cols;
        msg.info.height      = (uint)rows;
        msg.info.origin.position.x    = originX;   // Unity x
        msg.info.origin.position.y    = originZ;   // Unity z -> grid y
        msg.info.origin.position.z    = 0;
        msg.info.origin.orientation.w = 1.0;       // identity
        msg.data = data;
        return msg;
    }

    // Simple square (Chebyshev) dilation of occupied cells — a cheap costmap inflation.
    static sbyte[] Inflate(sbyte[] src, int cols, int rows, int radius)
    {
        if (radius <= 0) return src;
        sbyte[] dst = (sbyte[])src.Clone();
        for (int y = 0; y < rows; y++)
            for (int x = 0; x < cols; x++)
            {
                if (src[y * cols + x] != 100) continue;
                for (int dy = -radius; dy <= radius; dy++)
                    for (int dx = -radius; dx <= radius; dx++)
                    {
                        int nx = x + dx, ny = y + dy;
                        if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
                        dst[ny * cols + nx] = 100;
                    }
            }
        return dst;
    }
}
