using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Shared mesh/prefab helpers for the procedural N3mo asset generators.
public static class AssetMeshUtil
{
    public const string Dir = "Assets/Models/Generated";

    public static Material Mat(string name, Color c, bool cullOff = false)
    {
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Models/Generated");
        var m = new Material(Shader.Find("HDRP/Lit"));
        m.SetColor("_BaseColor", c);
        if (cullOff) m.SetFloat("_CullMode", 0f);
        AssetDatabase.CreateAsset(m, $"{Dir}/{name}.mat");
        return m;
    }

    public static Mesh Save(Mesh mesh, string name)
    {
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Models/Generated");
        AssetDatabase.CreateAsset(mesh, $"{Dir}/{name}.asset");
        return mesh;
    }

    public static void MeshChild(string name, Transform parent, Mesh mesh, Material mat)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
    }

    public static void Primitive(PrimitiveType type, string name, Transform parent,
                                 Vector3 pos, Vector3 euler, Vector3 scale, Material mat)
    {
        var go = GameObject.CreatePrimitive(type);
        go.name = name;
        Object.DestroyImmediate(go.GetComponent<Collider>());
        go.transform.SetParent(parent, false);
        go.transform.localPosition = pos;
        go.transform.localEulerAngles = euler;
        go.transform.localScale = scale;
        go.GetComponent<MeshRenderer>().sharedMaterial = mat;
    }

    public static Mesh Triangle(Vector3 a, Vector3 b, Vector3 c)
    {
        var mesh = new Mesh();
        mesh.SetVertices(new List<Vector3> { a, b, c });
        mesh.SetTriangles(new[] { 0, 1, 2 }, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    // A flat board (swept flattened ellipse), +Z = nose, centred on the origin.
    public static Mesh Board(float length, float width, float thickness, int lenSegs = 24, int radSegs = 14)
    {
        var verts = new List<Vector3>();
        for (int i = 0; i <= lenSegs; i++)
        {
            float t = (float)i / lenSegs;
            float s = (t - 0.5f) * length;
            float outline = Mathf.Sqrt(Mathf.Max(0f, 1f - Mathf.Pow(2f * t - 1f, 2f)));
            float nose = Mathf.Lerp(1f, 0.7f, Mathf.SmoothStep(0.6f, 1f, t));
            float halfW = 0.5f * width * outline * nose;
            float halfT = 0.5f * thickness * Mathf.Pow(outline, 0.4f);
            for (int j = 0; j < radSegs; j++)
            {
                float a = 2f * Mathf.PI * j / radSegs;
                verts.Add(new Vector3(halfW * Mathf.Cos(a), halfT * Mathf.Sin(a), s));
            }
        }
        var tris = new List<int>();
        for (int i = 0; i < lenSegs; i++)
            for (int j = 0; j < radSegs; j++)
            {
                int a = i * radSegs + j, b = i * radSegs + (j + 1) % radSegs;
                int c = (i + 1) * radSegs + (j + 1) % radSegs, d = (i + 1) * radSegs + j;
                tris.Add(a); tris.Add(d); tris.Add(c);
                tris.Add(a); tris.Add(c); tris.Add(b);
            }
        var mesh = new Mesh { name = "Board" };
        mesh.SetVertices(verts);
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    // Standard traffic prefab wrapper: root(Labeling + BoxCollider) -> model(KinematicBob).
    public static void SavePrefab(GameObject root, GameObject model, string label,
                                  Vector3 boxCenter, Vector3 boxSize, string prefabPath)
    {
        var labeling = root.AddComponent<Labeling>();
        labeling.labels.Add(label);
        labeling.labels.Add("dynamic_obstacle");
        labeling.RefreshLabeling();
        var box = root.AddComponent<BoxCollider>();
        box.center = boxCenter;
        box.size = boxSize;
        model.AddComponent<KinematicBob>();
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Prefabs");
        PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
        Object.DestroyImmediate(root);
        AssetDatabase.SaveAssets();
    }
}
