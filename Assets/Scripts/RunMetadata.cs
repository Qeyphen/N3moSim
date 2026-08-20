using System.Globalization;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Perception.GroundTruth;
using UnityEngine.Perception.GroundTruth.LabelManagement;

// Writes a per-recording metadata (data-card) JSON next to the SOLO dataset when a recording
// stops: capture stats, resolution, camera intrinsics/extrinsics + URDF mount, environment,
// scene, labels, and system info. One file per record stop.
public static class RunMetadata
{
    public static void Write(PerceptionCamera pc, float targetHz, float actualHz, int frames, float duration)
    {
        try { WriteInternal(pc, targetHz, actualHz, frames, duration); }
        catch (System.Exception e) { Debug.LogWarning($"[RunMetadata] failed: {e.Message}"); }
    }

    static void WriteInternal(PerceptionCamera pc, float targetHz, float actualHz, int frames, float duration)
    {
        var sb = new StringBuilder();
        var now = System.DateTime.Now;
        string outDir = LatestSoloDir();
        string stamp = now.ToString("yyyyMMdd_HHmmss");
        string cameraKey = ResolveCameraKey(pc);

        sb.Append("{\n");

        // A. run identity
        sb.Append($"  \"run_id\": \"{Path.GetFileName(outDir)}\",\n");
        sb.Append($"  \"recorded_at\": \"{now:yyyy-MM-ddTHH:mm:ss}\",\n");
        sb.Append($"  \"dataset_path\": \"{Esc(outDir)}\",\n");
        sb.Append($"  \"camera_key\": \"{Esc(cameraKey)}\",\n");

        // B. capture
        sb.Append("  \"capture\": {");
        sb.Append($" \"target_hz\": {F(targetHz)}, \"actual_hz\": {F(actualHz)}, ");
        sb.Append($"\"frames\": {frames}, \"duration_s\": {F(duration)}");
        var sched0 = pc != null ? pc.GetComponent<DatasetCaptureScheduler>() : null;
        if (sched0 != null)
        {
            sb.Append($", \"control_topic\": \"{Esc(sched0.controlTopic)}\", ");
            sb.Append($"\"frames_topic\": \"{Esc(sched0.framesTopic)}\", ");
            sb.Append($"\"capture_rate_topic\": \"{Esc(sched0.captureRateTopic)}\", ");
            sb.Append($"\"scenario_info_topic\": \"{Esc(sched0.scenarioInfoTopic)}\"");
        }
        sb.Append(" },\n");

        var cam = pc != null ? pc.GetComponent<Camera>() : null;
        if (cam != null)
        {
            int W = cam.pixelWidth, H = cam.pixelHeight;
            float vfov = cam.fieldOfView;
            float aspect = H > 0 ? (float)W / H : 1.7778f;
            float fy = (H / 2f) / Mathf.Tan(vfov * 0.5f * Mathf.Deg2Rad);
            float hfov = 2f * Mathf.Atan(Mathf.Tan(vfov * 0.5f * Mathf.Deg2Rad) * aspect) * Mathf.Rad2Deg;

            // C. image
            sb.Append("  \"image\": {");
            sb.Append($" \"width\": {W}, \"height\": {H}, \"pixels\": {(long)W * H}, ");
            sb.Append($"\"megapixels\": {F(W * H / 1e6f)}, \"aspect\": {F(aspect)} }},\n");

            // D. camera
            var p = cam.transform.position; var e = cam.transform.eulerAngles;
            sb.Append("  \"camera\": {");
            sb.Append($" \"fov_vertical_deg\": {F(vfov)}, \"fov_horizontal_deg\": {F(hfov)}, ");
            sb.Append($"\"intrinsics_px\": {{ \"fx\": {F(fy)}, \"fy\": {F(fy)}, \"cx\": {F(W / 2f)}, \"cy\": {F(H / 2f)} }}, ");
            sb.Append($"\"near\": {F(cam.nearClipPlane)}, \"far\": {F(cam.farClipPlane)}, ");
            sb.Append($"\"pose\": {{ \"position\": [{F(p.x)},{F(p.y)},{F(p.z)}], \"euler\": [{F(e.x)},{F(e.y)},{F(e.z)}] }}");
            var urdf = Object.FindFirstObjectByType<UrdfCameraPose>();
            if (urdf != null)
                sb.Append($", \"urdf_mount\": {{ \"xyz\": [{F(urdf.MountXyz.x)},{F(urdf.MountXyz.y)},{F(urdf.MountXyz.z)}], " +
                          $"\"rpy\": [{F(urdf.MountRpy.x)},{F(urdf.MountRpy.y)},{F(urdf.MountRpy.z)}] }}");
            sb.Append(" },\n");
        }

        var res = Object.FindFirstObjectByType<CaptureResolution>();
        if (res != null)
        {
            sb.Append("  \"resolution\": {");
            sb.Append($" \"width\": {res.width}, \"height\": {res.height}, ");
            sb.Append($"\"topic\": \"{Esc(res.resolutionTopic)}\" }},\n");
        }

        // E. environment
        var env = Object.FindFirstObjectByType<EnvironmentController>();
        if (env != null)
        {
            sb.Append("  \"environment\": {");
            sb.Append($" \"time_of_day\": {F(env.timeOfDay)}, \"weather\": \"{Esc(env.weather)}\", ");
            sb.Append($"\"cloudiness\": {F(env.cloudiness)}, \"fog\": {F(env.fog)}, \"wind\": {F(env.wind)}, ");
            sb.Append($"\"wave\": {F(env.waveHeight)}, \"rain\": {F(env.rain)}, ");
            sb.Append($"\"advance_rate\": {F(env.advanceRate)}, \"seed\": {env.lastSeed} }},\n");
        }

        // F. scene (from config/Scene.json)
        string scenePath = Path.Combine(Application.dataPath, "..", "config", "Scene.json");
        if (File.Exists(scenePath))
        {
            var sc = JsonUtility.FromJson<SceneConfig>(File.ReadAllText(scenePath));
            string mode = (sc?.objects != null && sc.objects.Count > 0) ? sc.objects[0].control_mode : "";
            int nObj = sc?.objects != null ? sc.objects.Count : 0;
            sb.Append("  \"scene\": {");
            sb.Append($" \"objects\": {nObj}, \"ego_control_mode\": \"{Esc(mode)}\"");
            if (sc?.environment != null)
                sb.Append($", \"config_env\": {{ \"wind_speed\": {F(sc.environment.wind_speed)}, " +
                          $"\"wave_height\": {F(sc.environment.wave_height)}, \"time_of_day\": \"{Esc(sc.environment.time_of_day)}\" }}");
            sb.Append(" },\n");
        }

        var occ = Object.FindFirstObjectByType<OccupancyGridPublisher>();
        if (occ != null)
        {
            sb.Append("  \"occupancy_grid\": {");
            sb.Append($" \"topic\": \"{Esc(occ.topic)}\", \"frame_id\": \"{Esc(occ.frameId)}\", ");
            sb.Append($"\"origin_x\": {F(occ.originX)}, \"origin_z\": {F(occ.originZ)}, ");
            sb.Append($"\"width_m\": {F(occ.widthMeters)}, \"height_m\": {F(occ.heightMeters)}, ");
            sb.Append($"\"resolution\": {F(occ.resolution)}, \"inflation_radius\": {F(occ.inflationRadius)} }},\n");
        }

        var posePub = Object.FindFirstObjectByType<EgoPosePublisher>();
        if (posePub != null)
        {
            sb.Append("  \"ego_pose_publisher\": {");
            sb.Append($" \"topic\": \"{Esc(posePub.topic)}\", \"frame_id\": \"{Esc(posePub.frameId)}\", ");
            sb.Append($"\"publish_hz\": {F(posePub.publishHz)} }},\n");
        }

        var auto = Object.FindFirstObjectByType<AutonomousBoatController>();
        if (auto != null)
        {
            sb.Append("  \"boat_controller\": {");
            sb.Append($" \"arrival_radius\": {F(auto.arrivalRadius)}, ");
            sb.Append($"\"heading_tolerance\": {F(auto.headingTolerance)}, ");
            sb.Append($"\"steer_power\": {F(auto.steerPower)}, ");
            sb.Append($"\"power\": {F(auto.power)}, \"max_speed\": {F(auto.maxSpeed)} }},\n");
        }

        // H. labels (distinct labels present in the scene)
        var set = new SortedSet<string>();
        foreach (var lab in Object.FindObjectsByType<Labeling>(FindObjectsSortMode.None))
            foreach (var s in lab.labels) set.Add(s);
        sb.Append("  \"labels\": { \"classes\": [");
        int i = 0; foreach (var s in set) sb.Append((i++ > 0 ? ", " : "") + $"\"{Esc(s)}\"");
        sb.Append("] },\n");

        if (ScenarioMetadataContext.HasScenario)
        {
            var sc = ScenarioMetadataContext.Current;
            sb.Append("  \"scenario\": {");
            sb.Append($" \"id\": \"{Esc(sc.id)}\", \"manifest_path\": \"{Esc(sc.manifest_path)}\", ");
            sb.Append($"\"weather\": \"{Esc(sc.weather)}\", \"weather_mode\": \"{Esc(sc.weather_mode)}\", ");
            sb.Append($"\"time_mode\": \"{Esc(sc.time_mode)}\", \"time_bucket\": \"{Esc(sc.time_bucket)}\", ");
            sb.Append($"\"time_start_of_day\": {F(sc.time_start_of_day)}, \"time_end_of_day\": {F(sc.time_end_of_day)}, ");
            sb.Append($"\"time_update_period_s\": {F(sc.time_update_period_s)}, ");
            sb.Append($"\"duration_s\": {F(sc.duration_s)}, \"capture_hz\": {F(sc.capture_hz)}, ");
            sb.Append($"\"track_count\": {sc.track_count}, \"area_type\": \"{Esc(sc.area_type)}\", ");
            sb.Append($"\"scenario_seed\": {sc.scenario_seed}, \"type_counts_json\": \"{Esc(sc.type_counts_json)}\" }},\n");
        }

        // I. system
        sb.Append("  \"system\": {");
        sb.Append($" \"unity\": \"{Esc(Application.unityVersion)}\", ");
        sb.Append($"\"platform\": \"{Application.platform}\", ");
        sb.Append($"\"quality\": \"{Esc(QualitySettings.names[QualitySettings.GetQualityLevel()])}\", ");
        sb.Append($"\"scene_name\": \"{Esc(UnityEngine.SceneManagement.SceneManager.GetActiveScene().name)}\" }}\n");

        sb.Append("}\n");

        string file = Path.Combine(outDir, $"run_metadata_{cameraKey}_{stamp}.json");
        File.WriteAllText(file, sb.ToString());
        Debug.Log($"[RunMetadata] wrote {file}");
    }

