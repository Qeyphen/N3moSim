"""
bag_to_csv.py
=============
Converts a ROS2 bag session into CSV files + JPEG frames for ML.

Output per session:
  frames/000001.jpg   — camera frames extracted from bag
  poses.csv           — vessel positions over time
  commands.csv        — velocity commands
  gps.csv             — GPS track
  wind.csv            — wind data
  grid_stats.csv      — occupancy grid stats
  dataset.csv         — frames aligned with pose + command (ML ready)

Usage:
  python3 bag_to_csv.py /recordings/session_NAME
"""

import os
import sys
import csv

try:
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    import sqlite3
except ImportError as e:
    print(f'Missing dependency: {e}')
    sys.exit(1)


def read_bag(bag_path):
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

    cursor.execute('SELECT id, name, type FROM topics')
    topics = {row[0]: {'name': row[1], 'type': row[2]}
              for row in cursor.fetchall()}

    print('Topics:')
    for t in topics.values():
        print(f'  {t["name"]} ({t["type"]})')

    cursor.execute(
        'SELECT topic_id, timestamp, data FROM messages ORDER BY timestamp')
    messages = cursor.fetchall()
    conn.close()
    print(f'Total messages: {len(messages)}')
    return topics, messages


def find_closest(rows, target_ts):
    """Find row with timestamp closest to target_ts."""
    if not rows:
        return None
    return min(rows, key=lambda r: abs(float(r['timestamp']) - target_ts))


def export_session(bag_path, output_path):
    os.makedirs(output_path, exist_ok=True)
    frames_dir = os.path.join(output_path, 'frames')
    os.makedirs(frames_dir, exist_ok=True)

    topics, messages = read_bag(bag_path)
    id_to_name    = {k: v['name'] for k, v in topics.items()}
    topic_types   = {v['name']: v['type'] for v in topics.values()}

    files   = {}
    writers = {}

    def get_writer(name, headers):
        if name not in writers:
            path          = os.path.join(output_path, f'{name}.csv')
            files[name]   = open(path, 'w', newline='')
            writers[name] = csv.writer(files[name])
            writers[name].writerow(headers)
        return writers[name]

    # collect rows for alignment
    pose_rows    = []
    command_rows = []
    frame_rows   = []
    counts       = {}
    frame_idx    = 0

    for topic_id, timestamp_ns, data in messages:
        topic_name = id_to_name.get(topic_id, '')
        topic_type = topic_types.get(topic_name, '')
        ts         = timestamp_ns / 1e9

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
                row = {
                    'timestamp': f'{ts:.6f}',
                    'pos_x':     f'{pose.position.x:.4f}',
                    'pos_z':     f'{pose.position.z:.4f}',
                }
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
                if i == 0:
                    pose_rows.append({
                        'timestamp': ts,
                        'pos_x':     pose.position.x,
                        'pos_z':     pose.position.z,
                        'rot_y':     pose.orientation.y,
                        'rot_w':     pose.orientation.w,
                    })

        # cmd_vel → commands.csv
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
            command_rows.append({
                'timestamp': ts,
                'linear_x':  msg.linear.x,
                'angular_z': msg.angular.z,
            })

        # gps → gps.csv
        elif topic_name == '/sailboat/gps':
            w = get_writer('gps', [
                'timestamp', 'latitude', 'longitude', 'altitude'])
            w.writerow([
                f'{ts:.6f}',
                f'{msg.latitude:.8f}',
                f'{msg.longitude:.8f}',
                f'{msg.altitude:.4f}',
            ])

        # wind → wind.csv
        elif topic_name == '/environment/wind':
            w = get_writer('wind', [
                'timestamp', 'wind_x', 'wind_speed', 'wind_z'])
            w.writerow([
                f'{ts:.6f}',
                f'{msg.x:.4f}',
                f'{msg.y:.4f}',
                f'{msg.z:.4f}',
            ])

        # occupancy_grid → grid_stats.csv
        elif topic_name == '/occupancy_grid':
            occupied = sum(1 for v in msg.data if v == 100)
            total    = msg.info.width * msg.info.height
            w = get_writer('grid_stats', [
                'timestamp', 'width', 'height',
                'resolution', 'occupied_cells', 'free_cells'])
            w.writerow([
                f'{ts:.6f}',
                msg.info.width, msg.info.height,
                msg.info.resolution,
                occupied, total - occupied,
            ])

        # camera → frames/
        elif topic_name == '/camera/compressed':
            frame_idx += 1
            fname = f'{frame_idx:06d}.jpg'
            fpath = os.path.join(frames_dir, fname)
            with open(fpath, 'wb') as f:
                f.write(bytes(msg.data))
            frame_rows.append({
                'timestamp': ts,
                'frame_file': f'frames/{fname}',
            })

    # close CSV files
    for f in files.values():
        f.close()

    # build dataset.csv — align frame + pose + command by closest timestamp
    print(f'\nBuilding dataset.csv ({len(frame_rows)} frames)...')
    dataset_path = os.path.join(output_path, 'dataset.csv')
    with open(dataset_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow([
            'frame_file', 'timestamp',
            'pos_x', 'pos_z', 'rot_y', 'rot_w',
            'linear_x', 'angular_z'
        ])
        for frame in frame_rows:
            ts   = frame['timestamp']
            pose = find_closest(pose_rows, ts)
            cmd  = find_closest(command_rows, ts)

            w.writerow([
                frame['frame_file'],
                f'{ts:.6f}',
                f'{pose["pos_x"]:.4f}'    if pose else '',
                f'{pose["pos_z"]:.4f}'    if pose else '',
                f'{pose["rot_y"]:.6f}'    if pose else '',
                f'{pose["rot_w"]:.6f}'    if pose else '',
                f'{cmd["linear_x"]:.4f}'  if cmd  else '',
                f'{cmd["angular_z"]:.4f}' if cmd  else '',
            ])

    print('\nExport complete:')
    for topic, count in counts.items():
        print(f'  {topic}: {count} messages')
    print(f'  Frames extracted: {frame_idx}')
    print(f'\nOutput: {output_path}')
    print(f'  poses.csv, commands.csv, gps.csv, wind.csv, grid_stats.csv')
    print(f'  frames/ ({frame_idx} JPEGs)')
    print(f'  dataset.csv ({frame_idx} rows — ML ready)')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        bag_path = sys.argv[1]
        export_session(bag_path, bag_path)
    else:
        print('Usage: python3 bag_to_csv.py /recordings/session_NAME')
        sys.exit(1)
