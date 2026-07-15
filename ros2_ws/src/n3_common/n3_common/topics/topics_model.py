from __future__ import annotations

from dataclasses import dataclass

from rclpy import qos

DEFAULT_DEAD_LINE_DURATION_SEC = 0.2  # 200ms
DEFAULT_LIFESPAN_DURATION_SEC = 0.3  # 300ms

# TODO-AFTER add topic type in TopicSpec and add n3_create_ros_pub(topic) and n3_create_ros_sub(topic, callback) methods. Change also n3mo_topics declaration with type inside


@dataclass(frozen=True, slots=True)
class TopicSpec:
    name: str
    qos: qos.QoSProfile


# use SAFETY for topics that should raise an action if not received for DEAD_LINE_DURATION: commands, joystick, keepalive/heartbeat
# deadline --> DDS raise a event_callback if duration since last message receive > DEAD_LINE_DURATION_SEC (check periodicity max of messages but not latency)
# life--> DDS trash the message if older than lifespan. The subscriber callback is just not fired (e.g., we don't want to receive a command too old. We prefer receive nothing) ( it checks latency)
# usage in a receiver node
# sub = node.create_subscription(
#     MsgType,
#     "topic",
#     callback,
#     qos,
#     event_callbacks=SubscriptionEventCallbacks(
#         deadline=lambda e: print("Deadline missed", e.total_count) # do failsafe behavior here.
#     )
# )
def safety_qos(
    dead_line_duration_sec: float = DEFAULT_DEAD_LINE_DURATION_SEC,
    lifespan_duration_sec: float = DEFAULT_LIFESPAN_DURATION_SEC,
) -> qos.QoSProfile:
    return qos.QoSProfile(
        depth=1,
        reliability=qos.QoSReliabilityPolicy.RELIABLE,
        history=qos.QoSHistoryPolicy.KEEP_LAST,
        durability=qos.QoSDurabilityPolicy.VOLATILE,
        deadline=qos.Duration(seconds=dead_line_duration_sec),
        lifespan=qos.Duration(seconds=lifespan_duration_sec),
    )


# for default safety qos
SAFETY_QOS = safety_qos()


# use RELIABLE for important but not critical data: commands, state, telemetry
# reliable means that DDS retry if the message not received
RELIABLE_QOS = qos.QoSProfile(
    depth=10,
    reliability=qos.QoSReliabilityPolicy.RELIABLE,
    history=qos.QoSHistoryPolicy.KEEP_LAST,
    durability=qos.QoSDurabilityPolicy.VOLATILE,
)

# use BEST_EFFORT for sensors, events, debug info
# best_effort means that DDS drop the message if not received
# you prefer receive the latest message than all of them with delay
BEST_EFFORT_QOS = qos.QoSProfile(
    depth=10,
    reliability=qos.QoSReliabilityPolicy.BEST_EFFORT,
    history=qos.QoSHistoryPolicy.KEEP_LAST,
    durability=qos.QoSDurabilityPolicy.VOLATILE,
)

# use LATCHED for latched topics: config, static info, mission plan, slow states sent only on change
# latched means that a new subscriber (e.g., a node recovering from a crash or a late starting node) will receive the latest message sent
LATCHED_QOS = qos.QoSProfile(
    depth=1,
    reliability=qos.QoSReliabilityPolicy.RELIABLE,
    history=qos.QoSHistoryPolicy.KEEP_LAST,
    durability=qos.QoSDurabilityPolicy.TRANSIENT_LOCAL,
)
