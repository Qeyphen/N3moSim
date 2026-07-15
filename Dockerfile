FROM ros:humble

RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    python3-pip \
    git \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-geographic-msgs \
    ros-humble-visualization-msgs \
    && rm -rf /var/lib/apt/lists/*

# Python deps for the n3_sim scenario generator (n3_common params + YAML scenarios).
RUN pip3 install --no-cache-dir pydantic pyyaml

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

WORKDIR /root/ros2_ws

RUN mkdir -p /root/ros2_ws/src && \
    cd /root/ros2_ws/src && \
    git clone -b main-ros2 \
      https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git && \
    echo "ROS TCP Endpoint cloned!"

COPY ros2_ws/src/n3mo_control /root/ros2_ws/src/n3mo_control

# Vendored n3-unity-sim packages for the scenario generator.
COPY ros2_ws/src/n3_new_msgs /root/ros2_ws/src/n3_new_msgs
COPY ros2_ws/src/n3_common   /root/ros2_ws/src/n3_common
COPY ros2_ws/src/n3_sim      /root/ros2_ws/src/n3_sim

RUN . /opt/ros/humble/setup.sh && \
    cd /root/ros2_ws && \
    colcon build && \
    echo "All packages built!"

RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /root/ros2_ws/install/setup.bash" >> /root/.bashrc && \
    echo "export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH" >> /root/.bashrc && \
    echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> /root/.bashrc

RUN sed -i 's/else self.parse_message_name(node.msg)/else (self.parse_message_name(node.msg) if (node is not None and node.msg is not None) else "")/g' \
    /root/ros2_ws/install/ros_tcp_endpoint/lib/python3.10/site-packages/ros_tcp_endpoint/tcp_sender.py

# The endpoint accepts `latch` but ignores it ("# TODO: surface latch functionality"),
# so latched publishers (e.g. /map) come out VOLATILE and late subscribers miss them.
# Make latch=True create a TRANSIENT_LOCAL publisher.
RUN python3 -c "p='/root/ros2_ws/install/ros_tcp_endpoint/lib/python3.10/site-packages/ros_tcp_endpoint/publisher.py'; s=open(p).read(); old='        self.pub = self.create_publisher(message_class, topic, queue_size)'; new='        if latch:\n            from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSHistoryPolicy\n            qos = QoSProfile(depth=queue_size, history=QoSHistoryPolicy.KEEP_LAST, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)\n            self.pub = self.create_publisher(message_class, topic, qos)\n        else:\n            self.pub = self.create_publisher(message_class, topic, queue_size)'; open(p,'w').write(s if 'TRANSIENT_LOCAL' in s else s.replace(old,new,1))"

WORKDIR /root/ros2_ws