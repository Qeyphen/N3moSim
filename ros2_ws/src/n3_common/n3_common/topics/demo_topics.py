from .topics_model import RELIABLE_QOS, TopicSpec

DEMO1_POSITION = TopicSpec(name="/my_position", qos=RELIABLE_QOS)
DEMO2_POSITION = TopicSpec(name="/demo2/pos_demo2", qos=RELIABLE_QOS)
