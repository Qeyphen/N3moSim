using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using U = AssetMeshUtil;

// Procedural kitesurfer: twin-tip board + an arced kite canopy up front + two lines. Traffic prefab.
// Run via N3mo -> Generate Kitesurf.
public static class KitesurfGenerator
{
    static readonly Vector3 KiteC = new Vector3(0f, 7f, 2.2f);   // kite centre (up + forward)
    const float Span = 4.2f, Chord = 0.9f, Sag = 1.6f;

    [MenuItem("N3mo/Generate Kitesurf")]
    public static void Generate()
    {
        var boardMat = U.Mat("Kitesurf_Board", new Color(0.15f, 0.15f, 0.18f));
        var kiteMat  = U.Mat("Kitesurf_Kite", new Color(0.95f, 0.75f, 0.15f), cullOff: true);
        var lineMat  = U.Mat("Kitesurf_Line", new Color(0.2f, 0.2f, 0.2f));

        var root = new GameObject("Kitesurf");
        var model = new GameObject("model");
        model.transform.SetParent(root.transform, false);

        U.MeshChild("Board", model.transform, U.Save(U.Board(1.4f, 0.42f, 0.08f), "Kitesurf_Board"), boardMat);
        U.MeshChild("Kite", model.transform, U.Save(BuildKite(), "Kitesurf_Kite"), kiteMat);

        Vector3 bar = new Vector3(0f, 0.6f, 0.4f);
        Line(model.transform, bar, TipL(), lineMat);
        Line(model.transform, bar, TipR(), lineMat);

        U.SavePrefab(root, model, "kitesurf",
            new Vector3(0, 3.5f, 1f), new Vector3(Span, 8f, 3f), "Assets/Prefabs/Kitesurf.prefab");

        Debug.Log("[KitesurfGenerator] built Assets/Prefabs/Kitesurf.prefab (type=Kitesurf).");
        EditorGUIUtility.PingObject(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Prefabs/Kitesurf.prefab"));
    }

    static Vector3 TipL() => new Vector3(-Span * 0.5f, KiteC.y - Sag, KiteC.z);
    static Vector3 TipR() => new Vector3( Span * 0.5f, KiteC.y - Sag, KiteC.z);

    // Arced canopy: a strip between a leading and trailing edge, tips sagging down (C-kite).
    static Mesh BuildKite()
    {
        int N = 16;
        var verts = new List<Vector3>();
        for (int k = 0; k <= N; k++)
        {
            float t = (float)k / N;
            float x = (t - 0.5f) * Span;
            float sag = Sag * Mathf.Pow(2f * t - 1f, 2f);
            verts.Add(new Vector3(x, KiteC.y - sag, KiteC.z + Chord * 0.5f));         // leading edge
            verts.Add(new Vector3(x, KiteC.y - sag - 0.12f, KiteC.z - Chord * 0.5f)); // trailing edge
        }
        var tris = new List<int>();
        for (int k = 0; k < N; k++)
        {
            int a = k * 2, b = k * 2 + 1, c = k * 2 + 2, d = k * 2 + 3;
            tris.Add(a); tris.Add(c); tris.Add(b);
            tris.Add(b); tris.Add(c); tris.Add(d);
        }
        var mesh = new Mesh { name = "Kite" };
        mesh.SetVertices(verts);
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static void Line(Transform parent, Vector3 a, Vector3 b, Material mat)
    {
        Vector3 dir = b - a;
        U.Primitive(PrimitiveType.Cylinder, "Line", parent, (a + b) * 0.5f,
            Quaternion.FromToRotation(Vector3.up, dir.normalized).eulerAngles,
            new Vector3(0.015f, dir.magnitude * 0.5f, 0.015f), mat);
    }
}
