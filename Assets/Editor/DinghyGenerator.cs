using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Generates a small dinghy hull mesh + a spawnable traffic prefab (Labeling + collider +
// KinematicBob), no external asset. Run via N3mo -> Generate Dinghy.
public static class DinghyGenerator
{
    const string MeshPath   = "Assets/Models/Generated/Dinghy.asset";
    const string MatPath    = "Assets/Models/Generated/Dinghy.mat";
    const string PrefabPath = "Assets/Prefabs/Dinghy.prefab";

    // metres
    const float Length = 3.0f, Beam = 1.4f, Depth = 0.45f, DeckY = 0.18f, TransomFrac = 0.6f;
    const int   LengthSegs = 24, ArcSegs = 10;

    [MenuItem("N3mo/Generate Dinghy")]
    public static void Generate()
    {
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Models/Generated");
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Prefabs");

        Mesh mesh = BuildMesh();
        AssetDatabase.CreateAsset(mesh, MeshPath);

        var mat = new Material(Shader.Find("HDRP/Lit"));
        mat.SetColor("_BaseColor", new Color(0.82f, 0.82f, 0.85f)); // light hull
        mat.SetFloat("_CullMode", 0f);                              // double-sided (open hull)
        AssetDatabase.CreateAsset(mat, MatPath);

        var root = new GameObject("Dinghy");
        var model = new GameObject("model");
        model.transform.SetParent(root.transform, false);
        model.AddComponent<MeshFilter>().sharedMesh = mesh;
        model.AddComponent<MeshRenderer>().sharedMaterial = mat;
        model.AddComponent<KinematicBob>();

        var labeling = root.AddComponent<Labeling>();
        labeling.labels.Add("dinghy");
        labeling.labels.Add("dynamic_obstacle");
        labeling.RefreshLabeling();

        var box = root.AddComponent<BoxCollider>();
        box.center = new Vector3(0f, DeckY - Depth * 0.5f, 0f);
        box.size = new Vector3(Beam, Depth + DeckY, Length);

        PrefabUtility.SaveAsPrefabAsset(root, PrefabPath);
        Object.DestroyImmediate(root);
        AssetDatabase.SaveAssets();

        Debug.Log($"[DinghyGenerator] built {PrefabPath} (+ mesh/material). " +
                  "Add it to TrackSpawner.prefabOverrides as type=Dinghy.");
        EditorGUIUtility.PingObject(AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath));
    }

    // Closed D-shaped cross-sections (flat deck, rounded hull) swept along +Z, beam widest amidships,
    // tapering to a point at the bow and a transom at the stern.
    static Mesh BuildMesh()
    {
        int RC = ArcSegs + 1;                          // vertices per ring
        var verts = new List<Vector3>();
        var uvs = new List<Vector2>();

        for (int i = 0; i <= LengthSegs; i++)
        {
            float t = (float)i / LengthSegs;           // 0 stern .. 1 bow
            float z = (t - 0.5f) * Length;
            float aft = Mathf.SmoothStep(0f, 0.5f, t);              // fills out behind the transom
            float bow = 1f - Mathf.SmoothStep(0.65f, 1f, t);        // tapers to the bow point
            float b = Beam * Mathf.Lerp(TransomFrac, 1f, aft) * bow;
            float d = Depth * (0.55f + 0.45f * bow);

            for (int k = 0; k <= ArcSegs; k++)
            {
                float a = Mathf.PI * k / ArcSegs;      // starboard gunwale -> keel -> port gunwale
                verts.Add(new Vector3(0.5f * b * Mathf.Cos(a), DeckY - d * Mathf.Sin(a), z));
                uvs.Add(new Vector2(t, (float)k / ArcSegs));
            }
        }

        var tris = new List<int>();
        for (int i = 0; i < LengthSegs; i++)
            for (int j = 0; j < RC; j++)
            {
                int jn = (j + 1) % RC;                  // wrap closes the deck (port->starboard)
                int a = i * RC + j, b = i * RC + jn;
                int c = (i + 1) * RC + jn, dd = (i + 1) * RC + j;
                tris.Add(a); tris.Add(b); tris.Add(c);
                tris.Add(a); tris.Add(c); tris.Add(dd);
            }

        AddCap(tris, 0, RC);                            // transom (stern)
        AddCap(tris, LengthSegs * RC, RC);              // bow point

        var mesh = new Mesh { name = "Dinghy" };
        mesh.SetVertices(verts);
        mesh.SetUVs(0, uvs);
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static void AddCap(List<int> tris, int ringStart, int rc)
    {
        for (int k = 1; k < rc - 1; k++)
        {
            tris.Add(ringStart);
            tris.Add(ringStart + k);
            tris.Add(ringStart + k + 1);
        }
    }
}