    public static string LatestSoloDir()
    {
        string root = Application.persistentDataPath;
        return TryGetLatestSoloDir(out string path) ? path : root;
    }

    public static bool TryGetLatestSoloDir(out string path)
    {
        string root = Application.persistentDataPath;
        string best = null;
        long bestT = 0;

        if (Directory.Exists(root))
        {
            foreach (var d in Directory.GetDirectories(root))
            {
                if (!Path.GetFileName(d).StartsWith("solo"))
                    continue;

                long t = Directory.GetLastWriteTime(d).Ticks;
                if (t > bestT)
                {
                    bestT = t;
                    best = d;
                }
            }
        }

        path = best;
        return !string.IsNullOrEmpty(best);
    }

    public static string ResolveCameraKey(PerceptionCamera pc)
    {
        if (pc == null)
            return "camera";

        string candidate = pc.gameObject.name;
        var cam = pc.GetComponent<Camera>();
        if (cam != null && !string.IsNullOrWhiteSpace(cam.name))
            candidate = cam.name;

        if (string.IsNullOrWhiteSpace(candidate))
            candidate = "camera";

        var sb = new StringBuilder(candidate.Length);
        foreach (char ch in candidate)
            sb.Append(char.IsLetterOrDigit(ch) ? char.ToLowerInvariant(ch) : '_');
        return sb.ToString().Trim('_');
    }

    static string F(float v) => v.ToString("0.####", CultureInfo.InvariantCulture);
    static string Esc(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
}
