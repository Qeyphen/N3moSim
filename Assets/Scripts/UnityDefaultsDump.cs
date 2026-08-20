using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using UnityEngine;
using UnityEngine.Perception.GroundTruth;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

public static class UnityDefaultsDump
{
    static bool written;
    static string cachedJson;
    static string cachedStamp;

    public static void WriteOnce(PerceptionCamera pc)
    {
        if (written) return;
        try
        {
            CacheInternal(pc);
            written = true;
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[UnityDefaultsDump] failed: {e.Message}");
        }
    }

    public static void FlushToSolo()
    {
        if (string.IsNullOrEmpty(cachedJson))
            return;
        string dir = RunMetadata.LatestSoloDir();
        if (string.IsNullOrEmpty(dir))
        {
            Debug.LogWarning("[UnityDefaultsDump] no SOLO folder yet; keeping cached defaults only.");
            return;
        }
        Directory.CreateDirectory(dir);
        string path = Path.Combine(dir, $"unity_defaults_{cachedStamp}.json");
        if (File.Exists(path))
            return;
        File.WriteAllText(path, cachedJson);
        Debug.Log($"[UnityDefaultsDump] wrote {path}");
    }

    static void CacheInternal(PerceptionCamera pc)
    {
        cachedStamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
        var root = new Dictionary<string, object>
        {
            ["written_at"] = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            ["application"] = BuildApplicationSection(),
            ["scene"] = BuildSceneSection(),
            ["screen"] = BuildScreenSection(),
            ["quality"] = BuildQualitySection(),
            ["time"] = BuildTimeSection(),
            ["physics"] = BuildPhysicsSection(),
            ["rendering"] = BuildRenderingSection(),
            ["counts"] = BuildCountsSection(),
            ["scene_config"] = BuildSceneConfigSection(),
            ["components"] = BuildComponentsSection(pc),
            ["cameras"] = BuildCameraSection(),
            ["project_settings_files"] = BuildProjectSettingsSection(),
        };

        cachedJson = ToJson(root);
        Debug.Log("[UnityDefaultsDump] cached startup defaults for later write into SOLO.");
    }

    static Dictionary<string, object> BuildApplicationSection()
    {
        return new Dictionary<string, object>
        {
            ["unity_version"] = Application.unityVersion,
            ["platform"] = Application.platform.ToString(),
            ["product_name"] = Application.productName,
            ["company_name"] = Application.companyName,
            ["data_path"] = Application.dataPath,
            ["persistent_data_path"] = Application.persistentDataPath,
            ["streaming_assets_path"] = Application.streamingAssetsPath,
            ["target_frame_rate"] = Application.targetFrameRate,
            ["run_in_background"] = Application.runInBackground,
            ["is_playing"] = Application.isPlaying,
            ["is_editor"] = Application.isEditor,
            ["genuine"] = Application.genuine,
            ["genuine_check_available"] = Application.genuineCheckAvailable,
        };
    }

    static Dictionary<string, object> BuildSceneSection()
    {
        var active = SceneManager.GetActiveScene();
        var loaded = new List<object>();
        for (int i = 0; i < SceneManager.sceneCount; i++)
        {
            var sc = SceneManager.GetSceneAt(i);
            loaded.Add(new Dictionary<string, object>
            {
                ["name"] = sc.name,
                ["path"] = sc.path,
                ["is_loaded"] = sc.isLoaded,
                ["root_count"] = sc.rootCount,
            });
        }

        return new Dictionary<string, object>
        {
            ["active_name"] = active.name,
            ["active_path"] = active.path,
            ["active_build_index"] = active.buildIndex,
            ["loaded_scenes"] = loaded,
        };
    }

    static Dictionary<string, object> BuildScreenSection()
    {
        var resolutions = new List<object>();
        foreach (var res in Screen.resolutions)
        {
            resolutions.Add(new Dictionary<string, object>
            {
                ["width"] = res.width,
                ["height"] = res.height,
                ["refresh_rate"] = res.refreshRateRatio.value,
            });
        }

        return new Dictionary<string, object>
        {
            ["width"] = Screen.width,
            ["height"] = Screen.height,
            ["dpi"] = Screen.dpi,
            ["fullscreen"] = Screen.fullScreen,
            ["fullscreen_mode"] = Screen.fullScreenMode.ToString(),
            ["current_resolution"] = new Dictionary<string, object>
            {
                ["width"] = Screen.currentResolution.width,
                ["height"] = Screen.currentResolution.height,
                ["refresh_rate"] = Screen.currentResolution.refreshRateRatio.value,
            },
            ["available_resolutions"] = resolutions,
        };
    }

