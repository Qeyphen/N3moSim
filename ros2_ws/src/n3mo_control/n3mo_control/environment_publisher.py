"""
environment_publisher.py
========================
Publishes environment state updates to Unity in real time.

Modes:
  manual   — publish once with given parameters
  cycle    — cycle through time of day automatically
  storm    — gradually build up wind and waves + apply Stormy preset
  calm     — gradually reduce wind and waves + apply Clear preset
  preset   — apply a named weather preset instantly

Preset encoding in data[4]:
  0.0  = gradual (no snap)
  1.0  = instant snap
  10.0 = preset Clear
  11.0 = preset Misty
  12.0 = preset Rainy
  13.0 = preset Stormy

Publishes:
  /environment/update  → EnvironmentController.cs in Unity

Usage:
  # manual wind/wave settings
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual \
    -p wind_speed:=15.0 \
    -p wind_direction:=45.0 \
    -p wave_height:=2.0 \
    -p time_of_day:=14.0 \
    -p instant:=true

  # apply a preset instantly
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=preset \
    -p preset_name:=stormy

  # build up a storm over 60 seconds
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=storm

  # cycle through time of day
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=cycle \
    -p cycle_speed:=1.0
"""

import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray


# preset codes — add 10 to encode in data[4]
PRESET_CLEAR  = 10.0
PRESET_MISTY  = 11.0
PRESET_RAINY  = 12.0
PRESET_STORMY = 13.0

PRESET_MAP = {
    'clear':   PRESET_CLEAR,
    'misty':   PRESET_MISTY,
    'fog':     PRESET_MISTY,
    'foggy':   PRESET_MISTY,
    'rainy':   PRESET_RAINY,
    'rain':    PRESET_RAINY,
    'stormy':  PRESET_STORMY,
    'storm':   PRESET_STORMY,
}


