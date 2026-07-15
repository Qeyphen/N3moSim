//Hand-written to match Unity-ROS MessageGeneration output for n3_new_msgs/TrackArray.
//(Equivalent to what Robotics > Generate ROS Messages would produce.)
using System;
using System.Linq;
using System.Collections.Generic;
using System.Text;
using Unity.Robotics.ROSTCPConnector.MessageGeneration;

namespace RosMessageTypes.N3New
{
    [Serializable]
    public class TrackArrayMsg : Message
    {
        public const string k_RosMessageName = "n3_new_msgs/TrackArray";
        public override string RosMessageName => k_RosMessageName;

        //  Batch of tracks in a single frame.
        public Std.HeaderMsg header;
        public TrackMsg[] tracks;

        public TrackArrayMsg()
        {
            this.header = new Std.HeaderMsg();
            this.tracks = new TrackMsg[0];
        }

        public TrackArrayMsg(Std.HeaderMsg header, TrackMsg[] tracks)
        {
            this.header = header;
            this.tracks = tracks;
        }

        public static TrackArrayMsg Deserialize(MessageDeserializer deserializer) => new TrackArrayMsg(deserializer);

        private TrackArrayMsg(MessageDeserializer deserializer)
        {
            this.header = Std.HeaderMsg.Deserialize(deserializer);
            deserializer.Read(out this.tracks, TrackMsg.Deserialize, deserializer.ReadLength());
        }

        public override void SerializeTo(MessageSerializer serializer)
        {
            serializer.Write(this.header);
            serializer.WriteLength(this.tracks);
            serializer.Write(this.tracks);
        }

        public override string ToString()
        {
            return "TrackArrayMsg: " +
            "\nheader: " + header.ToString() +
            "\ntracks: " + System.String.Join(", ", tracks.ToList());
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
