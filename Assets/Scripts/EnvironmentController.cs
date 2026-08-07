using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Std;

// Programmatic time-of-day + marine weather for an HDRP scene.
// Writes overrides to its own high-priority runtime Volume so they win the blend
// and never dirty a project asset (sample scenes ship several competing Volumes).
public class EnvironmentController : MonoBehaviour
{
    [Header("Scene references (assign in Inspector)")]
    public Light sun;
    public WaterSurface water;
    public ParticleSystem rainParticles;     // optional

    [Header("Rain follow")]
    [Tooltip("Rain emitter tracks this transform's XZ. Falls back to Camera.main.")]
    public Transform rainFollowTarget;
    [Tooltip("Height the rain emitter is held at.")]
    public float rainHeight = 30f;
    [Tooltip("Meters the rain box is pushed ahead of the target, so rain fills the POV view.")]
    public float rainForwardOffset = 2f;

    [Header("Override volume")]
    [Tooltip("Runtime Volume priority. Keep above every other Volume in the scene.")]
    public float overridePriority = 1000f;

    [Header("Time of day")]
    [Range(0f, 24f)] public float timeOfDay = 12f;
    public float sunAzimuth        = 170f;
    public float daySunIntensity   = 100000f;
    public float nightSunIntensity = 0f;
    public float dawnDuskTempK     = 3200f;
    public float noonTempK         = 5500f;   // lower = warmer/less blue midday
    [Tooltip("Hours per real second (0 = frozen).")]
    public float advanceRate = 0f;

    [Header("Weather (sliders drive the scene live)")]
    public string weather = "clear";
    [Range(0f, 1f)] public float cloudiness = 0.1f;
    [Range(0f, 1f)] public float fog        = 0.05f;
    [Range(0f, 1f)] public float wind       = 0.2f;
    [Range(0f, 1f)] public float waveHeight = 0.2f;
    [Range(0f, 1f)] public float rain       = 0f;
    public float fogClearDistance = 5000f;
    public float fogThickDistance = 60f;
    [Tooltip("Lower = fog visible earlier on the slider (1 = plain exponential).")]
    [Range(0.15f, 1f)] public float fogSliderResponse = 0.45f;
    public float maxWindKmh       = 60f;
    public float maxRainRate      = 4000f;

    [Header("ROS")]
    public bool enableRos = true;
    public string timeTopic      = "/env/time_of_day";
    public string weatherTopic   = "/env/weather";
    public string randomizeTopic = "/env/randomize";
    public string stateTopic     = "/env/state";
    [Tooltip("Individual 0..1 setters (fog / wind / wave / cloud / rain).")]
    public string fogTopic       = "/env/fog";
    public string windTopic      = "/env/wind";
    public string waveTopic      = "/env/wave";
    public string cloudTopic     = "/env/cloudiness";
    public string rainTopic      = "/env/rain";

    ROSConnection ros;
    HDAdditionalLightData sunHd;

    // Runtime volume + profile.
    Volume envVolume;
    VolumeProfile envProfile;
    Fog fogOv;
    VolumeComponent cloudsOv;      // VolumetricClouds or CloudLayer, via reflection

    // preset -> (cloudiness, fog, wind, waveHeight, rain, sunDim)
    static readonly Dictionary<string, (float cloud, float fog, float wind, float wave, float rain, float sunDim)> Presets = new()
    {
        { "clear",    (0.05f, 0.03f, 0.2f, 0.15f, 0.0f, 1.00f) },
        { "cloudy",   (0.40f, 0.05f, 0.4f, 0.35f, 0.0f, 0.85f) },
        { "overcast", (0.85f, 0.15f, 0.5f, 0.50f, 0.0f, 0.50f) },
        { "foggy",    (0.50f, 0.75f, 0.3f, 0.25f, 0.0f, 0.60f) },
        { "stormy",   (1.00f, 0.40f, 0.9f, 0.90f, 0.8f, 0.35f) },
    };
    static readonly string[] PresetNames = { "clear", "cloudy", "overcast", "foggy", "stormy" };

