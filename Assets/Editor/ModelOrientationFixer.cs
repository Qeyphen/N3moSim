using UnityEditor;
using UnityEngine;

// Sets the model child's local rotation across selected prefabs so its nose faces +Z
// (TrackSpawner aligns +Z to heading). Fixes traffic that travels sideways.
// Run via N3mo -> Fix Model Orientation.
public class ModelOrientationFixer : EditorWindow
{
    private Vector3 euler = new Vector3(0f, 90f, 0f);
    private string childName = "model";

    [MenuItem("N3mo/Fix Model Orientation")]
    private static void Open() => GetWindow<ModelOrientationFixer>("Fix Model Orientation");

    private void OnGUI()
    {
        EditorGUILayout.HelpBox(
            "Select traffic prefab(s) in the Project window, set the model child's local Euler " +
            "so its nose points along +Z, then Apply.\n" +
            "sideways -> Y = 90 or -90;  lying flat / upside down -> add X = -90.",
            MessageType.Info);

        childName = EditorGUILayout.TextField(
            new GUIContent("Child name", "Model child to rotate; falls back to the first child."),
            childName);
        euler = EditorGUILayout.Vector3Field("Local Euler", euler);

        using (new EditorGUI.DisabledScope(Selection.objects.Length == 0))
        {
            if (GUILayout.Button($"Apply to {Selection.objects.Length} selected prefab(s)"))
                Apply();
        }
    }

    private void Apply()
    {
        int n = 0;
        foreach (var obj in Selection.objects)
        {
            string path = AssetDatabase.GetAssetPath(obj);
            if (string.IsNullOrEmpty(path) || !path.EndsWith(".prefab")) continue;

            GameObject root = PrefabUtility.LoadPrefabContents(path);
            Transform model = root.transform.Find(childName);
            if (model == null && root.transform.childCount > 0)
                model = root.transform.GetChild(0);

            if (model != null)
            {
                model.localEulerAngles = euler;
                PrefabUtility.SaveAsPrefabAsset(root, path);
                Debug.Log($"[ModelOrientationFixer] {path}: '{model.name}' -> Euler {euler}");
                n++;
            }
            else
            {
                Debug.LogWarning($"[ModelOrientationFixer] {path}: no model child to rotate.");
            }
            PrefabUtility.UnloadPrefabContents(root);
        }
        Debug.Log($"[ModelOrientationFixer] Applied to {n} prefab(s).");
    }
}
