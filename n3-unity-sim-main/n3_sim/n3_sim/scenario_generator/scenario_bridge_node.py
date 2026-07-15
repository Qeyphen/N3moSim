"""WebSocket bridge between the MCP scenario server (host) and the ROS scenario generator."""

from __future__ import annotations

import asyncio
import json
import math
import threading

import n3_common.ros as ros
import rclpy
from n3_common.topics.sim_topics import SIM_POSE
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

WS_PORT = 9877


class ScenarioBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("scenario_bridge_node", enable_logger_service=True)
        self.log = self.get_logger()

        # Latest boat pose (ENU)
        self.boat_x = 0.0
        self.boat_y = 0.0
        self.boat_heading_rad = 0.0
        self.has_pose = False

        # ROS service client for scenario commands
        self.srv_cb_group = ReentrantCallbackGroup()
        self.cmd_client = self.create_client(
            ros.ScenarioCommand, "/sim/scenario/command",
            callback_group=self.srv_cb_group,
        )

        # Subscribe to own boat pose
        self.create_subscription(
            ros.PoseStamped, SIM_POSE.name, self.on_pose, SIM_POSE.qos
        )

        # Connected WebSocket clients
        self.ws_clients: set = set()

        # Start WebSocket server in a background thread
        self.ws_thread = threading.Thread(target=self._run_ws_server, daemon=True)
        self.ws_thread.start()

        self.log.info(f"ScenarioBridgeNode ready — WS server on :{WS_PORT}")

    def on_pose(self, msg: ros.PoseStamped) -> None:
        self.boat_x = msg.pose.position.x
        self.boat_y = msg.pose.position.y
        q = msg.pose.orientation
        self.boat_heading_rad = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )
        self.has_pose = True

    # ------------------------------------------------------------------
    # WebSocket server (runs in background thread)
    # ------------------------------------------------------------------

    def _run_ws_server(self) -> None:
        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_until_complete(self._ws_serve())

    async def _ws_serve(self) -> None:
        try:
            import websockets  # noqa: F811
        except ImportError:
            self.log.error("websockets package not installed — bridge disabled")
            return

        async with websockets.serve(self._ws_handler, "0.0.0.0", WS_PORT):
            self.log.info(f"WebSocket server listening on 0.0.0.0:{WS_PORT}")
            await asyncio.Future()  # run forever

    async def _ws_handler(self, websocket) -> None:
        self.ws_clients.add(websocket)
        self.log.info("MCP client connected")
        try:
            # Send initial pose
            if self.has_pose:
                await websocket.send(self._pose_json())

            # Start pose streaming task
            pose_task = asyncio.create_task(self._stream_pose(websocket))

            async for raw_msg in websocket:
                await self._handle_ws_message(websocket, raw_msg)

            pose_task.cancel()
        except Exception as e:
            self.log.warn(f"WS client disconnected: {e}")
        finally:
            self.ws_clients.discard(websocket)

    async def _stream_pose(self, websocket) -> None:
        """Send boat pose updates at ~2 Hz."""
        while True:
            await asyncio.sleep(0.5)
            if self.has_pose:
                try:
                    await websocket.send(self._pose_json())
                except Exception:
                    break

    def _pose_json(self) -> str:
        return json.dumps(
            {
                "type": "pose",
                "x": round(self.boat_x, 3),
                "y": round(self.boat_y, 3),
                "heading_rad": round(self.boat_heading_rad, 4),
            }
        )

    async def _handle_ws_message(self, websocket, raw_msg: str) -> None:
        """Handle an incoming WS command from the MCP server."""
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            await websocket.send(
                json.dumps(
                    {
                        "type": "result",
                        "success": False,
                        "error": "Invalid JSON",
                    }
                )
            )
            return

        # Call the ROS service
        request = ros.ScenarioCommand.Request()
        request.json_request = raw_msg

        # Check service availability and call — both blocking, so run in executor
        # to avoid blocking the asyncio event loop (which kills the WS connection).
        loop = asyncio.get_event_loop()

        svc_ready = await loop.run_in_executor(
            None, self.cmd_client.wait_for_service, 2.0
        )
        if not svc_ready:
            await websocket.send(
                json.dumps(
                    {
                        "type": "result",
                        "success": False,
                        "error": "Scenario command service not available",
                    }
                )
            )
            return

        future = self.cmd_client.call_async(request)
        result = await loop.run_in_executor(
            None, self._wait_for_future, future
        )

        if result is None:
            await websocket.send(
                json.dumps(
                    {
                        "type": "result",
                        "success": False,
                        "error": "Service call failed",
                    }
                )
            )
            return

        await websocket.send(
            json.dumps(
                {
                    "type": "result",
                    "cmd": msg.get("cmd"),
                    "success": result.success,
                    "data": json.loads(result.json_response)
                    if result.json_response
                    else {},
                }
            )
        )

    def _wait_for_future(self, future) -> ros.ScenarioCommand.Response | None:
        """Block until rclpy future completes (called from executor thread).

        The node is already spinning in the main thread, so we just poll
        the future rather than calling spin_until_future_complete again.
        """
        import time

        deadline = time.monotonic() + 5.0
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.05)
        if future.done():
            return future.result()
        return None


def main() -> None:
    rclpy.init()
    node = ScenarioBridgeNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
