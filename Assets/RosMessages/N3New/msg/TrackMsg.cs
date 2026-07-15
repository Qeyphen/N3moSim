//Hand-written to match Unity-ROS MessageGeneration output for n3_new_msgs/Track.
//(Equivalent to what Robotics > Generate ROS Messages would produce.)
using System;
using System.Linq;
using System.Collections.Generic;
using System.Text;
using Unity.Robotics.ROSTCPConnector.MessageGeneration;

namespace RosMessageTypes.N3New
{
    [Serializable]
    public class TrackMsg : Message
    {
        public const string k_RosMessageName = "n3_new_msgs/Track";
        public override string RosMessageName => k_RosMessageName;

        //  A moving object: ground truth from scenario_generator or estimated state from tracker.
        //  Stamp is in the TrackArray header, not repeated here.
        public const byte UNKNOWN = 0;
        public const byte SAILBOAT = 1;
        public const byte MOTORBOAT = 2;
        public const byte JETSKI = 3;
        public const byte KAYAK = 4;
        public const byte PADDLEBOARD = 5;
        public const byte SWIMMER = 6;
        public const byte DINGHY = 7;
        public const byte FISHING_BOAT = 8;
        public const byte FERRY = 9;
        public const byte CARGO = 10;
        public const byte BUOY = 11;
        public const byte DEBRIS = 12;
        public const byte WINDSURF = 13;
        public const byte KITESURF = 14;
        public const byte PEDALO = 15;

        public uint id;
        //  unique track identifier
        public Geometry.PoseMsg pose;
        //  position and orientation (ENU frame)
        public Geometry.TwistMsg twist;
        //  linear and angular velocity
        public byte type;
        //  track type (see constants above)

        public TrackMsg()
        {
            this.id = 0;
            this.pose = new Geometry.PoseMsg();
            this.twist = new Geometry.TwistMsg();
            this.type = 0;
        }

        public TrackMsg(uint id, Geometry.PoseMsg pose, Geometry.TwistMsg twist, byte type)
        {
            this.id = id;
            this.pose = pose;
            this.twist = twist;
            this.type = type;
        }

        public static TrackMsg Deserialize(MessageDeserializer deserializer) => new TrackMsg(deserializer);

        private TrackMsg(MessageDeserializer deserializer)
        {
            deserializer.Read(out this.id);
            this.pose = Geometry.PoseMsg.Deserialize(deserializer);
            this.twist = Geometry.TwistMsg.Deserialize(deserializer);
            deserializer.Read(out this.type);
        }

        public override void SerializeTo(MessageSerializer serializer)
        {
            serializer.Write(this.id);
            serializer.Write(this.pose);
            serializer.Write(this.twist);
            serializer.Write(this.type);
        }

        public override string ToString()
        {
            return "TrackMsg: " +
            "\nid: " + id.ToString() +
            "\npose: " + pose.ToString() +
            "\ntwist: " + twist.ToString() +
            "\ntype: " + type.ToString();
        }

#if UNITY_EDITOR
        [UnityEditor.InitializeOnLoadMethod]
#else
        [UnityEngine.RuntimeInitializeOnLoadMethod]
#endif
        public static void Register()
        {
            MessageRegistry.Register(k_RosMessageName, Deserialize);
        }
    }
}