    void Start()
    {
        ResolveReferences();
        EnsureOverrideVolume();

        if (enableRos)
        {
            ros = ROSConnection.GetOrCreateInstance();
            ros.Subscribe<Float32Msg>(timeTopic, m => SetTimeOfDay(m.data));
            ros.Subscribe<StringMsg>(weatherTopic, m => SetWeather(m.data));
            ros.Subscribe<Int32Msg>(randomizeTopic, m => Randomize(m.data));
            ros.Subscribe<Float32Msg>(fogTopic,   m => SetFog(m.data));
            ros.Subscribe<Float32Msg>(windTopic,  m => SetWind(m.data));
            ros.Subscribe<Float32Msg>(waveTopic,  m => SetWave(m.data));
            ros.Subscribe<Float32Msg>(cloudTopic, m => SetCloudiness(m.data));
            ros.Subscribe<Float32Msg>(rainTopic,  m => SetRain(m.data));
            ros.RegisterPublisher<StringMsg>(stateTopic);
        }

        Apply();
        PublishState();
        Debug.Log($"[Environment] ready — {weather} @ {timeOfDay:F1}h, sun={(sun ? sun.name : "NULL")}, overrideVolume={(envVolume ? "OK" : "NULL")}");
    }

    void OnDestroy()
    {
        // Clean up the runtime volume + profile.
        if (envVolume != null)
        {
            if (Application.isPlaying) Destroy(envVolume.gameObject);
            else DestroyImmediate(envVolume.gameObject);
        }
        if (envProfile != null)
        {
            if (Application.isPlaying) Destroy(envProfile);
            else DestroyImmediate(envProfile);
        }
    }

    void Update()
    {
        if (advanceRate != 0f)
        {
            timeOfDay = Mathf.Repeat(timeOfDay + advanceRate * Time.deltaTime, 24f);
            ApplyTimeOfDay();
        }
    }

    // Hold the rain emitter above the follow target, pointing straight down.
    void LateUpdate()
    {
        if (rainParticles == null) return;
        if (rainFollowTarget == null && Camera.main != null)
            rainFollowTarget = Camera.main.transform;
        if (rainFollowTarget == null) return;

        var p = rainFollowTarget.position;
        // Push ahead along the target's heading, flattened so pitch/roll doesn't shift rain height.
        var fwd = rainFollowTarget.forward; fwd.y = 0f;
        fwd = fwd.sqrMagnitude > 0.001f ? fwd.normalized : Vector3.forward;
        var center = new Vector3(p.x, rainHeight, p.z) + fwd * rainForwardOffset;
        rainParticles.transform.SetPositionAndRotation(
            center,
            Quaternion.Euler(90f, 0f, 0f));
    }

    // Live-apply on Inspector edit. Volume can't be created here, so until Start /
    // "Apply Now" runs, only the sun updates.
    void OnValidate()
    {
        if (!isActiveAndEnabled) return;
        if (sun == null) sun = RenderSettings.sun;
        if (sun != null && sunHd == null) sunHd = sun.GetComponent<HDAdditionalLightData>();
        if (envVolume != null) Apply();
        else ApplyTimeOfDay();
    }

    [ContextMenu("Apply Now")]
    void ApplyNow()
    {
        ResolveReferences();
        EnsureOverrideVolume();
        Apply();
        Debug.Log($"[Environment] Apply Now — sun={(sun ? sun.name : "NULL")}, time={timeOfDay:F1}h, weather={weather}, fogDist={CurrentFogDistance():F0}m");
    }

    void ResolveReferences()
    {
        if (sun == null) sun = RenderSettings.sun;
        if (sun != null) sunHd = sun.GetComponent<HDAdditionalLightData>();
        if (water == null) water = FindFirstObjectByType<WaterSurface>();
    }

    // Create a global Volume that outranks every other Volume in the scene.
    void EnsureOverrideVolume()
    {
        if (envVolume != null) return;

        var go = new GameObject("EnvOverrideVolume (runtime)");
        go.transform.SetParent(transform, false);
        go.layer = gameObject.layer;              // must be in the camera's Volume Mask
        // Edit mode: keep out of the saved scene. Play mode: leave visible in the Hierarchy.
        if (!Application.isPlaying) go.hideFlags = HideFlags.DontSave;

        envVolume = go.AddComponent<Volume>();
        envVolume.isGlobal = true;
        envVolume.priority = overridePriority;

        envProfile = ScriptableObject.CreateInstance<VolumeProfile>();
        envProfile.name = "EnvOverrideProfile (runtime)";
        if (!Application.isPlaying) envProfile.hideFlags = HideFlags.DontSave;
        envVolume.sharedProfile = envProfile;     // shared: avoid instance-cloning

        // Fog always; clouds only if the type exists in this HDRP version.
        fogOv = envProfile.Add<Fog>(false);

        var vcType = FindVolumeComponentType("VolumetricClouds");
        if (vcType != null) cloudsOv = envProfile.Add(vcType, false);
        else
        {
            var clType = FindVolumeComponentType("CloudLayer");
            if (clType != null) cloudsOv = envProfile.Add(clType, false);
        }
    }

