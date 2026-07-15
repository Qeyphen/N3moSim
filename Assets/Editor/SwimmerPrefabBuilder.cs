using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Builds Swimmer.prefab from SWIM.fbx: loops the swim clip, makes an animator controller,
// and adds the swimmer Labeling. Run via N3mo -> Build Swimmer Prefab.
public static class SwimmerPrefabBuilder
{
    const string FbxPath        = "Assets/Models/SWIM.fbx";
    const string ControllerPath = "Assets/Animations/SwimController.controller";
    const string PrefabPath     = "Assets/Prefabs/Swimmer.prefab";

    [MenuItem("N3mo/Build Swimmer Prefab")]
    public static void Build()
    {
        if (AssetImporter.GetAtPath(FbxPath) is not ModelImporter importer)
        {
            Debug.LogError($"[SwimmerPrefabBuilder] No ModelImporter at {FbxPath}. Is SWIM.fbx imported?");
            return;
        }

        // Force the embedded clip(s) to loop.
        ModelImporterClipAnimation[] clips =
            importer.clipAnimations.Length > 0 ? importer.clipAnimations : importer.defaultClipAnimations;
        if (clips.Length > 0)
        {
            foreach (var c in clips) { c.loopTime = true; c.loopPose = true; }
            importer.clipAnimations = clips;
            importer.SaveAndReimport();
        }

        // Longest non-preview clip = the swim take.
        AnimationClip clip = AssetDatabase.LoadAllAssetsAtPath(FbxPath)
            .OfType<AnimationClip>()
            .Where(c => !c.name.StartsWith("__preview__"))
            .OrderByDescending(c => c.length)
            .FirstOrDefault();
        if (clip == null)
        {
            Debug.LogError($"[SwimmerPrefabBuilder] No AnimationClip found inside {FbxPath}.");
            return;
        }

        System.IO.Directory.CreateDirectory(Application.dataPath + "/Animations");
        var controller = AnimatorController.CreateAnimatorControllerAtPathWithClip(ControllerPath, clip);

        var fbx = AssetDatabase.LoadAssetAtPath<GameObject>(FbxPath);
        var instance = (GameObject)PrefabUtility.InstantiatePrefab(fbx);
        instance.name = "Swimmer";

        var animator = instance.GetComponentInChildren<Animator>() ?? instance.AddComponent<Animator>();
        animator.runtimeAnimatorController = controller;
        animator.applyRootMotion = false;   // position is spawner-driven

        var labeling = instance.AddComponent<Labeling>();
        labeling.labels.Add("swimmer");
        labeling.labels.Add("dynamic_obstacle");
        labeling.RefreshLabeling();

        var cap = instance.AddComponent<CapsuleCollider>();
        cap.direction = 2;        // Z — roughly horizontal in the water
        cap.height = 2f;
        cap.radius = 0.3f;
        cap.center = new Vector3(0f, 0.3f, 0f);

        System.IO.Directory.CreateDirectory(Application.dataPath + "/Prefabs");
        PrefabUtility.SaveAsPrefabAsset(instance, PrefabPath);
        Object.DestroyImmediate(instance);

        AssetDatabase.SaveAssets();
        Debug.Log($"[SwimmerPrefabBuilder] Built {PrefabPath} (clip '{clip.name}'). " +
                  "Add it to TrackSpawner.prefabOverrides as type=Swimmer.");
        EditorGUIUtility.PingObject(AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath));
    }
}
