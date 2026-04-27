# /tmp/test_grid.py
import numpy as np
import json

with open('/n3mosim/config/scene_config.json') as f:
    config = json.load(f)

resolution = 1.0
width_m    = 500.0
height_m   = 500.0
origin_x   = -250.0
origin_y   = -250.0
cols = int(width_m  / resolution)
rows = int(height_m / resolution)
data = np.zeros(rows * cols, dtype=np.int8)

RADIUS = {'sailboat': 3, 'catamaran': 4, 'buoy': 2}

for obj in config['objects']:
    if obj.get('dynamic', False):
        continue
    pos   = obj['position']
    otype = obj['type'].lower()
    cx = int((pos[0] - origin_x) / resolution)
    cy = int((pos[2] - origin_y) / resolution)
    r  = RADIUS.get(otype, 2)
    print(obj['id'], 'world', pos[0], pos[2], 'cell', cx, cy, 'radius', r)
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            if dx*dx + dy*dy <= r*r:
                nx, ny = cx+dx, cy+dy
                if 0 <= nx < cols and 0 <= ny < rows:
                    data[ny*cols+nx] = 100

occupied = int(np.sum(data == 100))
print('Total occupied cells:', occupied)