    static Dictionary<string, object> BuildQualitySection()
    {
        var names = new List<object>();
        foreach (var n in QualitySettings.names) names.Add(n);

        return new Dictionary<string, object>
        {
            ["active_level"] = QualitySettings.GetQualityLevel(),
            ["active_name"] = QualitySettings.names[QualitySettings.GetQualityLevel()],
            ["all_names"] = names,
            ["v_sync_count"] = QualitySettings.vSyncCount,
            ["anti_aliasing"] = QualitySettings.antiAliasing,
            ["master_texture_limit"] = QualitySettings.globalTextureMipmapLimit,
            ["anisotropic_filtering"] = QualitySettings.anisotropicFiltering.ToString(),
            ["lod_bias"] = QualitySettings.lodBias,
            ["pixel_light_count"] = QualitySettings.pixelLightCount,
            ["shadow_distance"] = QualitySettings.shadowDistance,
            ["skin_weights"] = QualitySettings.skinWeights.ToString(),
            ["active_color_space"] = QualitySettings.activeColorSpace.ToString(),
            ["desired_color_space"] = QualitySettings.desiredColorSpace.ToString(),
        };
    }

    static Dictionary<string, object> BuildTimeSection()
    {
        return new Dictionary<string, object>
        {
            ["time_scale"] = Time.timeScale,
            ["fixed_delta_time"] = Time.fixedDeltaTime,
            ["maximum_delta_time"] = Time.maximumDeltaTime,
            ["maximum_particle_delta_time"] = Time.maximumParticleDeltaTime,
            ["capture_framerate"] = Time.captureFramerate,
            ["in_fixed_time_step"] = Time.inFixedTimeStep,
        };
    }

    static Dictionary<string, object> BuildPhysicsSection()
    {
        return new Dictionary<string, object>
        {
            ["gravity"] = Physics.gravity,
            ["default_contact_offset"] = Physics.defaultContactOffset,
            ["sleep_threshold"] = Physics.sleepThreshold,
            ["bounce_threshold"] = Physics.bounceThreshold,
            ["default_solver_iterations"] = Physics.defaultSolverIterations,
            ["default_solver_velocity_iterations"] = Physics.defaultSolverVelocityIterations,
            ["queries_hit_backfaces"] = Physics.queriesHitBackfaces,
            ["queries_hit_triggers"] = Physics.queriesHitTriggers,
            ["auto_sync_transforms"] = Physics.autoSyncTransforms,
        };
    }

    static Dictionary<string, object> BuildRenderingSection()
    {
        return new Dictionary<string, object>
        {
            ["default_render_pipeline"] = NameOrNull(GraphicsSettings.defaultRenderPipeline),
            ["current_render_pipeline"] = NameOrNull(GraphicsSettings.currentRenderPipeline),
            ["quality_render_pipeline"] = NameOrNull(QualitySettings.renderPipeline),
            ["realtime_gi"] = DynamicGI.isConverged,
            ["scalable_buffer_width"] = ScalableBufferManager.widthScaleFactor,
            ["scalable_buffer_height"] = ScalableBufferManager.heightScaleFactor,
            ["fog_enabled"] = RenderSettings.fog,
            ["ambient_mode"] = RenderSettings.ambientMode.ToString(),
            ["reflection_intensity"] = RenderSettings.reflectionIntensity,
            ["sun"] = RenderSettings.sun != null ? BuildObjectRef(RenderSettings.sun) : null,
        };
    }

