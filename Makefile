# Easy commands to manage the simulation
#
# Usage:
#   make start          ← start all ROS2 services
#   make stop           ← stop all services
#   make logs           ← view all logs
#   make status         ← check service status
#   make sail-forward   ← move sailboat forward
#   make sail-stop      ← stop sailboat
#   make stop-all       ← stop all objects

# Docker Compose
start:
	docker compose up -d
	@echo "N3moSim ROS2 services started!"
	@echo "Now press Play in Unity"

stop:
	docker compose down
	@echo "N3moSim ROS2 services stopped!"

restart:
	docker compose down && docker compose up -d

logs:
	docker compose logs -f

logs-bridge:
	docker compose logs -f ros_bridge

logs-controller:
	docker compose logs -f n3mo_controller

logs-mission:
	docker compose logs -f mission_planner

status:
	docker compose ps

build:
	docker compose build

# Sailboat Commands
sail-forward:
	./send_command.sh sailboat_01 1.0 0.0

sail-reverse:
	./send_command.sh sailboat_01 -1.0 0.0

sail-left:
	./send_command.sh sailboat_01 0.5 -1.0

sail-right:
	./send_command.sh sailboat_01 0.5 1.0

sail-stop:
	./send_command.sh sailboat_01 0.0 0.0

# Catamaran Commands
cat1-forward:
	./send_command.sh catamaran_01 1.0 0.0

cat1-stop:
	./send_command.sh catamaran_01 0.0 0.0

cat2-forward:
	./send_command.sh catamaran_02 0.5 0.0

cat2-stop:
	./send_command.sh catamaran_02 0.0 0.0

# Buoy Commands
buoy-move:
	./send_command.sh buoy_03 0.3 0.0

buoy-stop:
	./send_command.sh buoy_03 0.0 0.0

# Stop Everything
stop-all:
	./send_command.sh all stop

# ROS2 Topic Tools
list-topics:
	docker exec n3mo_bridge bash -c \
		"source /opt/ros/humble/setup.bash && ros2 topic list"

echo-sailboat:
	docker exec n3mo_bridge bash -c \
		"source /opt/ros/humble/setup.bash && \
		ros2 topic echo /sailboat_01/cmd_vel"

echo-gps:
	docker exec n3mo_bridge bash -c \
		"source /opt/ros/humble/setup.bash && \
		ros2 topic echo /sailboat/gps"

.PHONY: start stop restart logs status build \
        sail-forward sail-reverse sail-left sail-right sail-stop \
        cat1-forward cat1-stop cat2-forward cat2-stop \
        buoy-move buoy-stop stop-all \
        list-topics echo-sailboat echo-gps