using System.Collections.Generic;
using System.IO;
using UnityEngine;

// Builds the visual land for a real-world lake from a costmap (realworld_scene.py output):
// reads <dir>/<name>_costmap.png + _meta.json and raises a land mesh over the land cells; the
// lake cells stay open so the existing HDRP water shows through. ROS(x,y) -> Unity(x, h, z=y).
[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class RealWorldSceneLoader : MonoBehaviour
{
    [System.Serializable]
    class Meta
    {
        public string name;
        public float resolution_m, origin_x_m, origin_y_m;
        public int width, height;
    }

    [Header("Source")]
    public string sceneName = "lake_geneva";
    public string dir = "config/realworld";     // relative to the project root

    [Header("Land mesh")]
    public float landHeight = 2f;
    [Tooltip("Downsample the grid to at most this many cells per side (keeps the mesh light).")]
    public int maxCells = 128;
    public Material landMaterial;

    void Start() => Build();

    [ContextMenu("Build Now")]
    void Build()
    {
        string basePath = Path.Combine(Application.dataPath, "..", dir, sceneName);
        if (!File.Exists(basePath + "_meta.json") || !File.Exists(basePath + "_costmap.png"))
        {
            Debug.LogWarning($"[RealWorldScene] missing {sceneName}_meta.json / _costmap.png in {dir}");
            return;
        }

        var meta = JsonUtility.FromJson<Meta>(File.ReadAllText(basePath + "_meta.json"));
        var tex = new Texture2D(2, 2);
        tex.LoadImage(File.ReadAllBytes(basePath + "_costmap.png"));   // white=land, black=water
        Color32[] px = tex.GetPixels32();
        int W = meta.width, H = meta.height;

        int step = Mathf.Max(1, Mathf.CeilToInt((float)Mathf.Max(W, H) / maxCells));
        float cell = meta.resolution_m * step;

        var verts = new List<Vector3>();
        var tris = new List<int>();
        for (int r = 0; r < H; r += step)
            for (int c = 0; c < W; c += step)
            {
                if (!BlockIsLand(px, W, H, c, r, step)) continue;   // water block -> leave open

                // ROS lower-left origin; PNG row 0 is the TOP, so flip the row for world y.
                float x = meta.origin_x_m + c * meta.resolution_m;
                float z = meta.origin_y_m + (H - 1 - r) * meta.resolution_m;
                int v = verts.Count;
                verts.Add(new Vector3(x, landHeight, z));
                verts.Add(new Vector3(x + cell, landHeight, z));
                verts.Add(new Vector3(x + cell, landHeight, z - cell));
                verts.Add(new Vector3(x, landHeight, z - cell));
                tris.AddRange(new[] { v, v + 1, v + 2, v, v + 2, v + 3 });
            }

        var mesh = new Mesh { indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
        mesh.SetVertices(verts);
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        GetComponent<MeshFilter>().sharedMesh = mesh;
        if (landMaterial != null) GetComponent<MeshRenderer>().sharedMaterial = landMaterial;

        Debug.Log($"[RealWorldScene] built '{sceneName}' land: {verts.Count / 4} blocks, cell {cell:F1} m.");
    }

    static bool BlockIsLand(Color32[] px, int W, int H, int c0, int r0, int step)
    {
        int land = 0, total = 0;
        for (int r = r0; r < Mathf.Min(r0 + step, H); r++)
            for (int c = c0; c < Mathf.Min(c0 + step, W); c++)
            {
                if (px[r * W + c].r > 127) land++;   // white = land
                total++;
            }
        return total > 0 && land * 2 >= total;       // majority land
    }
}
