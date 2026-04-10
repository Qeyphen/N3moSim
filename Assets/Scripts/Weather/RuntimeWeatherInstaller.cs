using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace N3mo.Weather
{
    public static class RuntimeWeatherInstaller
    {
        public static void Install(SceneConfig config, GameObject followTargetCandidate = null)
        {
            var volume = Object.FindFirstObjectByType<Volume>();
            var sun = FindSunLight();

            if (volume == null || sun == null)
            {
                Debug.LogWarning("[RuntimeWeatherInstaller] Missing HDRP Volume or directional light. Weather bootstrap skipped.");
                return;
            }

            var runtimeRoot = new GameObject("RuntimeWeather");
            var runtimeProfile = BuildRuntimeProfile(volume);
            var weatherController = runtimeRoot.AddComponent<SimpleWeatherController>();
            var dayNightCycle = runtimeRoot.AddComponent<SimpleDayNightCycle>();
            var rainController = CreateRainSystem(runtimeRoot.transform, followTargetCandidate);

            volume.profile = runtimeProfile;
            weatherController.Configure(volume, sun, rainController);
            dayNightCycle.Configure(sun, sun.transform);

            ApplyEnvironmentConfig(config, weatherController, dayNightCycle);
        }

        private static VolumeProfile BuildRuntimeProfile(Volume volume)
        {
            var sourceProfile = volume.sharedProfile != null ? volume.sharedProfile : volume.profile;
            var runtimeProfile = sourceProfile != null
                ? Object.Instantiate(sourceProfile)
                : ScriptableObject.CreateInstance<VolumeProfile>();

            EnsureComponent<VisualEnvironment>(runtimeProfile);
            EnsureComponent<PhysicallyBasedSky>(runtimeProfile);
            EnsureComponent<Fog>(runtimeProfile);
            EnsureComponent<Exposure>(runtimeProfile);

            if (runtimeProfile.TryGet(out VisualEnvironment visualEnvironment))
            {
                visualEnvironment.skyType.Override(4);
                visualEnvironment.renderingSpace.Override(RenderingSpace.World);
                visualEnvironment.cloudType.Override(1);
            }

            if (runtimeProfile.TryGet(out PhysicallyBasedSky sky))
            {
                sky.groundTint.Override(new Color(0.12f, 0.10f, 0.09f, 1f));
                sky.aerosolAnisotropy.Override(0.8f);
            }

            if (runtimeProfile.TryGet(out Fog fog))
            {
                fog.enabled.Override(true);
                fog.enableVolumetricFog.Override(true);
                fog.maxFogDistance.Override(5000f);
                fog.meanFreePath.Override(400f);
                fog.baseHeight.Override(4f);
                fog.maximumHeight.Override(250f);
                fog.albedo.Override(new Color(0.78f, 0.91f, 1f, 1f));
                fog.depthExtent.Override(64f);
            }

            if (runtimeProfile.TryGet(out Exposure exposure))
            {
                exposure.mode.Override(ExposureMode.Fixed);
                exposure.fixedExposure.Override(14f);
            }

            return runtimeProfile;
        }

        private static void ApplyEnvironmentConfig(SceneConfig config, SimpleWeatherController weatherController, SimpleDayNightCycle dayNightCycle)
        {
            var timeOfDayValue = config?.environment?.time_of_day;
            weatherController.ApplyPresetByName(timeOfDayValue);

            var normalized = timeOfDayValue == null ? "day" : timeOfDayValue.Trim().ToLowerInvariant();
            switch (normalized)
            {
                case "night":
                    dayNightCycle.SetTimeOfDay(22f);
                    break;
                case "sunrise":
                    dayNightCycle.SetTimeOfDay(6.5f);
                    break;
                case "sunset":
                    dayNightCycle.SetTimeOfDay(18.5f);
                    break;
                case "storm":
                case "stormy":
                    dayNightCycle.SetTimeOfDay(15f);
                    break;
                default:
                    dayNightCycle.SetTimeOfDay(12f);
                    break;
            }
        }

        private static SimpleRainController CreateRainSystem(Transform parent, GameObject followTargetCandidate)
        {
            var rainObject = new GameObject("Rain");
            rainObject.transform.SetParent(parent, false);

            var particleSystem = rainObject.AddComponent<ParticleSystem>();
            var renderer = rainObject.GetComponent<ParticleSystemRenderer>();
            var rainController = rainObject.AddComponent<SimpleRainController>();

            ConfigureParticleSystem(particleSystem);
            ConfigureRenderer(renderer);

            var followTarget = followTargetCandidate != null
                ? followTargetCandidate.transform
                : FindBestFollowTarget();

            rainController.Configure(particleSystem, followTarget, new Vector3(0f, 20f, 0f));
            return rainController;
        }

        private static void ConfigureParticleSystem(ParticleSystem particleSystem)
        {
            var main = particleSystem.main;
            main.loop = true;
            main.playOnAwake = false;
            main.duration = 1f;
            main.startLifetime = 1.2f;
            main.startSpeed = 30f;
            main.startSize = 0.05f;
            main.maxParticles = 6000;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.scalingMode = ParticleSystemScalingMode.Shape;
            main.gravityModifier = 0.2f;

            var emission = particleSystem.emission;
            emission.enabled = true;
            emission.rateOverTime = 0f;

            var shape = particleSystem.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(45f, 1f, 45f);

            var velocityOverLifetime = particleSystem.velocityOverLifetime;
            velocityOverLifetime.enabled = true;
            velocityOverLifetime.space = ParticleSystemSimulationSpace.World;
            velocityOverLifetime.x = new ParticleSystem.MinMaxCurve(-1f);
            velocityOverLifetime.y = new ParticleSystem.MinMaxCurve(-35f);
            velocityOverLifetime.z = new ParticleSystem.MinMaxCurve(0f);

            var collision = particleSystem.collision;
            collision.enabled = false;

            var trails = particleSystem.trails;
            trails.enabled = false;
        }

        private static void ConfigureRenderer(ParticleSystemRenderer renderer)
        {
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.alignment = ParticleSystemRenderSpace.View;
            renderer.minParticleSize = 0.0001f;
            renderer.maxParticleSize = 0.02f;

            var shader = Shader.Find("HDRP/Unlit");
            if (shader == null)
            {
                shader = Shader.Find("Universal Render Pipeline/Particles/Unlit");
            }

            if (shader == null)
            {
                shader = Shader.Find("Particles/Standard Unlit");
            }

            if (shader == null)
            {
                return;
            }

            var material = new Material(shader)
            {
                name = "RuntimeRainMaterial"
            };

            if (material.HasColor("_BaseColor"))
            {
                material.SetColor("_BaseColor", new Color(0.8f, 0.9f, 1f, 0.35f));
            }

            if (material.HasFloat("_SurfaceType"))
            {
                material.SetFloat("_SurfaceType", 1f);
            }

            if (material.HasFloat("_BlendMode"))
            {
                material.SetFloat("_BlendMode", 0f);
            }

            renderer.sharedMaterial = material;
        }

        private static T EnsureComponent<T>(VolumeProfile profile) where T : VolumeComponent
        {
            if (!profile.TryGet(out T component))
            {
                component = profile.Add<T>(true);
            }

            return component;
        }

        private static Light FindSunLight()
        {
            var lights = Object.FindObjectsByType<Light>(FindObjectsSortMode.None);
            foreach (var light in lights)
            {
                if (light.type == LightType.Directional)
                {
                    return light;
                }
            }

            return null;
        }

        private static Transform FindBestFollowTarget()
        {
            var mainCamera = Camera.main;
            if (mainCamera != null)
            {
                return mainCamera.transform;
            }

            var sceneLoader = Object.FindFirstObjectByType<SceneLoader>();
            if (sceneLoader != null)
            {
                var sailboat = sceneLoader.GetSpawnedObject("sailboat_01");
                if (sailboat != null)
                {
                    return sailboat.transform;
                }

                var catamaran = sceneLoader.GetSpawnedObject("catamaran_01");
                if (catamaran != null)
                {
                    return catamaran.transform;
                }
            }

            return null;
        }
    }
}
