using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Generates a stand-up paddleboard mesh + a spawnable traffic prefab (Labeling + collider +
// KinematicBob), so it needs no external 3D asset. Run via N3mo -> Generate Paddleboard.
public static class PaddleboardGenerator
{
    const string MeshPath   = "Assets/Models/Generated/Paddleboard.asset";
    const string MatPath    = "Assets/Models/Generated/Paddleboard.mat";
    const string PrefabPath = "Assets/Prefabs/Paddleboard.prefab";

    // metres
    const float Length = 3.2f, Width = 0.75f, Thickness = 0.14f;
    const int   LengthSegs = 28, RadialSegs = 16;

    [MenuItem("N3mo/Generate Paddleboard")]
    public static void Generate()
    {
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Models/Generated");
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Prefabs");

        Mesh mesh = BuildMesh();
        AssetDatabase.CreateAsset(mesh, MeshPath);

        var mat = new Material(Shader.Find("HDRP/Lit"));
        mat.SetColor("_BaseColor", new Color(0.85f, 0.75f, 0.35f)); // sand/foam board
        AssetDatabase.CreateAsset(mat, MatPath);

        var root = new GameObject("Paddleboard");
        var model = new GameObject("model");
        model.transform.SetParent(root.transform, false);
        model.AddComponent<MeshFilter>().sharedMesh = mesh;
        model.AddComponent<MeshRenderer>().sharedMaterial = mat;
        model.AddComponent<KinematicBob>();

        var labeling = root.AddComponent<Labeling>();
        labeling.labels.Add("paddleboard");
        labeling.labels.Add("dynamic_obstacle");
        labeling.RefreshLabeling();

        var box = root.AddComponent<BoxCollider>();
        box.center = new Vector3(0f, 0f, 0f);
        box.size = new Vector3(Width, Thickness, Length);

        PrefabUtility.SaveAsPrefabAsset(root, PrefabPath);
        Object.DestroyImmediate(root);
        AssetDatabase.SaveAssets();

        Debug.Log($"[PaddleboardGenerator] built {PrefabPath} (+ mesh/material). " +
                  "Add it to TrackSpawner.prefabOverrides as type=Paddleboard.");
        EditorGUIUtility.PingObject(AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath));
    }

    // Sweep flattened elliptical cross-sections along the length; width/thickness taper to the
    // nose and tail (which collapse to points -> rounded ends). Nose (+Z) is a bit pointier.
    static Mesh BuildMesh()
    {
        var verts = new List<Vector3>();
        var uvs = new List<Vector2>();
        var tris = new List<int>();

        for (int i = 0; i <= LengthSegs; i++)
        {
            float t = (float)i / LengthSegs;          // 0 tail .. 1 nose
            float s = (t - 0.5f) * Length;            // along +Z
            float outline = Mathf.Sqrt(Mathf.Max(0f, 1f - Mathf.Pow(2f * t - 1f, 2f))); // rounded
            float nose = Mathf.Lerp(1f, 0.75f, Mathf.SmoothStep(0.6f, 1f, t));           // taper the nose
            float halfW = 0.5f * Width * outline * nose;
            float halfT = 0.5f * Thickness * Mathf.Pow(outline, 0.4f);

            for (int j = 0; j < RadialSegs; j++)
            {
                float a = 2f * Mathf.PI * j / RadialSegs;
                verts.Add(new Vector3(halfW * Mathf.Cos(a), halfT * Mathf.Sin(a), s));
                uvs.Add(new Vector2(t, (float)j / RadialSegs));
            }
        }

        for (int i = 0; i < LengthSegs; i++)
            for (int j = 0; j < RadialSegs; j++)
            {
                int a = i * RadialSegs + j;
                int b = i * RadialSegs + (j + 1) % RadialSegs;
                int c = (i + 1) * RadialSegs + (j + 1) % RadialSegs;
                int d = (i + 1) * RadialSegs + j;
                tris.Add(a); tris.Add(d); tris.Add(c);
                tris.Add(a); tris.Add(c); tris.Add(b);
            }

        var mesh = new Mesh { name = "Paddleboard" };
        mesh.SetVertices(verts);
        mesh.SetUVs(0, uvs);
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }
}