class EnvironmentPublisher(Node):
    def __init__(self):
        super().__init__('environment_publisher')

        # ── parameters ────────────────────────────────────────
        self.declare_parameter('mode',           'manual')
        self.declare_parameter('wind_speed',     5.0)
        self.declare_parameter('wind_direction', 0.0)
        self.declare_parameter('wave_height',    0.5)
        self.declare_parameter('time_of_day',    12.0)
        self.declare_parameter('instant',        False)
        self.declare_parameter('cycle_speed',    1.0)
        self.declare_parameter('publish_hz',     10.0)
        self.declare_parameter('preset_name',    'clear')

        self.mode           = self.get_parameter('mode').value
        self.wind_speed     = float(self.get_parameter('wind_speed').value)
        self.wind_direction = float(self.get_parameter('wind_direction').value)
        self.wave_height    = float(self.get_parameter('wave_height').value)
        self.time_of_day    = float(self.get_parameter('time_of_day').value)
        self.instant        = bool(self.get_parameter('instant').value)
        self.cycle_speed    = float(self.get_parameter('cycle_speed').value)
        self.publish_hz     = float(self.get_parameter('publish_hz').value)
        self.preset_name    = self.get_parameter('preset_name').value.lower()

        # internal state
        self.elapsed        = 0.0
        self.storm_progress = 0.0
        self.preset_sent    = False

        self.pub = self.create_publisher(
            Float32MultiArray, '/environment/update', 10)

        dt = 1.0 / max(self.publish_hz, 0.1)
        self.create_timer(dt, self._publish)

        self.get_logger().info(
            f'EnvironmentPublisher ready\n'
            f'  mode          : {self.mode}\n'
            f'  wind_speed    : {self.wind_speed}\n'
            f'  wind_direction: {self.wind_direction}\n'
            f'  wave_height   : {self.wave_height}\n'
            f'  time_of_day   : {self.time_of_day}\n'
            f'  instant       : {self.instant}\n'
            f'  publish_hz    : {self.publish_hz}'
        )
        if self.mode == 'preset':
            self.get_logger().info(
                f'  preset_name   : {self.preset_name}'
            )

    # ── main publish loop ─────────────────────────────────────────────────────
    def _publish(self):
        dt = 1.0 / max(self.publish_hz, 0.1)
        self.elapsed += dt

        if self.mode == 'manual':
            self._publish_values(
                self.wind_speed,
                self.wind_direction,
                self.wave_height,
                self.time_of_day,
                1.0 if self.instant else 0.0
            )

        elif self.mode == 'preset':
            # send preset code once, then keep sending gradual updates
            preset_val = PRESET_MAP.get(self.preset_name, PRESET_CLEAR)
            if not self.preset_sent:
                self._publish_values(
                    self.wind_speed,
                    self.wind_direction,
                    self.wave_height,
                    self.time_of_day,
                    preset_val
                )
                self.preset_sent = True
                self.get_logger().info(
                    f'Preset sent: {self.preset_name} (code={preset_val})'
                )
            else:
                # keep publishing current values without preset trigger
                self._publish_values(
                    self.wind_speed,
                    self.wind_direction,
                    self.wave_height,
                    self.time_of_day,
                    0.0
                )

        elif self.mode == 'cycle':
            # advance time of day continuously
            self.time_of_day += dt * self.cycle_speed
            if self.time_of_day >= 24.0:
                self.time_of_day -= 24.0

            wind  = 3.0 + 4.0 * math.sin(self.elapsed * 0.1)
            waves = 0.3 + 0.3 * math.sin(self.elapsed * 0.07)

            self._publish_values(
                wind, self.wind_direction, waves,
                self.time_of_day, 0.0)

            if int(self.elapsed) % 10 == 0:
                self.get_logger().info(
                    f'Cycle | time={self.time_of_day:.1f}h '
                    f'wind={wind:.1f}m/s waves={waves:.2f}m'
                )

        elif self.mode == 'storm':
            # gradually build up over 60 seconds
            self.storm_progress = min(self.elapsed / 60.0, 1.0)

            wind   = 5.0  + 25.0 * self.storm_progress
            waves  = 0.5  + 4.5  * self.storm_progress
            wind_d = (self.wind_direction + 90.0 * self.storm_progress) % 360.0

            # trigger Stormy preset at 30% progress
            if self.storm_progress >= 0.3 and not self.preset_sent:
                self.preset_sent = True
                self._publish_values(wind, wind_d, waves,
                                     self.time_of_day, PRESET_STORMY)
                self.get_logger().info('Storm reached 30% — applying Stormy preset')
                return

            self._publish_values(wind, wind_d, waves, self.time_of_day, 0.0)

            if int(self.elapsed) % 5 == 0:
                self.get_logger().info(
                    f'Storm {self.storm_progress*100:.0f}% | '
                    f'wind={wind:.1f}m/s waves={waves:.2f}m'
                )

        elif self.mode == 'calm':
            # gradually reduce over 30 seconds
            progress = min(self.elapsed / 30.0, 1.0)
            wind     = self.wind_speed  * (1.0 - progress)
            waves    = self.wave_height * (1.0 - progress)

            # trigger Clear preset at 50% progress
            if progress >= 0.5 and not self.preset_sent:
                self.preset_sent = True
                self._publish_values(wind, self.wind_direction, waves,
                                     self.time_of_day, PRESET_CLEAR)
                self.get_logger().info('Calm reached 50% — applying Clear preset')
                return

            self._publish_values(wind, self.wind_direction, waves,
                                 self.time_of_day, 0.0)

            if int(self.elapsed) % 5 == 0:
                self.get_logger().info(
                    f'Calm {progress*100:.0f}% | '
                    f'wind={wind:.1f}m/s waves={waves:.2f}m'
                )

    def _publish_values(self, wind_speed, wind_direction,
                        wave_height, time_of_day, flag):
        msg      = Float32MultiArray()
        msg.data = [
            float(wind_speed),
            float(wind_direction),
            float(wave_height),
            float(time_of_day),
            float(flag)
        ]
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = EnvironmentPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()