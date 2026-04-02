# ─────────────────────────────────────────────────────────────────────────────
# N3moSim ROS2 Docker Image
# Base: ROS2 Humble
# Includes: ROS TCP Endpoint + n3mo_control package
# ─────────────────────────────────────────────────────────────────────────────

FROM ros:humble

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Create ROS2 workspace ─────────────────────────────────────────────────────
WORKDIR /root/ros2_ws

# ── Clone ROS TCP Endpoint ────────────────────────────────────────────────────
RUN mkdir -p /root/ros2_ws/src && \
    cd /root/ros2_ws/src && \
    git clone -b main-ros2 \
      https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git && \
    echo "ROS TCP Endpoint cloned!"

# ── Copy n3mo_control package ─────────────────────────────────────────────────
COPY ros2_ws/src/n3mo_control /root/ros2_ws/src/n3mo_control

# ── Build ALL packages together in one step ───────────────────────────────────
# This ensures all packages are in the same AMENT_PREFIX_PATH
RUN . /opt/ros/humble/setup.sh && \
    cd /root/ros2_ws && \
    colcon build && \
    echo "All packages built successfully!"

# ── Source everything permanently in bashrc ───────────────────────────────────
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /root/ros2_ws/install/setup.bash" >> /root/.bashrc && \
    echo "export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH" >> /root/.bashrc

# ── Set entrypoint to source everything before any command ────────────────────
RUN echo '#!/bin/bash' > /ros_entrypoint.sh && \
    echo 'source /opt/ros/humble/setup.bash' >> /ros_entrypoint.sh && \
    echo 'source /root/ros2_ws/install/setup.bash' >> /ros_entrypoint.sh && \
    echo 'export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:$AMENT_PREFIX_PATH' >> /ros_entrypoint.sh && \
    echo 'exec "$@"' >> /ros_entrypoint.sh && \
    chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]

# ── Set default working directory ────────────────────────────────────────────
WORKDIR /root/ros2_ws