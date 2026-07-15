using UnityEditor;
using UnityEngine;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Turns each kayak selected in the Hierarchy into its own traffic prefab (Labeling + collider
// + KinematicBob, no Rigidbody — traffic is kinematic). Run via N3mo -> Build Kayak Prefabs
// From Selection. The kayak FBX is a 6-colour pack, so select the colours you want.
public static class KayakPrefabBuilder
{
    [MenuItem("N3mo/Build Kayak Prefabs From Selection")]
    public static void Build()
    {
        GameObject[] sel = Selection.gameObjects;
        if (sel == null || sel.Length == 0)
        {
            Debug.LogError("[KayakPrefabBuilder] Nothing selected. Drag kayak.fbx into the scene, " +
                           "expand it, and select the kayak colour(s), then run again.");
            return;
        }

        System.IO.Directory.CreateDirectory(Application.dataPath + "/Prefabs");
        int built = 0;
        foreach (var s in sel)
        {
            string name = s.name.Replace("(Clone)", "").Trim();
            string path = $"Assets/Prefabs/{name}.prefab";

            GameObject model = Object.Instantiate(s);
            model.name = "model";

            var root = new GameObject(name);
            model.transform.SetParent(root.transform, worldPositionStays: false);
            model.transform.localPosition = Vector3.zero;

            var labeling = root.AddComponent<Labeling>();
            labeling.labels.Add("kayak");
            labeling.labels.Add("dynamic_obstacle");
            labeling.RefreshLabeling();

            var rends = root.GetComponentsInChildren<Renderer>();
            if (rends.Length > 0)
            {
                Bounds b = rends[0].bounds;
                foreach (var r in rends) b.Encapsulate(r.bounds);
                var bc = root.AddComponent<BoxCollider>();
                bc.center = root.transform.InverseTransformPoint(b.center);
                bc.size = b.size;
            }

            model.AddComponent<KinematicBob>();   // bob lives on the child, not the spawner-driven root

            PrefabUtility.SaveAsPrefabAsset(root, path);
            Object.DestroyImmediate(root);
            Debug.Log($"[KayakPrefabBuilder] Built {path}");
            built++;
        }

        AssetDatabase.SaveAssets();
        Debug.Log($"[KayakPrefabBuilder] Done — {built} prefab(s). " +
                  "Add each to TrackSpawner.prefabOverrides as type=Kayak.");
    }
}
