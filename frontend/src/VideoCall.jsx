import { useEffect, useRef, useState } from "react";
import { api } from "./api";

// Free public STUN server: helps each phone discover its public network address.
// (Some strict networks also need a TURN relay server; described in the report, not built.)
const ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];
const MAX_VIDEO_BITRATE = 150_000; // ~150 kbps: workable on weak 3G

// Full-screen 1-to-1 video consult for one referral (CHV, nurse or doctor).
export default function VideoCall({ referralId, title, t, onClose }) {
  const localVideo = useRef(null);
  const remoteVideo = useRef(null);
  const pcRef = useRef(null); // the RTCPeerConnection
  const streamRef = useRef(null); // my camera + microphone
  const [status, setStatus] = useState("starting"); // starting | waiting | connected | ended | error
  const [peer, setPeer] = useState(null);
  const [micOn, setMicOn] = useState(true);
  const [videoOn, setVideoOn] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let pollTimer = null;
    const pendingIce = []; // ICE that arrives before the other side's description
    const signal = (type, data) => api(`/calls/${referralId}/signal`, { method: "POST", body: { type, data } });

    async function start() {
      // 1. Camera + mic, small video to save bandwidth
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: { width: 320, height: 240, frameRate: 15 },
        });
      } catch {
        setError(t.cameraError);
        setStatus("error");
        return;
      }
      if (cancelled) return stream.getTracks().forEach((tr) => tr.stop());
      streamRef.current = stream;
      localVideo.current.srcObject = stream;

      // 2. Connection object: sends my tracks, shows theirs
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      pcRef.current = pc;
      stream.getTracks().forEach((track) => pc.addTrack(track, stream));
      pc.ontrack = (e) => (remoteVideo.current.srcObject = e.streams[0]);
      pc.onicecandidate = (e) => e.candidate && signal("ice", e.candidate.toJSON());
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "connected") {
          setStatus("connected");
          limitBitrate(pc);
        }
      };

      // 3. Join the room. The second person to arrive makes the offer.
      let joined;
      try {
        joined = await api(`/calls/${referralId}/join`, { method: "POST" });
      } catch (err) {
        setError(err.message);
        setStatus("error");
        return;
      }
      if (cancelled) return;
      setPeer(joined.peer);
      setStatus(joined.peer ? "connecting" : "waiting");
      if (joined.start_call) {
        await pc.setLocalDescription(await pc.createOffer());
        await signal("offer", pc.localDescription.toJSON());
      }

      // 4. Every second: collect messages the other side sent us via the server
      pollTimer = setInterval(async () => {
        let res;
        try {
          res = await api(`/calls/${referralId}/signal`);
        } catch {
          return; // weak signal: try again next second
        }
        if (res.peer) setPeer(res.peer);
        for (const msg of res.messages) {
          if (msg.type === "offer") {
            await pc.setRemoteDescription(msg.data);
            await pc.setLocalDescription(await pc.createAnswer());
            await signal("answer", pc.localDescription.toJSON());
            pendingIce.splice(0).forEach((c) => pc.addIceCandidate(c));
          } else if (msg.type === "answer") {
            await pc.setRemoteDescription(msg.data);
            pendingIce.splice(0).forEach((c) => pc.addIceCandidate(c));
          } else if (msg.type === "ice") {
            if (pc.remoteDescription) await pc.addIceCandidate(msg.data);
            else pendingIce.push(msg.data);
          } else if (msg.type === "bye") {
            setStatus("ended");
            clearInterval(pollTimer);
          }
        }
      }, 1000);
    }

    start();

    // Leaving the screen = hang up: tell the other side, free the camera
    return () => {
      cancelled = true;
      clearInterval(pollTimer);
      api(`/calls/${referralId}/leave`, { method: "POST" }).catch(() => {});
      pcRef.current?.close();
      streamRef.current?.getTracks().forEach((tr) => tr.stop());
    };
  }, [referralId, t.cameraError]);

  const toggleMic = () => {
    streamRef.current?.getAudioTracks().forEach((tr) => (tr.enabled = !micOn));
    setMicOn(!micOn);
  };

  // Audio-only: stop sending video (for very weak signal)
  const toggleVideo = () => {
    streamRef.current?.getVideoTracks().forEach((tr) => (tr.enabled = !videoOn));
    setVideoOn(!videoOn);
  };

  const statusText = {
    starting: t.callStarting,
    waiting: t.callWaiting,
    connecting: t.callConnecting,
    connected: `${t.callConnected} ${peer?.name ?? ""}`,
    ended: t.callEnded,
    error: error,
  }[status];

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-stone-900 text-white">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="font-semibold">📹 {title}</p>
          <p className={`text-sm ${status === "error" ? "text-red-300" : "text-stone-300"}`}>{statusText}</p>
        </div>
        {status === "connected" && <span className="rounded-full bg-emerald-500 px-2 py-0.5 text-xs font-semibold">LIVE</span>}
      </div>

      <div className="relative flex-1 bg-black">
        {/* The other person (big) */}
        <video ref={remoteVideo} autoPlay playsInline className="h-full w-full object-contain" />
        {status !== "connected" && (
          <div className="absolute inset-0 flex items-center justify-center text-stone-400">{statusText}</div>
        )}
        {/* Me (small, mirrored, muted so I don't hear myself) */}
        <video
          ref={localVideo}
          autoPlay
          playsInline
          muted
          className="absolute bottom-3 right-3 w-32 -scale-x-100 rounded-lg border-2 border-white/30 sm:w-48"
        />
      </div>

      <div className="flex justify-center gap-3 px-4 py-4">
        <button onClick={toggleMic} className={`rounded-full px-4 py-3 text-sm font-semibold ${micOn ? "bg-stone-700" : "bg-amber-600"}`}>
          {micOn ? `🎙 ${t.mute}` : `🔇 ${t.unmute}`}
        </button>
        <button onClick={toggleVideo} className={`rounded-full px-4 py-3 text-sm font-semibold ${videoOn ? "bg-stone-700" : "bg-amber-600"}`}>
          {videoOn ? `🔈 ${t.audioOnly}` : `📷 ${t.videoOnAgain}`}
        </button>
        <button onClick={onClose} className="rounded-full bg-red-600 px-5 py-3 text-sm font-semibold hover:bg-red-700">
          ⏹ {t.hangUp}
        </button>
      </div>
    </div>
  );
}

// Cap the video bitrate once connected, so calls survive weak rural signal
async function limitBitrate(pc) {
  for (const sender of pc.getSenders()) {
    if (sender.track?.kind !== "video") continue;
    const params = sender.getParameters();
    if (!params.encodings?.length) params.encodings = [{}];
    params.encodings[0].maxBitrate = MAX_VIDEO_BITRATE;
    await sender.setParameters(params).catch(() => {});
  }
}