    // ---- public API ----

    public void SetTimeOfDay(float hour)
    {
        timeOfDay = Mathf.Repeat(hour, 24f);
        Apply();
        PublishState();
    }

    public void SetWeather(string name)
    {
        name = (name ?? "").Trim().ToLower();
        if (!Presets.TryGetValue(name, out var p))
        {
            Debug.LogWarning($"[Environment] unknown weather '{name}' (use: {string.Join(", ", PresetNames)})");
            return;
        }
        weather = name;
        cloudiness = p.cloud; fog = p.fog; wind = p.wind; waveHeight = p.wave; rain = p.rain;
        Apply();
        PublishState();
    }

    // 0..1 setters (clamped).
    public void SetFog(float v)        { fog = Mathf.Clamp01(v);        Apply(); PublishState(); }
    public void SetWind(float v)       { wind = Mathf.Clamp01(v);       Apply(); PublishState(); }
    public void SetWave(float v)       { waveHeight = Mathf.Clamp01(v); Apply(); PublishState(); }
    public void SetCloudiness(float v) { cloudiness = Mathf.Clamp01(v); Apply(); PublishState(); }
    public void SetRain(float v)       { rain = Mathf.Clamp01(v);       Apply(); PublishState(); }

    [System.NonSerialized] public int lastSeed = -1;   // last Randomize seed, for run metadata

    public void Randomize(int seed)
    {
        lastSeed = seed;
        var rng = seed == 0 ? new System.Random() : new System.Random(seed);
        timeOfDay = 6f + (float)rng.NextDouble() * 12f;   // 06:00–18:00 so it stays daylit
        string name = PresetNames[rng.Next(PresetNames.Length)];
        var p = Presets[name];
        weather    = name;
        cloudiness = Jitter(rng, p.cloud);
        fog        = (float)rng.NextDouble();   // randomize fog across the full 0..1 range
        wind       = Jitter(rng, p.wind);
        waveHeight = Jitter(rng, p.wave);
        rain       = 0f;                        // no rain in the dataset — never randomize it
        Apply();
        PublishState();
        Debug.Log($"[Environment] randomize seed={seed} -> {weather} @ {timeOfDay:F1}h");
    }

    static float Jitter(System.Random rng, float v) =>
        Mathf.Clamp01(v + ((float)rng.NextDouble() - 0.5f) * 0.2f);

    // ---- apply ----

    void Apply() { ApplyTimeOfDay(); ApplyWeather(); }

    void ApplyTimeOfDay()
    {
        if (sun == null) return;
        float pitch = (timeOfDay - 6f) / 12f * 180f;   // 6h=sunrise, 12h=noon, 18h=sunset
        sun.transform.rotation = Quaternion.Euler(pitch, sunAzimuth, 0f);

        float daylight = Mathf.Clamp01(Mathf.Sin(pitch * Mathf.Deg2Rad));
        float sunDim   = Presets.TryGetValue(weather, out var p) ? p.sunDim : 1f;
        float intensity = Mathf.Lerp(nightSunIntensity, daySunIntensity, daylight) * sunDim;

        if (sunHd != null) sunHd.intensity = intensity;
        else sun.intensity = intensity;

        sun.useColorTemperature = true;
        sun.colorTemperature = Mathf.Lerp(dawnDuskTempK, noonTempK, daylight);
    }

    void ApplyWeather()
    {
        ApplyFog();
        ApplyClouds();
        ApplyWater();
        ApplyRain();
    }

    float CurrentFogDistance() =>
        // Exponential fog=0..1 -> clear..thick, bent by fogSliderResponse so fog appears early.
        fogClearDistance * Mathf.Pow(fogThickDistance / fogClearDistance,
                                     Mathf.Pow(fog, fogSliderResponse));

    void ApplyFog()
    {
        if (fogOv == null) return;
        fogOv.active = true;

        fogOv.enabled.overrideState = true;
        fogOv.enabled.value = true;

        fogOv.meanFreePath.overrideState = true;
        fogOv.meanFreePath.value = CurrentFogDistance();

        // Let distance fog reach the horizon.
        fogOv.maxFogDistance.overrideState = true;
        fogOv.maxFogDistance.value = Mathf.Max(fogClearDistance, 5000f);
    }

