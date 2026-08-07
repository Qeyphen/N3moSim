using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Generates a detailed sailboat (hull + keel + rudder + mast + boom + mainsail + jib + cabin) and a
// spawnable traffic prefab (Labeling + collider + KinematicBob). No external asset.
// Run via N3mo -> Generate Sailboat.
public static class SailboatGenerator
{
    const string Dir        = "Assets/Models/Generated";
    const string PrefabPath = "Assets/Prefabs/Sailboat.prefab";

    // hull (metres), +Z = bow
    const float Length = 5.5f, Beam = 1.8f, Depth = 0.6f, DeckY = 0.35f, TransomFrac = 0.4f;
    const int   LengthSegs = 28, ArcSegs = 10;

    // rig
    const float MastZ = 0.6f, MastH = 6.0f, BoomY = 0.95f, BoomEndZ = -2.0f;

    [MenuItem("N3mo/Generate Sailboat")]
    public static void Generate()
    {
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Models/Generated");
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Prefabs");

        var hullMat = Mat("Sailboat_Hull", new Color(0.85f, 0.85f, 0.88f), cullOff: true);
        var sparMat = Mat("Sailboat_Spar", new Color(0.55f, 0.55f, 0.58f), cullOff: false);
        var sailMat = Mat("Sailboat_Sail", new Color(0.95f, 0.95f, 0.92f), cullOff: true);

        var root = new GameObject("Sailboat");
        var model = new GameObject("model");
        model.transform.SetParent(root.transform, false);
        model.AddComponent<KinematicBob>();

        // Hull + sails as custom meshes; spars/keel/cabin as scaled primitives.
        MeshChild("Hull", model.transform, SaveMesh(BuildHull(), "Sailboat_Hull"), hullMat);

        float mastTopY = DeckY + MastH;
        MeshChild("Mainsail", model.transform, SaveMesh(Triangle(
            new Vector3(0, mastTopY, MastZ), new Vector3(0, BoomY, MastZ),
            new Vector3(0, BoomY, BoomEndZ)), "Sailboat_Mainsail"), sailMat);
        MeshChild("Jib", model.transform, SaveMesh(Triangle(
            new Vector3(0, 0.5f, Length * 0.47f), new Vector3(0, mastTopY - 0.8f, MastZ),
            new Vector3(0, 0.7f, 1.0f)), "Sailboat_Jib"), sailMat);

        Primitive(PrimitiveType.Cylinder, "Mast", model.transform,
            new Vector3(0, DeckY + MastH * 0.5f, MastZ), Vector3.zero,
            new Vector3(0.10f, MastH * 0.5f, 0.10f), sparMat);
        Primitive(PrimitiveType.Cylinder, "Boom", model.transform,
            new Vector3(0, BoomY, (MastZ + BoomEndZ) * 0.5f), new Vector3(90, 0, 0),
            new Vector3(0.08f, (MastZ - BoomEndZ) * 0.5f, 0.08f), sparMat);
        Primitive(PrimitiveType.Cube, "Keel", model.transform,
            new Vector3(0, -0.75f, -0.1f), Vector3.zero, new Vector3(0.08f, 1.0f, 1.4f), sparMat);
        Primitive(PrimitiveType.Cube, "Rudder", model.transform,
            new Vector3(0, -0.45f, -2.5f), Vector3.zero, new Vector3(0.06f, 0.7f, 0.35f), sparMat);
        Primitive(PrimitiveType.Cube, "Cabin", model.transform,
            new Vector3(0, DeckY + 0.2f, -0.2f), Vector3.zero, new Vector3(1.0f, 0.4f, 1.8f), hullMat);

        var labeling = root.AddComponent<Labeling>();
        labeling.labels.Add("sailboat");
        labeling.labels.Add("dynamic_obstacle");
        labeling.RefreshLabeling();

        var box = root.AddComponent<BoxCollider>();
        box.center = new Vector3(0, DeckY - Depth * 0.5f, 0);
        box.size = new Vector3(Beam, Depth + DeckY, Length);

        PrefabUtility.SaveAsPrefabAsset(root, PrefabPath);
        Object.DestroyImmediate(root);
        AssetDatabase.SaveAssets();

        Debug.Log($"[SailboatGenerator] built {PrefabPath}. Add it to TrackSpawner.prefabOverrides as type=Sailboat.");
        EditorGUIUtility.PingObject(AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath));
    }

    // ---- helpers ----

    static Material Mat(string name, Color c, bool cullOff)
    {
        var m = new Material(Shader.Find("HDRP/Lit"));
        m.SetColor("_BaseColor", c);
        if (cullOff) m.SetFloat("_CullMode", 0f);
        AssetDatabase.CreateAsset(m, $"{Dir}/{name}.mat");
        return m;
    }

    static Mesh SaveMesh(Mesh mesh, string name)
    {
        AssetDatabase.CreateAsset(mesh, $"{Dir}/{name}.asset");
        return mesh;
    }

    static void MeshChild(string name, Transform parent, Mesh mesh, Material mat)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
    }

    static void Primitive(PrimitiveType type, string name, Transform parent,
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

    static Mesh Triangle(Vector3 a, Vector3 b, Vector3 c)
    {
        var mesh = new Mesh();
        mesh.SetVertices(new List<Vector3> { a, b, c });
        mesh.SetUVs(0, new List<Vector2> { new(0, 0), new(0, 1), new(1, 0) });
        mesh.SetTriangles(new[] { 0, 1, 2 }, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static Mesh BuildHull()
    {
        int RC = ArcSegs + 1;
        var verts = new List<Vector3>();
        for (int i = 0; i <= LengthSegs; i++)
        {
            float t = (float)i / LengthSegs;
            float z = (t - 0.5f) * Length;
            float aft = Mathf.SmoothStep(0f, 0.5f, t);
            float bow = 1f - Mathf.SmoothStep(0.65f, 1f, t);
            float b = Beam * Mathf.Lerp(TransomFrac, 1f, aft) * bow;
            float d = Depth * (0.55f + 0.45f * bow);
            for (int k = 0; k <= ArcSegs; k++)
            {
                float ang = Mathf.PI * k / ArcSegs;
                verts.Add(new Vector3(0.5f * b * Mathf.Cos(ang), DeckY - d * Mathf.Sin(ang), z));
            }
        }

        var tris = new List<int>();
        for (int i = 0; i < LengthSegs; i++)
            for (int j = 0; j < RC; j++)
            {
                int jn = (j + 1) % RC;
                int a = i * RC + j, b = i * RC + jn, c = (i + 1) * RC + jn, dd = (i + 1) * RC + j;
                tris.Add(a); tris.Add(b); tris.Add(c);
                tris.Add(a); tris.Add(c); tris.Add(dd);
            }
        for (int k = 1; k < RC - 1; k++) { tris.Add(0); tris.Add(k); tris.Add(k + 1); }               // transom
        int last = LengthSegs * RC;
        for (int k = 1; k < RC - 1; k++) { tris.Add(last); tris.Add(last + k); tris.Add(last + k + 1); } // bow

        var mesh = new Mesh { name = "Sailboat_Hull" };
        mesh.SetVertices(verts);
        mesh.SetTriangles(tris, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }
}
