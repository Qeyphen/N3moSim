using System;
using System.IO;
using UnityEngine;
using UnityEngine.Perception.GroundTruth;

[Serializable]
public class ScenarioInfoPayload
{
    public string id;
    public string manifest_path;
    public string weather;
    public string weather_mode;
    public string time_mode;
    public string time_bucket;
    public float time_start_of_day;
    public float time_end_of_day;
    public float time_update_period_s;
    public float duration_s;
    public float capture_hz;
    public int track_count;
    public string area_type;
    public string type_counts_json;
    public int scenario_seed;
}

[Serializable]
class ScenarioSnapshotRecord
{
    public string stage;
    public string written_at;
    public string dataset_path;
    public ScenarioInfoPayload scenario;
}

public static class ScenarioMetadataContext
{
    static ScenarioInfoPayload current;
    static string rawJson = "";

    public static ScenarioInfoPayload Current => current;
    public static string RawJson => rawJson;
    public static bool HasScenario => current != null && !string.IsNullOrEmpty(current.id);

    public static void SetCurrentFromJson(string json)
    {
        if (string.IsNullOrWhiteSpace(json)) return;
        try
        {
            var parsed = JsonUtility.FromJson<ScenarioInfoPayload>(json);
            if (parsed == null || string.IsNullOrEmpty(parsed.id))
            {
                Debug.LogWarning("[ScenarioMetadata] ignored invalid scenario info payload.");
                return;
            }
            current = parsed;
            rawJson = json;
            Debug.Log($"[ScenarioMetadata] current scenario = '{parsed.id}'.");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[ScenarioMetadata] failed to parse scenario info: {e.Message}");
        }
    }

    public static void WriteSnapshot(string stage, PerceptionCamera pc)
    {
        if (!HasScenario) return;
        try
        {
            string outDir = ResolveOutputDir(pc);
            Directory.CreateDirectory(outDir);
            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string cameraKey = RunMetadata.ResolveCameraKey(pc);
            var rec = new ScenarioSnapshotRecord
            {
                stage = stage,
                written_at = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
                dataset_path = outDir,
                scenario = current,
            };
            string path = Path.Combine(outDir, $"scenario_{stage}_{cameraKey}_{current.id}_{stamp}.json");
            File.WriteAllText(path, JsonUtility.ToJson(rec, true));
            Debug.Log($"[ScenarioMetadata] wrote {path}");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[ScenarioMetadata] snapshot failed: {e.Message}");
        }
    }

    static string ResolveOutputDir(PerceptionCamera pc)
    {
        string latest = RunMetadata.LatestSoloDir();
        if (!string.IsNullOrEmpty(latest) && Directory.Exists(latest))
            return latest;
        return Application.persistentDataPath;
    }
}
