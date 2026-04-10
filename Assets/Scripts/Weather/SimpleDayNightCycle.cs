using UnityEngine;

namespace N3mo.Weather
{
    public class SimpleDayNightCycle : MonoBehaviour
    {
        [SerializeField] private Light directionalLight;
        [SerializeField] private Transform sunTransform;
        [SerializeField, Range(0f, 24f)] private float timeOfDay = 12f;
        [SerializeField] private bool animate = false;
        [SerializeField] private float dayLengthInMinutes = 8f;
        [SerializeField] private float sunriseHour = 6f;
        [SerializeField] private float sunsetHour = 18f;
        [SerializeField] private float nightIntensity = 0f;
        [SerializeField] private float dayIntensity = 120000f;

        public void Configure(Light lightSource, Transform lightTransform)
        {
            directionalLight = lightSource;
            sunTransform = lightTransform;
            ApplyTime();
        }

        public void SetTimeOfDay(float hour)
        {
            timeOfDay = Mathf.Repeat(hour, 24f);
            ApplyTime();
        }

        private void Reset()
        {
            directionalLight = FindFirstObjectByType<Light>();
            sunTransform = directionalLight != null ? directionalLight.transform : null;
        }

        private void Update()
        {
            if (animate)
            {
                var daySeconds = Mathf.Max(1f, dayLengthInMinutes * 60f);
                timeOfDay += (24f / daySeconds) * Time.deltaTime;
                if (timeOfDay >= 24f)
                {
                    timeOfDay -= 24f;
                }
            }

            ApplyTime();
        }

        private void OnValidate()
        {
            timeOfDay = Mathf.Repeat(timeOfDay, 24f);

            if (!Application.isPlaying)
            {
                ApplyTime();
            }
        }

        private void ApplyTime()
        {
            if (sunTransform != null)
            {
                var normalized = timeOfDay / 24f;
                var sunAngle = (normalized * 360f) - 90f;
                sunTransform.rotation = Quaternion.Euler(sunAngle, 30f, 0f);
            }

            if (directionalLight == null)
            {
                return;
            }

            var daylight = EvaluateDaylight(timeOfDay);
            directionalLight.intensity = Mathf.Lerp(nightIntensity, dayIntensity, daylight);
            directionalLight.colorTemperature = Mathf.Lerp(2200f, 6500f, daylight);
            directionalLight.enabled = directionalLight.intensity > 0.01f;
        }

        private float EvaluateDaylight(float hour)
        {
            if (hour <= sunriseHour || hour >= sunsetHour)
            {
                return 0f;
            }

            var daylightSpan = Mathf.Max(0.01f, sunsetHour - sunriseHour);
            var t = (hour - sunriseHour) / daylightSpan;
            return Mathf.Sin(t * Mathf.PI);
        }
    }
}
