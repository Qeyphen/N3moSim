"""
config_loader.py
================
Shared utility for loading scene_config.json.
Used by all N3moSim ROS2 nodes.

Search order:
1. /n3mosim/config/scene_config.json
2. ROS2 package share directory
3. Relative path fallback
"""

import json
import os


def load_config(logger=None):
    """
    Load scene_config.json from known locations.
    Returns parsed config dict or None if not found.
    """

    search_paths = [
        # 1. Mounted from N3moSim root (docker volume)
        '/n3mosim/config/scene_config.json',

        # 2. ROS2 package share directory
        '/root/ros2_ws/install/n3mo_control/share/n3mo_control/config/scene_config.json',

        # 3. Local package config folder
        os.path.join(os.path.dirname(__file__),
                     '..', 'config', 'scene_config.json'),
    ]

    for path in search_paths:
        path = os.path.normpath(path)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                if logger:
                    logger.info(f'Config loaded from: {path}')
                return config
            except json.JSONDecodeError as e:
                if logger:
                    logger.error(f'Config JSON error in {path}: {e}')
                return None

    if logger:
        logger.error(
            f'Config not found! Searched:\n' +
            '\n'.join(f'  - {p}' for p in search_paths)
        )
    return None