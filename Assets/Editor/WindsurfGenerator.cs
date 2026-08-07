using UnityEditor;
using UnityEngine;
using U = AssetMeshUtil;

// Procedural windsurfer: board + raked mast + wishbone boom + sail. Traffic prefab.
// Run via N3mo -> Generate Windsurf.
public static class WindsurfGenerator
{
    [MenuItem("N3mo/Generate Windsurf")]
    public static void Generate()
    {
        var boardMat = U.Mat("Windsurf_Board", new Color(0.2f, 0.5f, 0.8f));
        var sparMat  = U.Mat("Windsurf_Spar", new Color(0.5f, 0.5f, 0.55f));
        var sailMat  = U.Mat("Windsurf_Sail", new Color(0.9f, 0.3f, 0.25f), cullOff: true);

        var root = new GameObject("Windsurf");
        var model = new GameObject("model");
        model.transform.SetParent(root.transform, false);

        U.MeshChild("Board", model.transform, U.Save(U.Board(2.6f, 0.65f, 0.12f), "Windsurf_Board"), boardMat);

        // rig raked slightly aft, in the fore-aft plane
        Vector3 mastBase = new Vector3(0f, 0.1f, 0.2f);
        Vector3 mastTop  = new Vector3(0f, 4.4f, -0.3f);
        Vector3 clew     = new Vector3(0f, 1.3f, -1.7f);
        U.MeshChild("Sail", model.transform, U.Save(U.Triangle(mastBase, mastTop, clew), "Windsurf_Sail"), sailMat);
        U.Primitive(PrimitiveType.Cylinder, "Mast", model.transform,
            (mastBase + mastTop) * 0.5f, MastEuler(mastBase, mastTop),
            new Vector3(0.05f, (mastTop - mastBase).magnitude * 0.5f, 0.05f), sparMat);
        U.Primitive(PrimitiveType.Cylinder, "Boom", model.transform,
            new Vector3(0f, 1.3f, -0.6f), MastEuler(new Vector3(0, 1.3f, 0.2f), clew),
            new Vector3(0.03f, (clew - new Vector3(0, 1.3f, 0.2f)).magnitude * 0.5f, 0.03f), sparMat);

        U.SavePrefab(root, model, "windsurf",
            new Vector3(0, 0.05f, 0), new Vector3(0.7f, 4.5f, 2.6f), "Assets/Prefabs/Windsurf.prefab");

        Debug.Log("[WindsurfGenerator] built Assets/Prefabs/Windsurf.prefab (type=Windsurf).");
        EditorGUIUtility.PingObject(AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Prefabs/Windsurf.prefab"));
    }

    // orient a Y-axis cylinder to point from a to b
    static Vector3 MastEuler(Vector3 a, Vector3 b) =>
        Quaternion.FromToRotation(Vector3.up, (b - a).normalized).eulerAngles;
}