    static Dictionary<string, object> BuildCountsSection()
    {
        return new Dictionary<string, object>
        {
            ["root_game_objects"] = SceneManager.GetActiveScene().rootCount,
            ["camera_count"] = UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsSortMode.None).Length,
            ["perception_camera_count"] = UnityEngine.Object.FindObjectsByType<PerceptionCamera>(FindObjectsSortMode.None).Length,
            ["light_count"] = UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Length,
            ["labeling_count"] = UnityEngine.Object.FindObjectsByType<UnityEngine.Perception.GroundTruth.LabelManagement.Labeling>(FindObjectsSortMode.None).Length,
        };
    }

    static Dictionary<string, object> BuildSceneConfigSection()
    {
        string scenePath = Path.Combine(Application.dataPath, "..", "config", "Scene.json");
        var data = new Dictionary<string, object>
        {
            ["path"] = scenePath,
            ["exists"] = File.Exists(scenePath),
        };
        if (File.Exists(scenePath))
        {
            string text = File.ReadAllText(scenePath);
            data["size_bytes"] = text.Length;
            data["raw_json"] = text;
        }
        return data;
    }

    static Dictionary<string, object> BuildComponentsSection(PerceptionCamera pc)
    {
        var section = new Dictionary<string, object>();
        AddComponentSnapshots(section, "environment_controller", UnityEngine.Object.FindObjectsByType<EnvironmentController>(FindObjectsSortMode.None));
        AddComponentSnapshots(section, "dataset_capture_scheduler", UnityEngine.Object.FindObjectsByType<DatasetCaptureScheduler>(FindObjectsSortMode.None));
        AddComponentSnapshots(section, "capture_resolution", UnityEngine.Object.FindObjectsByType<CaptureResolution>(FindObjectsSortMode.None));
        AddComponentSnapshots(section, "occupancy_grid_publisher", UnityEngine.Object.FindObjectsByType<OccupancyGridPublisher>(FindObjectsSortMode.None));
        AddComponentSnapshots(section, "ego_pose_publisher", UnityEngine.Object.FindObjectsByType<EgoPosePublisher>(FindObjectsSortMode.None));
        AddComponentSnapshots(section, "urdf_camera_pose", UnityEngine.Object.FindObjectsByType<UrdfCameraPose>(FindObjectsSortMode.None));
        AddComponentSnapshots(section, "autonomous_boat_controller", UnityEngine.Object.FindObjectsByType<AutonomousBoatController>(FindObjectsSortMode.None));
        AddComponentSnapshots(section, "track_spawner", UnityEngine.Object.FindObjectsByType<TrackSpawner>(FindObjectsSortMode.None));

        if (pc != null)
            section["active_perception_camera"] = SnapshotComponent(pc);

        return section;
    }

    static List<object> BuildCameraSection()
    {
        var items = new List<object>();
        foreach (var cam in UnityEngine.Object.FindObjectsByType<Camera>(FindObjectsSortMode.None))
        {
            items.Add(new Dictionary<string, object>
            {
                ["name"] = cam.name,
                ["path"] = GameObjectPath(cam.transform),
                ["enabled"] = cam.enabled,
                ["tag"] = cam.tag,
                ["depth"] = cam.depth,
                ["field_of_view"] = cam.fieldOfView,
                ["near_clip"] = cam.nearClipPlane,
                ["far_clip"] = cam.farClipPlane,
                ["aspect"] = cam.aspect,
                ["orthographic"] = cam.orthographic,
                ["pixel_width"] = cam.pixelWidth,
                ["pixel_height"] = cam.pixelHeight,
                ["target_texture"] = cam.targetTexture != null ? cam.targetTexture.name : null,
                ["position"] = cam.transform.position,
                ["rotation"] = cam.transform.eulerAngles,
            });
        }
        return items;
    }

    static List<object> BuildProjectSettingsSection()
    {
        string root = Path.Combine(Application.dataPath, "..", "ProjectSettings");
        string[] files =
        {
            "ProjectSettings.asset",
            "QualitySettings.asset",
            "TimeManager.asset",
            "TagManager.asset",
            "GraphicsSettings.asset",
            "InputManager.asset",
            "DynamicsManager.asset",
            "EditorBuildSettings.asset",
            "HDRPProjectSettings.asset",
        };

        var items = new List<object>();
        foreach (string name in files)
        {
            string path = Path.Combine(root, name);
            var entry = new Dictionary<string, object>
            {
                ["path"] = path,
                ["exists"] = File.Exists(path),
            };
            if (File.Exists(path))
            {
                string text = File.ReadAllText(path);
                entry["size_bytes"] = text.Length;
                entry["raw_text"] = text;
            }
            items.Add(entry);
        }
        return items;
    }

    static void AddComponentSnapshots<T>(Dictionary<string, object> dst, string key, T[] components) where T : Component
    {
        var items = new List<object>();
        foreach (var comp in components)
            items.Add(SnapshotComponent(comp));
        dst[key] = items;
    }

    static Dictionary<string, object> SnapshotComponent(Component comp)
    {
        var fields = new Dictionary<string, object>();
        var flags = BindingFlags.Instance | BindingFlags.Public;
        foreach (var field in comp.GetType().GetFields(flags))
        {
            try { fields[field.Name] = MakeJsonFriendly(field.GetValue(comp), 0); }
            catch (Exception e) { fields[field.Name] = $"<error: {e.Message}>"; }
        }

        return new Dictionary<string, object>
        {
            ["type"] = comp.GetType().FullName,
            ["name"] = comp.name,
            ["game_object"] = comp.gameObject.name,
            ["path"] = GameObjectPath(comp.transform),
            ["enabled"] = comp is Behaviour b ? b.enabled : true,
            ["fields"] = fields,
        };
    }

    static object MakeJsonFriendly(object value, int depth)
    {
        if (value == null) return null;
        if (depth > 4) return "<max_depth>";

        Type t = value.GetType();
        if (value is string || value is bool) return value;
        if (t.IsEnum) return value.ToString();
        if (value is int || value is long || value is uint || value is ulong ||
            value is short || value is ushort || value is byte || value is sbyte)
            return value;
        if (value is float f) return float.IsNaN(f) || float.IsInfinity(f) ? null : f;
        if (value is double d) return double.IsNaN(d) || double.IsInfinity(d) ? null : d;
        if (value is decimal) return value;

        if (value is Vector2 v2) return new Dictionary<string, object> { ["x"] = v2.x, ["y"] = v2.y };
        if (value is Vector3 v3) return new Dictionary<string, object> { ["x"] = v3.x, ["y"] = v3.y, ["z"] = v3.z };
        if (value is Vector4 v4) return new Dictionary<string, object> { ["x"] = v4.x, ["y"] = v4.y, ["z"] = v4.z, ["w"] = v4.w };
        if (value is Quaternion q) return new Dictionary<string, object> { ["x"] = q.x, ["y"] = q.y, ["z"] = q.z, ["w"] = q.w, ["euler"] = q.eulerAngles };
        if (value is Color c) return new Dictionary<string, object> { ["r"] = c.r, ["g"] = c.g, ["b"] = c.b, ["a"] = c.a };
        if (value is Bounds b) return new Dictionary<string, object> { ["center"] = b.center, ["size"] = b.size, ["extents"] = b.extents };

        if (value is UnityEngine.Object obj) return BuildObjectRef(obj);

        if (value is IList list)
        {
            var items = new List<object>();
            foreach (var item in list)
                items.Add(MakeJsonFriendly(item, depth + 1));
            return items;
        }

        if (t.IsArray)
        {
            var items = new List<object>();
            foreach (var item in (IEnumerable)value)
                items.Add(MakeJsonFriendly(item, depth + 1));
            return items;
        }

        return value.ToString();
    }

    static Dictionary<string, object> BuildObjectRef(UnityEngine.Object obj)
    {
        string path = null;
        if (obj is Component comp) path = GameObjectPath(comp.transform);
        else if (obj is GameObject go) path = GameObjectPath(go.transform);

        return new Dictionary<string, object>
        {
            ["type"] = obj.GetType().FullName,
            ["name"] = obj.name,
            ["path"] = path,
        };
    }

    static string NameOrNull(UnityEngine.Object obj) => obj != null ? obj.name : null;

    static string GameObjectPath(Transform t)
    {
        if (t == null) return null;
        var parts = new List<string>();
        while (t != null)
        {
            parts.Add(t.name);
            t = t.parent;
        }
        parts.Reverse();
        return string.Join("/", parts);
    }

    static string ToJson(object value)
    {
        var sb = new StringBuilder();
        AppendJson(sb, value, 0);
        sb.Append('\n');
        return sb.ToString();
    }

    static void AppendJson(StringBuilder sb, object value, int indent)
    {
        if (value == null) { sb.Append("null"); return; }

        switch (value)
        {
            case string s:
                sb.Append('"').Append(Esc(s)).Append('"');
                return;
            case bool b:
                sb.Append(b ? "true" : "false");
                return;
            case int or long or uint or ulong or short or ushort or byte or sbyte:
                sb.Append(Convert.ToString(value, CultureInfo.InvariantCulture));
                return;
            case float f:
                sb.Append(f.ToString("0.####", CultureInfo.InvariantCulture));
                return;
            case double d:
                sb.Append(d.ToString("0.####", CultureInfo.InvariantCulture));
                return;
            case decimal m:
                sb.Append(m.ToString(CultureInfo.InvariantCulture));
                return;
            case IDictionary<string, object> dict:
                AppendDict(sb, dict, indent);
                return;
            case IList list:
                AppendList(sb, list, indent);
                return;
        }

        sb.Append('"').Append(Esc(value.ToString())).Append('"');
    }

    static void AppendDict(StringBuilder sb, IDictionary<string, object> dict, int indent)
    {
        sb.Append("{");
        if (dict.Count == 0) { sb.Append("}"); return; }
        sb.Append('\n');
        int i = 0;
        foreach (var kv in dict)
        {
            sb.Append(new string(' ', indent + 2));
            sb.Append('"').Append(Esc(kv.Key)).Append("\": ");
            AppendJson(sb, kv.Value, indent + 2);
            if (++i < dict.Count) sb.Append(",");
            sb.Append('\n');
        }
        sb.Append(new string(' ', indent)).Append("}");
    }

    static void AppendList(StringBuilder sb, IList list, int indent)
    {
        sb.Append("[");
        if (list.Count == 0) { sb.Append("]"); return; }
        sb.Append('\n');
        for (int i = 0; i < list.Count; i++)
        {
            sb.Append(new string(' ', indent + 2));
            AppendJson(sb, list[i], indent + 2);
            if (i + 1 < list.Count) sb.Append(",");
            sb.Append('\n');
        }
        sb.Append(new string(' ', indent)).Append("]");
    }

    static string Esc(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r");
}