    // Clouds via reflection (HDRP cloud API varies -> no compile dependency).
    void ApplyClouds()
    {
        if (cloudsOv == null) return;
        if (cloudsOv.GetType().Name == "VolumetricClouds")
        {
            SetParam(cloudsOv, "enable", cloudiness > 0.02f);
            SetParam(cloudsOv, "densityMultiplier", cloudiness);
        }
        else // CloudLayer
        {
            SetParam(cloudsOv, "opacity", cloudiness);   // 0..1 cloud cover
        }
    }

    void ApplyWater()
    {
        if (water == null) return;
        SetFloatMember(water, "largeWindSpeed", wind * maxWindKmh);   // sea state / swell
        SetFloatMember(water, "largeBand0Multiplier", waveHeight);
        SetFloatMember(water, "largeBand1Multiplier", waveHeight);
    }

    void ApplyRain()
    {
        if (rainParticles == null) return;
        var emission = rainParticles.emission;
        emission.rateOverTime = rain * maxRainRate;
        if (rain > 0.01f && !rainParticles.isPlaying) rainParticles.Play();
        else if (rain <= 0.01f && rainParticles.isPlaying) rainParticles.Stop();
    }

    void PublishState()
    {
        if (ros == null) return;
        string json =
            $"{{\"time_of_day\":{timeOfDay:F1},\"weather\":\"{weather}\",\"cloudiness\":{cloudiness:F2}," +
            $"\"fog\":{fog:F2},\"wind\":{wind:F2},\"wave\":{waveHeight:F2},\"rain\":{rain:F2}}}";
        ros.Publish(stateTopic, new StringMsg(json));
    }

    // ---- diagnostics ----

    // Fog the renderer actually uses after blending; mismatch means something outranks us.
    [ContextMenu("Log Effective Fog")]
    void LogEffectiveFog()
    {
        var f = VolumeManager.instance.stack.GetComponent<Fog>();
        if (f == null) { Debug.Log("[Environment] no Fog in the volume stack"); return; }
        Debug.Log($"[Environment] EFFECTIVE fog: enabled={f.enabled.value}, " +
                  $"meanFreePath={f.meanFreePath.value:F0}m, maxFogDistance={f.maxFogDistance.value:F0}m " +
                  $"| slider target={CurrentFogDistance():F0}m");
    }

    [ContextMenu("Log Volumes")]
    void LogVolumes()
    {
        var vols = FindObjectsByType<Volume>(FindObjectsSortMode.None);
        var sb = new System.Text.StringBuilder($"[Environment] {vols.Length} Volume(s):\n");
        foreach (var v in vols)
        {
            var prof = v.sharedProfile;
            sb.AppendLine($"  '{v.name}' global={v.isGlobal} priority={v.priority} layer={LayerMask.LayerToName(v.gameObject.layer)} profile='{(prof ? prof.name : "NULL")}':");
            if (prof != null)
                foreach (var c in prof.components)
                    sb.AppendLine($"      - {c.GetType().Name}");
        }
        Debug.Log(sb.ToString());
    }

    // ---- reflection helpers (version-agnostic, no-op if the member is absent) ----

    static System.Type FindVolumeComponentType(string shortName)
    {
        foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
        {
            var t = asm.GetType("UnityEngine.Rendering.HighDefinition." + shortName);
            if (t != null && typeof(VolumeComponent).IsAssignableFrom(t)) return t;
        }
        return null;
    }

    static void SetParam(VolumeComponent comp, string field, object value, bool isEnumName = false)
    {
        if (comp == null) return;
        var fi = comp.GetType().GetField(field);
        if (fi == null) return;
        if (!(fi.GetValue(comp) is VolumeParameter param)) return;
        param.overrideState = true;
        var vp = fi.FieldType.GetProperty("value");
        if (vp == null || !vp.CanWrite) return;
        object v = value;
        if (isEnumName && value is string s)
        {
            try { v = System.Enum.Parse(vp.PropertyType, s, true); }
            catch { return; }
        }
        vp.SetValue(param, v);
    }

    static void SetFloatMember(object target, string name, float value)
    {
        var t = target.GetType();
        var f = t.GetField(name);
        if (f != null && f.FieldType == typeof(float)) { f.SetValue(target, value); return; }
        var p = t.GetProperty(name);
        if (p != null && p.CanWrite && p.PropertyType == typeof(float)) p.SetValue(target, value);
    }
}