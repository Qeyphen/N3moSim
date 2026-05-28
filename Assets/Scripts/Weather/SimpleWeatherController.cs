using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace N3mo.Weather
{
    public class SimpleWeatherController : MonoBehaviour
    {
        public enum WeatherPreset
        {
            Clear,
            Misty,
            Rainy,
            Stormy
        }

        [Header("References")]
        [SerializeField] private Volume globalVolume;
        [SerializeField] private Light directionalLight;
        [SerializeField] private SimpleRainController rainController;

        [Header("State")]
        [SerializeField] private WeatherPreset preset = WeatherPreset.Clear;
        [SerializeField] private bool applyOnStart = true;

        public WeatherPreset Preset => preset;

        public void Configure(Volume volume, Light sunLight, SimpleRainController rain)
        {
            globalVolume      = volume;
            directionalLight  = sunLight;
            rainController    = rain;
        }

        private void Start()
        {
            if (applyOnStart)
                ApplyPreset(preset);
        }

        [ContextMenu("Apply Clear")]
        public void ApplyClear() => ApplyPreset(WeatherPreset.Clear);

        [ContextMenu("Apply Misty")]
        public void ApplyMisty() => ApplyPreset(WeatherPreset.Misty);

        [ContextMenu("Apply Rainy")]
        public void ApplyRainy() => ApplyPreset(WeatherPreset.Rainy);

        [ContextMenu("Apply Stormy")]
        public void ApplyStormy() => ApplyPreset(WeatherPreset.Stormy);

        public void ApplyPreset(WeatherPreset nextPreset)
        {
            preset = nextPreset;

            if (globalVolume == null || globalVolume.sharedProfile == null)
            {
                Debug.LogWarning("[SimpleWeatherController] requires a global " +
                                 "HDRP Volume with a shared profile.");
                return;
            }

            globalVolume.sharedProfile.TryGet(out Fog fog);
            globalVolume.sharedProfile.TryGet(out PhysicallyBasedSky sky);
            globalVolume.sharedProfile.TryGet(out Exposure exposure);

            switch (preset)
            {
                // ── CLEAR ─────────────────────────────────────────────────
                // Bright sunny day, crisp horizon, no fog
                case WeatherPreset.Clear:
                    ApplyFog(fog,
                        baseHeight:    100f,
                        maxHeight:     500f,
                        meanFreePath:  2000f,
                        color:         new Color(0.78f, 0.91f, 1f),
                        volumetric:    true);
                    ApplySky(sky,
                        groundTint:    new Color(0.29f, 0.36f, 0.44f),
                        anisotropy:    0.8f);
                    ApplyExposure(exposure, 14f);
                    ApplySun(120000f, 6500f, Color.white);
                    ApplyRain(0f);
                    break;

                // ── MISTY ─────────────────────────────────────────────────
                // Dense sea fog, visibility reduced to ~100m
                // Sun barely visible as a bright patch in the grey
                case WeatherPreset.Misty:
                    ApplyFog(fog,
                        baseHeight:    0f,
                        maxHeight:     60f,
                        meanFreePath:  80f,
                        color:         new Color(0.88f, 0.90f, 0.92f),
                        volumetric:    true);
                    ApplySky(sky,
                        groundTint:    new Color(0.75f, 0.78f, 0.80f),
                        anisotropy:    0.5f);
                    ApplyExposure(exposure, 12.5f);
                    ApplySun(35000f, 6000f, new Color(1f, 0.98f, 0.95f));
                    ApplyRain(0f);
                    break;

                // ── RAINY ─────────────────────────────────────────────────
                // Overcast, heavy rain, low visibility
                // Sky dark grey, sun heavily diffused
                case WeatherPreset.Rainy:
                    ApplyFog(fog,
                        baseHeight:    5f,
                        maxHeight:     80f,
                        meanFreePath:  150f,
                        color:         new Color(0.60f, 0.65f, 0.70f),
                        volumetric:    true);
                    ApplySky(sky,
                        groundTint:    new Color(0.18f, 0.22f, 0.28f),
                        anisotropy:    0.4f);
                    ApplyExposure(exposure, 11.5f);
                    ApplySun(20000f, 7500f, new Color(0.80f, 0.85f, 1f));
                    ApplyRain(1.0f);
                    break;

                // ── STORMY ────────────────────────────────────────────────
                // Very dark, severe weather, near zero visibility at distance
                // Heavy rain, almost no sun
                case WeatherPreset.Stormy:
                    ApplyFog(fog,
                        baseHeight:    0f,
                        maxHeight:     60f,
                        meanFreePath:  80f,
                        color:         new Color(0.45f, 0.50f, 0.55f),
                        volumetric:    true);
                    ApplySky(sky,
                        groundTint:    new Color(0.10f, 0.12f, 0.16f),
                        anisotropy:    0.35f);
                    ApplyExposure(exposure, 10.5f);
                    ApplySun(8000f, 8000f, new Color(0.70f, 0.75f, 0.90f));
                    ApplyRain(1.0f);
                    break;
            }

            Debug.Log($"[SimpleWeatherController] applied preset: {preset}");
        }

        public void ApplyPresetByName(string presetName)
        {
            if (string.IsNullOrWhiteSpace(presetName))
            {
                ApplyPreset(WeatherPreset.Clear);
                return;
            }

            if (System.Enum.TryParse(presetName, true, out WeatherPreset parsedPreset))
            {
                ApplyPreset(parsedPreset);
                return;
            }

            switch (presetName.Trim().ToLowerInvariant())
            {
                case "day":
                case "clear":
                    ApplyPreset(WeatherPreset.Clear);
                    break;
                case "mist":
                case "misty":
                case "fog":
                case "foggy":
                    ApplyPreset(WeatherPreset.Misty);
                    break;
                case "rain":
                case "rainy":
                case "overcast":
                    ApplyPreset(WeatherPreset.Rainy);
                    break;
                case "storm":
                case "stormy":
                    ApplyPreset(WeatherPreset.Stormy);
                    break;
                case "night":
                    ApplyPreset(WeatherPreset.Clear);
                    break;
                default:
                    ApplyPreset(WeatherPreset.Clear);
                    break;
            }
        }

        private void ApplyFog(
            Fog   fog,
            float baseHeight,
            float maxHeight,
            float meanFreePath,
            Color color,
            bool  volumetric)
        {
            if (fog == null) return;

            fog.enabled.Override(true);
            fog.enableVolumetricFog.Override(volumetric);
            fog.baseHeight.Override(baseHeight);
            fog.maximumHeight.Override(maxHeight);
            fog.meanFreePath.Override(meanFreePath);
            fog.albedo.Override(color);
            fog.maxFogDistance.Override(5000f);
            fog.depthExtent.Override(64f);
        }

        private void ApplySky(
            PhysicallyBasedSky sky,
            Color              groundTint,
            float              anisotropy)
        {
            if (sky == null) return;

            sky.groundTint.Override(groundTint);
            sky.aerosolAnisotropy.Override(anisotropy);
        }

        private void ApplyExposure(Exposure exposure, float fixedExposure)
        {
            if (exposure == null) return;

            exposure.mode.Override(ExposureMode.Fixed);
            exposure.fixedExposure.Override(fixedExposure);
        }

        private void ApplySun(
            float intensityLux,
            float colorTemperature,
            Color color)
        {
            if (directionalLight == null) return;

            directionalLight.intensity        = intensityLux;
            directionalLight.colorTemperature = colorTemperature;
            directionalLight.color            = color;
        }

        private void ApplyRain(float rainIntensity)
        {
            if (rainController != null)
                rainController.Intensity = rainIntensity;
        }
    }
}