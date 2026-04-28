"""
bag_to_csv.py
=============
Converts a recorded ROS2 bag session into CSV files for ML/analysis.

Produces per session:
  poses.csv          — vessel positions over time
  commands.csv       — velocity commands sent to each vessel
  gps.csv            — GPS track
  wind.csv           — wind data over time
  grid_stats.csv     — occupancy grid stats over time (occupied cell count)

Usage:
  ros2 run n3mo_control bag_to_csv --ros-args -p session:=session_2025_04_28_153000
  
  Or directly:
  python3 bag_to_csv.py /recordings/session_2025_04_28_153000
"""

import os
import sys
import csv
import argparse
import struct

try:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    import sqlite3
except ImportError as e:
    print(f'Missing dependency: {e}')
    sys.exit(1)


def read_bag(bag_path):
    """Read all messages from a ROS2 sqlite3 bag file."""
    db_path = None
    for f in os.listdir(bag_path):
        if f.endswith('.db3'):
            db_path = os.path.join(bag_path, f)
            break

    if not db_path:
        print(f'No .db3 file found in {bag_path}')
        sys.exit(1)

    print(f'Reading bag: {db_path}')
    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # get topic name → type mapping
    cursor.execute('SELECT id, name, type FROM topics')
    topics = {row[0]: {'name': row[1], 'type': row[2]}
              for row in cursor.fetchall()}

    print(f'Topics found:')
    for t in topics.values():
        print(f'  {t["name"]} ({t["type"]})')

    # get all messages
    cursor.execute(
        'SELECT topic_id, timestamp, data FROM messages ORDER BY timestamp')
    messages = cursor.fetchall()
    conn.close()

    print(f'Total messages: {len(messages)}')
    return topics, messages


def export_session(bag_path, output_path):
    """Export a bag session to CSV files."""
    os.makedirs(output_path, exist_ok=True)
    topics, messages = read_bag(bag_path)

    # reverse lookup: topic name → type string
    topic_types = {v['name']: v['type'] for v in topics.values()}
    topic_ids   = {v['id'] if 'id' in v else k: v['name']
                   for k, v in topics.items()}

    # rebuild id → name map
    id_to_name = {k: v['name'] for k, v in topics.items()}

    # CSV writers
    files   = {}
    writers = {}

    def get_writer(name, headers):
        if name not in writers:
            path       = os.path.join(output_path, f'{name}.csv')
            files[name] = open(path, 'w', newline='')
            writers[name] = csv.writer(files[name])
            writers[name].writerow(headers)
        return writers[name]

    counts = {}

    for topic_id, timestamp_ns, data in messages:
        topic_name = id_to_name.get(topic_id, '')
        topic_type = topic_types.get(topic_name, '')
        ts         = timestamp_ns / 1e9  # convert to seconds

        counts[topic_name] = counts.get(topic_name, 0) + 1

        try:
            msg_type = get_message(topic_type)
            msg      = deserialize_message(data, msg_type)
        except Exception:
            continue

        # /unity/all_poses → poses.csv
        if topic_name == '/unity/all_poses':
            w = get_writer('poses', [
                'timestamp', 'pose_index',
                'pos_x', 'pos_y', 'pos_z',
                'rot_x', 'rot_y', 'rot_z', 'rot_w'
            ])
            for i, pose in enumerate(msg.poses):
                w.writerow([
                    f'{ts:.6f}', i,
                    f'{pose.position.x:.4f}',
                    f'{pose.position.y:.4f}',
                    f'{pose.position.z:.4f}',
                    f'{pose.orientation.x:.6f}',
                    f'{pose.orientation.y:.6f}',
                    f'{pose.orientation.z:.6f}',
                    f'{pose.orientation.w:.6f}',
                ])

        # /sailboat_01/cmd_vel or /sailboat_01/pose → commands.csv
        elif 'cmd_vel' in topic_name:
            vessel_id = topic_name.split('/')[1]
            w = get_writer('commands', [
                'timestamp', 'vessel_id',
                'linear_x', 'linear_y', 'linear_z',
                'angular_x', 'angular_y', 'angular_z'
            ])
            w.writerow([
                f'{ts:.6f}', vessel_id,
                f'{msg.linear.x:.4f}',
                f'{msg.linear.y:.4f}',
                f'{msg.linear.z:.4f}',
                f'{msg.angular.x:.4f}',
                f'{msg.angular.y:.4f}',
                f'{msg.angular.z:.4f}',
            ])

        # /sailboat/gps → gps.csv
        elif topic_name == '/sailboat/gps':
            w = get_writer('gps', [
                'timestamp', 'latitude', 'longitude', 'altitude'
            ])
            w.writerow([
                f'{ts:.6f}',
                f'{msg.latitude:.8f}',
                f'{msg.longitude:.8f}',
                f'{msg.altitude:.4f}',
            ])

        # /environment/wind → wind.csv
        elif topic_name == '/environment/wind':
            w = get_writer('wind', [
                'timestamp', 'wind_x', 'wind_speed', 'wind_z'
            ])
            w.writerow([
                f'{ts:.6f}',
                f'{msg.x:.4f}',
                f'{msg.y:.4f}',
                f'{msg.z:.4f}',
            ])

        # /occupancy_grid → grid_stats.csv
        elif topic_name == '/occupancy_grid':
            occupied = sum(1 for v in msg.data if v == 100)
            w = get_writer('grid_stats', [
                'timestamp', 'width', 'height',
                'resolution', 'occupied_cells', 'free_cells'
            ])
            total = msg.info.width * msg.info.height
            w.writerow([
                f'{ts:.6f}',
                msg.info.width,
                msg.info.height,
                msg.info.resolution,
                occupied,
                total - occupied,
            ])

    # close all files
    for f in files.values():
        f.close()

    print('\nExport complete:')
    for topic, count in counts.items():
        print(f'  {topic}: {count} messages')
    print(f'\nCSV files written to: {output_path}')


def main():
    import rclpy
    rclpy.init()

    node = rclpy.create_node('bag_to_csv')
    node.declare_parameter('session', '')
    session = node.get_parameter('session').value
    node.destroy_node()
    rclpy.shutdown()

    if not session:
        print('Usage: ros2 run n3mo_control bag_to_csv --ros-args -p session:=session_NAME')
        sys.exit(1)

    bag_path    = f'/recordings/{session}'
    output_path = f'/recordings/{session}'

    if not os.path.exists(bag_path):
        print(f'Session not found: {bag_path}')
        sys.exit(1)

    export_session(bag_path, output_path)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        bag_path = sys.argv[1]
        export_session(bag_path, bag_path)
    else:
        main()
