using UnityEngine;
using UnityEngine.Rendering.HighDefinition;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Nav;
using RosMessageTypes.Std;
using RosMessageTypes.BuiltinInterfaces;
using System.IO;
using System.Collections;

/// <summary>
/// Generates a static 2D occupancy map of the scene after SceneLoader finishes.
/// Raycasts from above across a 1000x1000m grid, classifies hits as:
///   - Land/Island  → occupied (100)
///   - Buoy (fixed) → occupied (100)
///   - Water/sky    → free (0)
///
/// Publishes on /map as nav_msgs/OccupancyGrid (ROS2 Nav2 standard).
/// Saves map.pgm + map.yaml to recordings/session_<timestamp>/
/// </summary>
public class MapGenerator : MonoBehaviour
{
    [Header("Map Settings")]
    public float mapWidth      = 1000f;   // metres
    public float mapHeight     = 1000f;   // metres
    public float resolution    = 1.0f;    // metres per cell
    public float raycastHeight = 500f;    // height to cast rays from
    public Vector3 mapOrigin   = new Vector3(-500f, 0f, -500f); // bottom-left corner

    [Header("ROS2")]
    public string mapTopic = "/map";

    [Header("Export")]
    public bool saveToFile = true;

    // computed
    private int gridWidth;
    private int gridHeight;
    private sbyte[] mapData;

    private ROSConnection ros;

    void Start()
    {
        gridWidth  = Mathf.RoundToInt(mapWidth  / resolution);
        gridHeight = Mathf.RoundToInt(mapHeight / resolution);
        mapData    = new sbyte[gridWidth * gridHeight];

        ros = ROSConnection.GetOrCreateInstance();
        ros.RegisterPublisher<OccupancyGridMsg>(mapTopic);

        // wait for SceneLoader to finish spawning all objects
        StartCoroutine(GenerateAfterSceneLoad());
    }

    IEnumerator GenerateAfterSceneLoad()
    {
        // wait two frames — SceneLoader runs in Start() frame 0
        // RuntimeWeather installs in frame 1
        // frame 2 everything is settled
        yield return null;
        yield return null;

        Debug.Log("[MapGenerator] Starting map generation...");
        GenerateMap();
        PublishMap();

        if (saveToFile)
            SaveMapFiles();
    }

    void GenerateMap()
    {
        int occupied = 0;

        for (int row = 0; row < gridHeight; row++)
        {
            for (int col = 0; col < gridWidth; col++)
            {
                // world position of this cell centre
                float worldX = mapOrigin.x + (col + 0.5f) * resolution;
                float worldZ = mapOrigin.z + (row + 0.5f) * resolution;

                Vector3 origin    = new Vector3(worldX, raycastHeight, worldZ);
                Vector3 direction = Vector3.down;

                int cellIndex = row * gridWidth + col;

                if (Physics.Raycast(origin, direction, out RaycastHit hit, raycastHeight * 2f))
                {
                    string hitName = hit.collider.gameObject.name.ToLower();
                    string hitParent = hit.collider.transform.root.gameObject.name.ToLower();

                    // classify the hit
                    if (IsLand(hitName, hitParent))
                    {
                        mapData[cellIndex] = 100;   // occupied
                        occupied++;
                    }
                    else if (IsStaticObstacle(hitName, hitParent))
                    {
                        mapData[cellIndex] = 100;   // occupied
                        occupied++;
                    }
                    else
                    {
                        mapData[cellIndex] = 0;     // free (water)
                    }
                }
                else
                {
                    mapData[cellIndex] = 0;         // free (open water, nothing hit)
                }
            }
        }

        Debug.Log($"[MapGenerator] Map generated:" +
                  $"\n  Grid     : {gridWidth}x{gridHeight} cells" +
                  $"\n  Coverage : {mapWidth}x{mapHeight}m" +
                  $"\n  Occupied : {occupied} cells" +
                  $"\n  Free     : {gridWidth * gridHeight - occupied} cells");
    }

bool IsLand(string name, string rootName)
{
    bool result = name.Contains("island")   ||
                  name.Contains("terrain")  ||
                  name.Contains("ground")   ||
                  name.Contains("shore")    ||
                  name.Contains("coast")    ||
                  name.Contains("rock")     ||
                  rootName.Contains("island");

    if (!result)
        Debug.Log($"[MapGenerator] unclassified hit: name={name} root={rootName}");

    return result;
}

