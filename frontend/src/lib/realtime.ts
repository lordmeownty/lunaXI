/**
 * Luna voice.
 *  1) GPT Realtime over WebRTC (ephemeral key minted by the API). Luna can answer AND drive the app via tools.
 *  2) Automatic fallback: browser speech recognition (Edge/Chrome) + spoken replies, so voice commands still work
 *     when Foundry Realtime isn't configured or the network blocks WebRTC.
 */
import { api } from "./api";

export type VoiceStatus = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";
export interface VoiceHandlers {
  onTool: (name: string, args: any) => Promise<any>;
  onUtterance: (text: string) => Promise<string | null>; // fallback mode: handle text, return a reply to speak
  onTranscript: (role: "user" | "luna", text: string) => void;
  onStatus: (s: VoiceStatus, detail?: string) => void;
  onMode: (m: "realtime" | "browser") => void;
}

export function speak(text: string, onEnd?: () => void) {
  if (!("speechSynthesis" in window)) { onEnd?.(); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/[#*_]/g, "")); u.rate = 1.0; u.lang = "en-GB";
  u.onend = () => onEnd?.(); window.speechSynthesis.speak(u);
}

export class LunaVoice {
  private pc?: RTCPeerConnection; private dc?: RTCDataChannel; private mic?: MediaStream; private audio?: HTMLAudioElement;
  private rec: any; private active = false; private mode: "realtime" | "browser" | null = null;
  constructor(private h: VoiceHandlers) {}

  get running() { return this.active; }

  async start(matchId: string) {
    this.active = true;
    this.h.onStatus("connecting");
    try { await this.startRealtime(matchId); }
    catch (e: any) {
      this.teardownRtc();
      if (!this.startBrowser()) { this.active = false; this.h.onStatus("error", `Voice unavailable: ${e?.message ?? e}. Use Edge or Chrome, or add Foundry Realtime keys.`); }
    }
  }

  private async startRealtime(matchId: string) {
    const sess = await api.realtimeSession(matchId);
    this.mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    const pc = new RTCPeerConnection(); this.pc = pc;
    this.audio = new Audio(); this.audio.autoplay = true;
    pc.ontrack = (e) => { if (this.audio) this.audio.srcObject = e.streams[0]; };
    this.mic.getTracks().forEach((t) => pc.addTrack(t, this.mic!));
    const dc = pc.createDataChannel("oai-events"); this.dc = dc;
    dc.onopen = () => { this.send({ type: "session.update", session: sess.session }); this.mode = "realtime"; this.h.onMode("realtime"); this.h.onStatus("listening"); };
    dc.onmessage = (m) => this.onMessage(JSON.parse(m.data));
    pc.onconnectionstatechange = () => { if (["failed", "disconnected"].includes(pc.connectionState) && this.active) this.h.onStatus("error", "Voice connection lost. Tap the mic to reconnect."); };
    const offer = await pc.createOffer(); await pc.setLocalDescription(offer);
    const sep = sess.webrtc_url.includes("?") ? "&" : "?";
    const r = await fetch(`${sess.webrtc_url}${sep}model=${encodeURIComponent(sess.model)}`, { method: "POST", body: offer.sdp, headers: { Authorization: `Bearer ${sess.client_secret}`, "Content-Type": "application/sdp" } });
    if (!r.ok) throw new Error(`realtime negotiation ${r.status}`);
    await pc.setRemoteDescription({ type: "answer", sdp: await r.text() });
  }

  private startBrowser(): boolean {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return false;
    const rec = new SR(); this.rec = rec;
    rec.lang = "en-GB"; rec.continuous = true; rec.interimResults = false;
    rec.onresult = async (e: any) => {
      const text = e.results[e.results.length - 1][0].transcript.trim();
      if (!text) return;
      this.h.onTranscript("user", text); this.h.onStatus("thinking");
      rec.stop();
      const reply = await this.h.onUtterance(text).catch(() => "Sorry, I couldn't do that.");
      if (reply) { this.h.onStatus("speaking"); speak(reply, () => this.resumeBrowser()); } else this.resumeBrowser();
    };
    rec.onerror = (e: any) => { if (e.error === "not-allowed") { this.active = false; this.h.onStatus("error", "Microphone permission denied."); } };
    rec.onend = () => { if (this.active && this.mode === "browser" && !window.speechSynthesis?.speaking) this.resumeBrowser(); };
    this.mode = "browser"; this.h.onMode("browser");
    this.resumeBrowser();
    return true;
  }

  private resumeBrowser() {
    if (!this.active || this.mode !== "browser") return;
    try { this.rec.start(); } catch { /* already started */ }
    this.h.onStatus("listening");
  }

  private send(o: any) { if (this.dc?.readyState === "open") this.dc.send(JSON.stringify(o)); }

  private async onMessage(ev: any) {
    switch (ev.type) {
      case "input_audio_buffer.speech_started": this.h.onStatus("listening"); break;
      case "input_audio_buffer.speech_stopped": this.h.onStatus("thinking"); break;
      case "conversation.item.input_audio_transcription.completed": if (ev.transcript) this.h.onTranscript("user", ev.transcript.trim()); break;
      case "response.output_audio_transcript.done": case "response.audio_transcript.done": if (ev.transcript) this.h.onTranscript("luna", ev.transcript); break;
      case "output_audio_buffer.started": this.h.onStatus("speaking"); break;
      case "output_audio_buffer.stopped": case "response.done": this.h.onStatus("listening"); break;
      case "response.function_call_arguments.done": {
        let args: any = {}; try { args = JSON.parse(ev.arguments || "{}"); } catch { /* ignore */ }
        let output: any; try { output = await this.h.onTool(ev.name, args); } catch (e: any) { output = { error: e?.message ?? "tool failed" }; }
        this.send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: ev.call_id, output: JSON.stringify(output) } });
        this.send({ type: "response.create" }); break;
      }
      case "error": this.h.onStatus("error", ev.error?.message); break;
    }
  }

  /** Typed text while voice is live: realtime → Luna answers aloud; browser mode → handled like speech. */
  async sayText(text: string) {
    if (this.mode === "realtime") { this.send({ type: "conversation.item.create", item: { type: "message", role: "user", content: [{ type: "input_text", text }] } }); this.send({ type: "response.create" }); return; }
    const reply = await this.h.onUtterance(text);
    if (reply) speak(reply);
  }

  private teardownRtc() { this.mic?.getTracks().forEach((t) => t.stop()); this.dc?.close(); this.pc?.close(); this.pc = undefined; this.dc = undefined; this.mic = undefined; }

  stop() {
    this.active = false; this.teardownRtc();
    try { this.rec?.stop(); } catch { /* ignore */ }
    window.speechSynthesis?.cancel();
    this.mode = null; this.h.onStatus("idle");
  }
}
