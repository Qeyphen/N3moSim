#!/usr/bin/env python3
"""Set Unity environment conditions over ROS 2; publishes only the params passed (latched), then exits.

Usage: ros2 run n3mo_control env_control --ros-args -p time:=18.0 -p fog:=0.7
"""

import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from std_msgs.msg import Float32, Int32, String

# param name -> (topic, ros msg type)
FLOATS = {
    "time":       ("/env/time_of_day", Float32),
    "fog":        ("/env/fog",         Float32),
    "wind":       ("/env/wind",        Float32),
    "wave":       ("/env/wave",        Float32),
    "cloudiness": ("/env/cloudiness",  Float32),
    "rain":       ("/env/rain",        Float32),
}
NAN = float("nan")


class EnvControl(Node):
    def __init__(self):
        super().__init__("env_control")
        qos = QoSProfile(
            depth=1,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
        )

        self.declare_parameter("weather", "")
        self.declare_parameter("randomize", -1)    # >=0 sends a seed (0 = random)
        for name in FLOATS:
            self.declare_parameter(name, NAN)      # NaN = "not set"

        sent = []
        for name, (topic, msg_t) in FLOATS.items():
            val = float(self.get_parameter(name).value)
            if val == val:   # not NaN
                self.create_publisher(msg_t, topic, qos).publish(msg_t(data=val))
                sent.append(f"{name}={val}")

        weather = self.get_parameter("weather").value
        if weather:
            self.create_publisher(String, "/env/weather", qos).publish(String(data=weather))
            sent.append(f"weather={weather}")

        seed = int(self.get_parameter("randomize").value)
        if seed >= 0:
            self.create_publisher(Int32, "/env/randomize", qos).publish(Int32(data=seed))
            sent.append(f"randomize={seed}")

        if sent:
            self.get_logger().info("env_control sent: " + ", ".join(sent))
        else:
            self.get_logger().warn(
                "nothing to send. Pass e.g. -p time:=18.0 -p fog:=0.7 -p weather:=stormy"
            )
        time.sleep(0.5)   # let latched samples flush before exit


def main():
    rclpy.init()
    node = EnvControl()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
