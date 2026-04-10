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
            globalVolume = volume;
            directionalLight = sunLight;
            rainController = rain;
        }

        private void Start()
        {
            if (applyOnStart)
            {
                ApplyPreset(preset);
            }
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
                Debug.LogWarning("SimpleWeatherController requires a global HDRP Volume with a shared profile.");
                return;
            }

            globalVolume.sharedProfile.TryGet(out Fog fog);
            globalVolume.sharedProfile.TryGet(out PhysicallyBasedSky sky);
            globalVolume.sharedProfile.TryGet(out Exposure exposure);

            switch (preset)
            {
                case WeatherPreset.Clear:
                    ApplyFog(fog, 100f, 500f, 2000f, new Color(0.78f, 0.91f, 1f), true);
                    ApplySky(sky, new Color(0.29f, 0.36f, 0.44f), 0.8f);
                    ApplyExposure(exposure, 14f);
                    ApplySun(120000f, 6500f, Color.white);
                    ApplyRain(0f);
                    break;
                case WeatherPreset.Misty:
                    ApplyFog(fog, 40f, 250f, 900f, new Color(0.83f, 0.88f, 0.92f), true);
                    ApplySky(sky, new Color(0.32f, 0.38f, 0.43f), 0.7f);
                    ApplyExposure(exposure, 13.5f);
                    ApplySun(90000f, 6200f, new Color(1f, 0.97f, 0.93f));
                    ApplyRain(0f);
                    break;
                case WeatherPreset.Rainy:
                    ApplyFog(fog, 20f, 180f, 450f, new Color(0.72f, 0.8f, 0.86f), true);
                    ApplySky(sky, new Color(0.24f, 0.29f, 0.35f), 0.55f);
                    ApplyExposure(exposure, 13f);
                    ApplySun(50000f, 7000f, new Color(0.92f, 0.95f, 1f));
                    ApplyRain(0.65f);
                    break;
                case WeatherPreset.Stormy:
                    ApplyFog(fog, 10f, 140f, 250f, new Color(0.65f, 0.72f, 0.8f), true);
                    ApplySky(sky, new Color(0.17f, 0.2f, 0.24f), 0.45f);
                    ApplyExposure(exposure, 12.5f);
                    ApplySun(25000f, 7500f, new Color(0.85f, 0.9f, 1f));
                    ApplyRain(1f);
                    break;
            }
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

        private void ApplyFog(Fog fog, float baseHeightValue, float maximumHeightValue, float meanFreePathValue, Color albedoColor, bool volumetric)
        {
            if (fog == null)
            {
                return;
            }

            fog.enabled.Override(true);
            fog.enableVolumetricFog.Override(volumetric);
            fog.baseHeight.Override(baseHeightValue);
            fog.maximumHeight.Override(maximumHeightValue);
            fog.meanFreePath.Override(meanFreePathValue);
            fog.albedo.Override(albedoColor);
            fog.maxFogDistance.Override(5000f);
            fog.depthExtent.Override(64f);
        }

        private void ApplySky(PhysicallyBasedSky sky, Color groundTintColor, float aerosolAnisotropyValue)
        {
            if (sky == null)
            {
                return;
            }

            sky.groundTint.Override(groundTintColor);
            sky.aerosolAnisotropy.Override(aerosolAnisotropyValue);
        }

        private void ApplyExposure(Exposure exposure, float fixedExposureValue)
        {
            if (exposure == null)
            {
                return;
            }

            exposure.mode.Override(ExposureMode.Fixed);
            exposure.fixedExposure.Override(fixedExposureValue);
        }

        private void ApplySun(float intensityLux, float colorTemperature, Color color)
        {
            if (directionalLight == null)
            {
                return;
            }

            directionalLight.intensity = intensityLux;
            directionalLight.colorTemperature = colorTemperature;
            directionalLight.color = color;
        }

        private void ApplyRain(float rainIntensity)
        {
            if (rainController != null)
            {
                rainController.Intensity = rainIntensity;
            }
        }
    }
}
