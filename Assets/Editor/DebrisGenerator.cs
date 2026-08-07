using UnityEditor;
using UnityEngine;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Generates a floating-debris cluster (random planks + a log + a crate) and a spawnable traffic
// prefab (Labeling + collider + KinematicBob). Re-run for a different random pile. No external asset.
public static class DebrisGenerator
{
    const string Dir        = "Assets/Models/Generated";
    const string PrefabPath = "Assets/Prefabs/Debris.prefab";

    [MenuItem("N3mo/Generate Debris")]
    public static void Generate()
    {
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Models/Generated");
        System.IO.Directory.CreateDirectory(Application.dataPath + "/Prefabs");

        Material[] woods =
        {
            Mat("Debris_WoodA", new Color(0.45f, 0.30f, 0.18f)),
            Mat("Debris_WoodB", new Color(0.35f, 0.25f, 0.15f)),
            Mat("Debris_WoodC", new Color(0.52f, 0.42f, 0.26f)),
            Mat("Debris_Grey",  new Color(0.42f, 0.42f, 0.45f)),
        };

        var root = new GameObject("Debris");
        var model = new GameObject("model");
        model.transform.SetParent(root.transform, false);
        model.AddComponent<KinematicBob>();

        // planks: thin, flat, long, lying roughly flat on the water and overlapping
        for (int i = 0; i < 5; i++)
        {
            Vector2 p = Random.insideUnitCircle * 0.55f;
            Piece(PrimitiveType.Cube, model.transform,
                new Vector3(p.x, Random.Range(-0.05f, 0.15f), p.y),
                new Vector3(Random.Range(-12f, 12f), Random.Range(0f, 360f), Random.Range(-12f, 12f)),
                new Vector3(Random.Range(0.12f, 0.22f), Random.Range(0.04f, 0.09f), Random.Range(0.7f, 1.7f)),
                woods[Random.Range(0, woods.Length)]);
        }

        // a log
        Vector2 lp = Random.insideUnitCircle * 0.4f;
        Piece(PrimitiveType.Cylinder, model.transform,
            new Vector3(lp.x, 0.05f, lp.y),
            new Vector3(90f, Random.Range(0f, 360f), 0f),
            new Vector3(Random.Range(0.09f, 0.14f), Random.Range(0.5f, 0.8f), Random.Range(0.09f, 0.14f)),
            woods[Random.Range(0, 3)]);

        // a crate
        Piece(PrimitiveType.Cube, model.transform,
            new Vector3(Random.Range(-0.3f, 0.3f), 0.1f, Random.Range(-0.3f, 0.3f)),
            new Vector3(Random.Range(-15f, 15f), Random.Range(0f, 360f), Random.Range(-15f, 15f)),
            new Vector3(Random.Range(0.3f, 0.45f), Random.Range(0.3f, 0.4f), Random.Range(0.3f, 0.45f)),
            woods[Random.Range(0, woods.Length)]);

        var labeling = root.AddComponent<Labeling>();
        labeling.labels.Add("debris");
        labeling.labels.Add("dynamic_obstacle");
        labeling.RefreshLabeling();

        var box = root.AddComponent<BoxCollider>();
        box.center = new Vector3(0, 0.05f, 0);
        box.size = new Vector3(1.6f, 0.6f, 1.6f);

        PrefabUtility.SaveAsPrefabAsset(root, PrefabPath);
        Object.DestroyImmediate(root);
        AssetDatabase.SaveAssets();

        Debug.Log($"[DebrisGenerator] built {PrefabPath}. Add it to TrackSpawner.prefabOverrides as type=Debris.");
        EditorGUIUtility.PingObject(AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath));
    }

    static Material Mat(string name, Color c)
    {
        var m = new Material(Shader.Find("HDRP/Lit"));
        m.SetColor("_BaseColor", c);
        AssetDatabase.CreateAsset(m, $"{Dir}/{name}.mat");
        return m;
    }

    static void Piece(PrimitiveType type, Transform parent, Vector3 pos, Vector3 euler, Vector3 scale, Material mat)
    {
        var go = GameObject.CreatePrimitive(type);
        go.name = type.ToString();
        Object.DestroyImmediate(go.GetComponent<Collider>());
        go.transform.SetParent(parent, false);
        go.transform.localPosition = pos;
        go.transform.localEulerAngles = euler;
        go.transform.localScale = scale;
        go.GetComponent<MeshRenderer>().sharedMaterial = mat;
    }
}
