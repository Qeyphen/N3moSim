# Raw anemometer data from driver (before filtering)
# apparent wind angle (awa), degrees CCW - Robotics & Instrument convention (Note that marine convention is CW)
# signed, -180 to 180, 0 when coming in front of the boat (from bow to stern)
# positive = wind coming from Port side - left side
# awa is the ccw angle from vector "bow -> stern" to the wind "coming-from" vector
# + 45 deg for wind coming from front Port side (front left)
float32 angle_deg

# apparent wind speed, knots
float32 speed_kts
