using UnityEngine;

// Toggles a dynamic boat between Manual (keyboard) and Auto (ROS target-following)
// controllers. Mode is seeded from config but re-checked every frame, so it can be
// switched live in the Inspector during Play.
public class BoatControlSwitcher : MonoBehaviour
{
    [Tooltip("Active controller. Seeded from config; change at runtime to switch.")]
    public ControlMode mode = ControlMode.Manual;

    private string                  targetTopic;
    private ManualBoatController    manual;
    private AutonomousBoatController autonomous;
    private ControlMode?            applied;       // last-applied mode (null = none yet)

    // Called by SceneBuilder right after spawn to seed mode + topic.
    public void Configure(ControlMode initialMode, string targetTopic)
    {
        mode             = initialMode;
        this.targetTopic = targetTopic;
        if (autonomous != null) autonomous.Configure(targetTopic);
    }

    void Awake()
    {
        manual     = GetComponent<ManualBoatController>();
        autonomous = GetComponent<AutonomousBoatController>();
        if (autonomous == null)
            autonomous = gameObject.AddComponent<AutonomousBoatController>();

        autonomous.enabled = false;   // Apply() enables whichever the mode selects
    }

    void Update()
    {
        if (applied != mode) Apply();
    }

    void Apply()
    {
        bool auto = mode == ControlMode.Auto;

        if (manual != null)     manual.enabled     = !auto;
        if (autonomous != null) autonomous.enabled = auto;

        applied = mode;
        Debug.Log($"[BoatControlSwitcher] {name}: {(auto ? "AUTO" : "MANUAL")} control");
    }
}
