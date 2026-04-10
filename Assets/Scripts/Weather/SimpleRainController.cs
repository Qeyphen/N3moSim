using UnityEngine;

namespace N3mo.Weather
{
    public class SimpleRainController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private ParticleSystem rainParticleSystem;
        [SerializeField] private Transform followTarget;
        [SerializeField] private Vector3 worldOffset = new Vector3(0f, 20f, 0f);

        [Header("Rain")]
        [SerializeField, Range(0f, 1f)] private float intensity = 0f;
        [SerializeField] private float maxEmissionRate = 1500f;
        [SerializeField] private float minStartSpeed = 20f;
        [SerializeField] private float maxStartSpeed = 45f;
        [SerializeField] private float minStartSize = 0.03f;
        [SerializeField] private float maxStartSize = 0.08f;

        public float Intensity
        {
            get => intensity;
            set
            {
                intensity = Mathf.Clamp01(value);
                ApplyRainSettings();
            }
        }

        public void Configure(ParticleSystem particleSystem, Transform target, Vector3 offset)
        {
            rainParticleSystem = particleSystem;
            followTarget = target;
            worldOffset = offset;
            ApplyRainSettings();
        }

        private void Reset()
        {
            rainParticleSystem = GetComponentInChildren<ParticleSystem>();
        }

        private void OnEnable()
        {
            ApplyRainSettings();
        }

        private void LateUpdate()
        {
            if (followTarget != null)
            {
                transform.position = followTarget.position + worldOffset;
            }
        }

        private void OnValidate()
        {
            intensity = Mathf.Clamp01(intensity);

            if (!Application.isPlaying)
            {
                ApplyRainSettings();
            }
        }

        private void ApplyRainSettings()
        {
            if (rainParticleSystem == null)
            {
                return;
            }

            var emission = rainParticleSystem.emission;
            emission.rateOverTime = intensity * maxEmissionRate;

            var main = rainParticleSystem.main;
            main.startSpeed = Mathf.Lerp(minStartSpeed, maxStartSpeed, intensity);
            main.startSize = Mathf.Lerp(minStartSize, maxStartSize, intensity);

            if (intensity > 0.001f)
            {
                if (!rainParticleSystem.isPlaying)
                {
                    rainParticleSystem.Play();
                }
            }
            else if (rainParticleSystem.isPlaying)
            {
                rainParticleSystem.Stop();
            }
        }
    }
}
