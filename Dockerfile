FROM ros:humble

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    git \
    curl \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

WORKDIR /root/ros2_ws

RUN mkdir -p /root/ros2_ws/src && \
    cd /root/ros2_ws/src && \
    git clone -b main-ros2 \
      https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git && \
    echo "ROS TCP Endpoint cloned!"

COPY ros2_ws/src/n3mo_control /root/ros2_ws/src/n3mo_control

RUN . /opt/ros/humble/setup.sh && \
    cd /root/ros2_ws && \
    colcon build && \
    echo "All packages built!"

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /root/ros2_ws/install/setup.bash" >> /root/.bashrc && \
    echo "export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH" >> /root/.bashrc && \
    echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> /root/.bashrc

WORKDIR /root/ros2_ws