    bool IsStaticObstacle(string name, string rootName)
    {
        // only fixed buoys — not the dynamic sailboat/catamaran
        return (name.Contains("buoy") || rootName.Contains("buoy")) &&
               !name.Contains("sailboat") &&
               !name.Contains("catamaran");
    }

    void PublishMap()
    {
        var msg = new OccupancyGridMsg();

        // header
        msg.header = new HeaderMsg
        {
            stamp    = new TimeMsg { sec = (int)Time.time, nanosec = 0 },
            frame_id = "map"
        };

        // metadata
        msg.info = new MapMetaDataMsg
        {
            map_load_time = new TimeMsg { sec = (int)Time.time, nanosec = 0 },
            resolution    = resolution,
            width         = (uint)gridWidth,
            height        = (uint)gridHeight,
            origin        = new RosMessageTypes.Geometry.PoseMsg
            {
                position = new RosMessageTypes.Geometry.PointMsg
                {
                    x = mapOrigin.x,
                    y = mapOrigin.z,   // ROS uses Y for what Unity calls Z
                    z = 0.0
                },
                orientation = new RosMessageTypes.Geometry.QuaternionMsg
                {
                    x = 0, y = 0, z = 0, w = 1
                }
            }
        };

        // map data — convert sbyte[] to int[]
        // ROS2 OccupancyGrid uses int8[]
        msg.data = mapData;

        ros.Publish(mapTopic, msg);

        Debug.Log($"[MapGenerator] Published /map → {gridWidth}x{gridHeight}" +
                  $" resolution={resolution}m/cell");
    }

    void SaveMapFiles()
    {
        string timestamp = System.DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");

        // find the recordings folder by going up from Assets
        string assetsPath    = Application.dataPath;
        string projectPath   = Directory.GetParent(assetsPath).FullName;
        string recordingsDir = Path.Combine(projectPath, "recordings");

        // create recordings dir if it doesn't exist
        if (!Directory.Exists(recordingsDir))
            Directory.CreateDirectory(recordingsDir);

        string sessionDir = Path.Combine(recordingsDir, $"map_{timestamp}");
        Directory.CreateDirectory(sessionDir);

        Debug.Log($"[MapGenerator] Saving to: {sessionDir}");

        SavePGM(sessionDir);
        SaveYAML(sessionDir);

        Debug.Log($"[MapGenerator] Map saved to:\n{sessionDir}");
    }

    void SavePGM(string dir)
    {
        string path = Path.Combine(dir, "map.pgm");

        using (var writer = new BinaryWriter(File.Open(path, FileMode.Create)))
        {
            // PGM header (ASCII)
            string header = $"P5\n{gridWidth} {gridHeight}\n255\n";
            writer.Write(System.Text.Encoding.ASCII.GetBytes(header));

            // PGM data — write rows top to bottom
            // ROS convention: row 0 = bottom of map
            // PGM convention: row 0 = top of image
            // so we flip vertically
            for (int row = gridHeight - 1; row >= 0; row--)
            {
                for (int col = 0; col < gridWidth; col++)
                {
                    int cellIndex = row * gridWidth + col;
                    sbyte val     = mapData[cellIndex];

                    // convert occupancy to greyscale
                    // 100 (occupied) → 0   (black)
                    // 0   (free)     → 255 (white)
                    // -1  (unknown)  → 128 (grey)
                    byte pixel;
                    if      (val == 100) pixel = 0;
                    else if (val == 0)   pixel = 255;
                    else                 pixel = 128;

                    writer.Write(pixel);
                }
            }
        }

        Debug.Log($"[MapGenerator] Saved map.pgm ({gridWidth}x{gridHeight})");
    }

    void SaveYAML(string dir)
    {
        string path = Path.Combine(dir, "map.yaml");

        string yaml = $@"image: map.pgm
resolution: {resolution}
origin: [{mapOrigin.x}, {mapOrigin.z}, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
";
        File.WriteAllText(path, yaml);
        Debug.Log($"[MapGenerator] Saved map.yaml");
    }
}