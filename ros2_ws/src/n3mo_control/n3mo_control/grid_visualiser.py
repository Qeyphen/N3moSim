"""
grid_visualiser.py
==================
Web-based occupancy grid visualiser.
Opens in browser at http://localhost:8080
Shows live map with buoys and vessels updating in real time.
"""

import threading
import json
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from flask import Flask, Response, render_template_string

app = Flask(__name__)

# shared state between ROS thread and Flask thread
latest_grid = {
    'width':      0,
    'height':     0,
    'resolution': 1.0,
    'origin_x':   0.0,
    'origin_y':   0.0,
    'occupied':   [],   # list of (cx, cy) occupied cells
    'total':      0,
    'count':      0,
}
grid_lock = threading.Lock()

HTML = '''
<!DOCTYPE html>
<html>
<head>
  <title>N3moSim Occupancy Grid</title>
  <style>
    body { background: #1a1a2e; color: #eee; font-family: monospace;
           margin: 0; padding: 20px; }
    h1   { color: #00d4ff; margin-bottom: 4px; }
    #info { font-size: 13px; color: #aaa; margin-bottom: 12px; }
    canvas { border: 1px solid #333; display: block; }
    #stats { margin-top: 10px; font-size: 13px; color: #aaa; }
  </style>
</head>
<body>
  <h1>N3moSim — Occupancy Grid</h1>
  <div id="info">Live map · updates every second · 
    <span id="hz">waiting...</span></div>
  <canvas id="grid" width="600" height="600"></canvas>
  <div id="stats">Waiting for grid data...</div>

<script>
const canvas  = document.getElementById('grid');
const ctx     = canvas.getContext('2d');
const stats   = document.getElementById('stats');
const hzEl    = document.getElementById('hz');
let lastUpdate = 0;

async function fetchGrid() {
  try {
    const r    = await fetch('/grid_data');
    const data = await r.json();
    if (!data.width) return;

    const now = Date.now();
    const hz  = lastUpdate ? (1000 / (now - lastUpdate)).toFixed(1) : '...';
    lastUpdate = now;
    hzEl.textContent = hz + ' Hz';

    const W = canvas.width;
    const H = canvas.height;
    const cw = W / data.width;
    const ch = H / data.height;

    // clear
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, W, H);

    // draw grid lines (sparse)
    ctx.strokeStyle = '#1e2a3a';
    ctx.lineWidth = 0.5;
    const step = Math.floor(data.width / 10);
    for (let x = 0; x < data.width; x += step) {
      ctx.beginPath();
      ctx.moveTo(x * cw, 0);
      ctx.lineTo(x * cw, H);
      ctx.stroke();
    }
    for (let y = 0; y < data.height; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y * ch);
      ctx.lineTo(W, y * ch);
      ctx.stroke();
    }

    // draw origin crosshair
    const ox = (-data.origin_x / data.resolution) * cw;
    const oy = (-data.origin_y / data.resolution) * ch;
    ctx.strokeStyle = '#2a4a6a';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(ox, 0); ctx.lineTo(ox, H); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, oy); ctx.lineTo(W, oy); ctx.stroke();

    // draw occupied cells
    data.occupied.forEach(([cx, cy]) => {
      const px = cx * cw;
      const py = (data.height - cy - 1) * ch; // flip Y
      ctx.fillStyle = '#00d4ff';
      ctx.fillRect(px, py, Math.max(cw, 2), Math.max(ch, 2));
    });

    // draw world origin label
    ctx.fillStyle = '#555';
    ctx.font = '10px monospace';
    ctx.fillText('(0,0)', ox + 3, oy - 3);

    stats.innerHTML =
      'Map: ' + data.width + 'x' + data.height +
      ' cells &nbsp;|&nbsp; Resolution: ' + data.resolution + 'm/cell' +
      ' &nbsp;|&nbsp; <span style="color:#00d4ff">Occupied: ' +
      data.count + '</span> &nbsp;|&nbsp; Free: ' +
      (data.total - data.count);
  } catch(e) {
    stats.textContent = 'Waiting for data...';
  }
}

setInterval(fetchGrid, 500);
fetchGrid();
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/grid_data')
def grid_data():
    with grid_lock:
        return Response(
            json.dumps(latest_grid),
            mimetype='application/json'
        )


class GridVisNode(Node):
    def __init__(self):
        super().__init__('grid_visualiser')
        self.create_subscription(
            OccupancyGrid, '/occupancy_grid', self.on_grid, 10)
        self.get_logger().info(
            'GridVisualiser ready — open http://localhost:8080')

    def on_grid(self, msg):
        w = msg.info.width
        h = msg.info.height
        occupied = [
            (i % w, i // w)
            for i, v in enumerate(msg.data) if v == 100
        ]
        with grid_lock:
            latest_grid['width']      = w
            latest_grid['height']     = h
            latest_grid['resolution'] = msg.info.resolution
            latest_grid['origin_x']   = msg.info.origin.position.x
            latest_grid['origin_y']   = msg.info.origin.position.y
            latest_grid['occupied']   = occupied
            latest_grid['total']      = w * h
            latest_grid['count']      = len(occupied)


def ros_thread():
    rclpy.init()
    node = GridVisNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    t = threading.Thread(target=ros_thread, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=8080, debug=False)
