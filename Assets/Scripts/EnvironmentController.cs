using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Std;
using N3mo.Weather;
using UnityEngine.Rendering.HighDefinition;

/// <summary>
/// Receives environment update messages from ROS2 and
/// drives SimpleWeatherController, SimpleDayNightCycle
/// and WaterSurface in real time.
///
/// Message layout (Float32MultiArray):
///   [0] unused
///   [1] unused
///   [2] wave_height     0-5 metres
///   [3] time_of_day     0-24 hours
///   [4] flag:
///       0.0  = gradual transition
///       1.0  = instant snap
///       10.0 = apply Clear preset
///       11.0 = apply Misty preset
///       12.0 = apply Rainy preset
///       13.0 = apply Stormy preset
/// </summary>
public class EnvironmentController : MonoBehaviour
{
    [Header("ROS2")]
    public string topic = "/environment/update";

    [Header("Transition Speed")]
    public float waveTransitionSpeed = 1.0f;
    public float timeTransitionSpeed = 0.5f;

    [Header("Scene References — auto-found at runtime")]
    public WaterSurface            waterSurface;
    public SimpleWeatherController weatherController;
    public SimpleDayNightCycle     dayNightCycle;

    [Header("Debug — current values")]
    [SerializeField] private float currentWaveHeight = 1.0f;
    [SerializeField] private float currentTimeOfDay  = 12f;

    private float targetWaveHeight;
    private float targetTimeOfDay;
    private bool  snapToTarget = false;

    private ROSConnection ros;

    void Start()
    {
        targetWaveHeight = currentWaveHeight;
        targetTimeOfDay  = currentTimeOfDay;

        if (waterSurface == null)
            waterSurface = FindFirstObjectByType<WaterSurface>();

        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<Float32MultiArrayMsg>(topic, OnEnvironmentUpdate);

        StartCoroutine(FindRuntimeComponents());
    }

    System.Collections.IEnumerator FindRuntimeComponents()
    {
        yield return null;

        var runtimeWeather = GameObject.Find("RuntimeWeather");
        if (runtimeWeather != null)
        {
            if (weatherController == null)
                weatherController = runtimeWeather
                    .GetComponent<SimpleWeatherController>();

            if (dayNightCycle == null)
                dayNightCycle = runtimeWeather
                    .GetComponent<SimpleDayNightCycle>();
        }

        Debug.Log($"[EnvironmentController] ready:" +
                  $"\n  WaterSurface     : {(waterSurface      != null ? waterSurface.name      : "NOT FOUND")}" +
                  $"\n  WeatherController: {(weatherController != null ? weatherController.name : "NOT FOUND")}" +
                  $"\n  DayNightCycle    : {(dayNightCycle     != null ? dayNightCycle.name      : "NOT FOUND")}");

        ApplyToScene();
    }

    void OnEnvironmentUpdate(Float32MultiArrayMsg msg)
    {
        if (msg.data.Length < 5) return;

        float newWaveHeight = Mathf.Clamp(msg.data[2], 0f, 5f);
        float newTimeOfDay  = Mathf.Clamp(msg.data[3], 0f, 24f);
        float flag          = msg.data[4];
        bool  newSnap       = flag > 0.5f && flag < 9.5f;
        bool  isPreset      = flag >= 9.5f;

        // ── apply weather preset ──────────────────────────────
        if (isPreset && weatherController != null)
        {
            int presetCode = Mathf.RoundToInt(flag) - 10;
            var presets    = new[]
            {
                SimpleWeatherController.WeatherPreset.Clear,
                SimpleWeatherController.WeatherPreset.Misty,
                SimpleWeatherController.WeatherPreset.Rainy,
                SimpleWeatherController.WeatherPreset.Stormy
            };
            if (presetCode >= 0 && presetCode < presets.Length)
            {
                weatherController.ApplyPreset(presets[presetCode]);
                Debug.Log($"[EnvironmentController] preset → {presets[presetCode]}");
            }
        }

        bool changed =
            !Mathf.Approximately(newWaveHeight, targetWaveHeight) ||
            !Mathf.Approximately(newTimeOfDay,  targetTimeOfDay);

        targetWaveHeight = newWaveHeight;
        targetTimeOfDay  = newTimeOfDay;
        snapToTarget     = newSnap;

        if (newSnap)
        {
            currentWaveHeight = targetWaveHeight;
            currentTimeOfDay  = targetTimeOfDay;
            ApplyToScene();
            Debug.Log($"[EnvironmentController] SNAP:" +
                      $" waves={currentWaveHeight:F2}m" +
                      $" time={currentTimeOfDay:F1}h");
        }
        else if (changed)
        {
            Debug.Log($"[EnvironmentController] gradual →" +
                      $" waves={targetWaveHeight:F2}m" +
                      $" time={targetTimeOfDay:F1}h");
        }
    }

    void Update()
    {
        if (snapToTarget) return;

        bool changed = false;

        if (!Mathf.Approximately(currentWaveHeight, targetWaveHeight))
        {
            currentWaveHeight = Mathf.MoveTowards(
                currentWaveHeight, targetWaveHeight,
                waveTransitionSpeed * Time.deltaTime);
            changed = true;
        }

        if (!Mathf.Approximately(currentTimeOfDay, targetTimeOfDay))
        {
            currentTimeOfDay = Mathf.MoveTowards(
                currentTimeOfDay, targetTimeOfDay,
                timeTransitionSpeed * Time.deltaTime);
            changed = true;
        }

        if (changed)
            ApplyToScene();
    }

    void ApplyToScene()
    {
        ApplyWaves();
        ApplyTimeOfDay();
    }

    void ApplyWaves()
    {
        if (waterSurface == null) return;

        // timeMultiplier: 0.5=calm, 1.0=normal, 3.0=very rough
        waterSurface.timeMultiplier = Mathf.Lerp(
            0.5f, 3.0f, currentWaveHeight / 5f);
    }

    void ApplyTimeOfDay()
    {
        if (dayNightCycle == null) return;
        dayNightCycle.SetTimeOfDay(currentTimeOfDay);
    }
}