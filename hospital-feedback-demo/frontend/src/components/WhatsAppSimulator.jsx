import { useEffect, useRef, useState } from "react";
import {
  Bot,
  BrainCircuit,
  CheckCheck,
  Lock,
  Mic,
  MicOff,
  Phone,
  Send,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { api } from "../api";
import Toast from "./Toast";

const BOT_PHONE = "+2348012345678";

const QUICK_SUGGESTIONS = [
  "The pharmacy wait time was 2 hours today!",
  "The doctor was excellent and very polite.",
  "The emergency room was dirty and we waited 3 hours.",
  "What dosage of Amoxicillin should I give my child?",
];

const PIPELINE_STEPS = [
  { key: "pii", label: "PII Protection · SHA-256 hash" },
  { key: "extract", label: "Structured JSON extraction" },
  { key: "escalate", label: "Escalation evaluation" },
];

const STEP_LABELS = {
  department: "asking · department",
  rating: "asking · satisfaction",
  issues: "asking · priorities",
  detail: "asking · extra detail",
  confirm: "confirming · summary",
  reset: "conversation reset",
};

export default function WhatsAppSimulator() {
  const [messages, setMessages] = useState([
    {
      role: "bot",
      text: "Hello! 👋 I'm the UBTH feedback assistant. Tell me about your visit — a text or voice note works fine.",
      time: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [phone, setPhone] = useState(BOT_PHONE);
  const [processing, setProcessing] = useState(false);
  const [recording, setRecording] = useState(false);
  const [log, setLog] = useState([]);
  const [lastHash, setLastHash] = useState(null);
  const [toast, setToast] = useState(null);
  const chatEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, processing]);

  const pushBotMessage = (text) =>
    setMessages((prev) => [...prev, { role: "bot", text, time: new Date() }]);

  const addLog = (entry) =>
    setLog((prev) => [
      ...prev,
      { ...entry, time: new Date().toLocaleTimeString() },
    ]);

  const simulateSteps = (hash, extracted, escalation) => {
    setLog([]);
    const stepDefs = [
      {
        key: "pii",
        render: () => (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold text-teal">
              PII Protection · SHA-256 hash
            </span>
            <code className="text-[11px] break-all text-ink-muted font-mono bg-paper rounded-md px-2 py-1 border border-line">
              {hash || "n/a (anonymous)"}
            </code>
          </div>
        ),
      },
      {
        key: "extract",
        render: () => (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold text-teal">
              Structured JSON extraction
            </span>
            <pre className="text-[11px] leading-relaxed font-mono text-teal-deep bg-sand rounded-lg2 p-3 overflow-x-auto border border-line">
{JSON.stringify(extracted, null, 2)}
            </pre>
          </div>
        ),
      },
      {
        key: "escalate",
        render: () => (
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-teal">
              Escalation evaluation
            </span>
            {escalation ? (
              <span className="chip bg-rose-soft text-rose border border-rose/25">
                HIGH severity alert created
              </span>
            ) : (
              <span className="chip bg-emerald-soft text-emerald border border-emerald/25">
                No escalation
              </span>
            )}
          </div>
        ),
      },
    ];

    stepDefs.forEach((s, i) => {
      setTimeout(() => addLog({ ...s, render: s.render() }), 350 * (i + 1));
    });
  };

  const sendText = async (overrideText) => {
    const text = (overrideText ?? input).trim();
    if (!text || processing) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text, time: new Date() }]);
    setProcessing(true);
    try {
      const res = await api.whatsappText({ phone_number: phone, message_text: text });
      if (!res.guardrail_triggered) setLastHash(res.phone_hash);
      if (res.guardrail_triggered) {
        setLog([]);
        addLog({
          render: (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-rose">🛡️ Guardrail triggered</span>
              <span className="chip bg-rose-soft text-rose border border-rose/25">No record saved</span>
            </div>
          ),
        });
      } else if (res.conversational) {
        setLog([]);
        addLog({
          render: (
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-teal">
                💬 Conversational intake · {STEP_LABELS[res.conversation_step] || "asking"}
              </span>
              <span className="text-[11px] text-ink-muted">
                Waiting for the patient's next answer…
              </span>
            </div>
          ),
        });
      } else {
        simulateSteps(res.phone_hash, res.extracted_data, res.escalation_triggered);
      }
      setTimeout(() => {
        if (res.guardrail_triggered) {
          pushBotMessage("🛡️ " + res.message);
          setToast({
            type: "alert",
            title: "Medical guardrail triggered",
            message: "No feedback record was saved.",
          });
        } else if (res.conversational) {
          pushBotMessage(res.message);
        } else {
          pushBotMessage(res.message);
          if (res.escalation_triggered) {
            setToast({
              type: "alert",
              title: "Escalation triggered",
              message: `Alert ${res.alert_id} created — see Executive Dashboard.`,
            });
          } else {
            setToast({
              type: "success",
              title: "Feedback logged",
              message: `Ref: ${res.feedback_id}`,
            });
          }
        }
        setProcessing(false);
      }, 1300);
    } catch (e) {
      setProcessing(false);
      pushBotMessage("⚠️ Something went wrong on my end — please try again.");
      setToast({ type: "error", title: "Error", message: e.message });
    }
  };

  // ------------------------------------------------------------- audio
  const toggleRecording = async () => {
    if (recording) {
      mediaRecorderRef.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => chunksRef.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await sendAudio(blob);
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setRecording(true);
    } catch {
      setToast({
        type: "error",
        title: "Microphone unavailable",
        message: "Voice notes need mic permission — use text instead, or try the demo with the browser mic.",
      });
    }
  };

  const sendAudio = async (blob) => {
    const form = new FormData();
    form.append("phone_number", phone);
    form.append("audio_file", blob, "voice-note.webm");
    setProcessing(true);
    try {
      const res = await api.whatsappAudio(form);
      if (!res.guardrail_triggered) setLastHash(res.phone_hash);
      if (res.guardrail_triggered) {
        setLog([]);
        addLog({
          render: (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-rose">🛡️ Guardrail triggered</span>
              <span className="chip bg-rose-soft text-rose border border-rose/25">No record saved</span>
            </div>
          ),
        });
      } else if (res.conversational) {
        setLog([]);
        addLog({
          render: (
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-teal">
                💬 Conversational intake · {STEP_LABELS[res.conversation_step] || "asking"}
              </span>
              <span className="text-[11px] text-ink-muted">
                Waiting for the patient's next answer…
              </span>
            </div>
          ),
        });
      } else {
        simulateSteps(res.phone_hash, res.extracted_data, res.escalation_triggered);
      }
      setTimeout(() => {
        pushBotMessage(
          res.guardrail_triggered
            ? "🛡️ " + res.message
            : `🎙️ Got your voice note. ${res.message}`
        );
        if (res.guardrail_triggered) {
          setToast({
            type: "alert",
            title: "Medical guardrail triggered",
            message: "No feedback record was saved.",
          });
        }
        setProcessing(false);
      }, 1200);
    } catch (e) {
      setProcessing(false);
      pushBotMessage("⚠️ " + e.message);
      setToast({ type: "error", title: "Audio failed", message: e.message });
    }
  };

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <p className="eyebrow">Patient channel · AI extraction</p>
        <div className="flex items-center gap-3 mt-1.5">
          <span className="w-9 h-9 rounded-lg2 bg-teal-soft text-teal grid place-items-center">
            <Bot size={18} />
          </span>
          <h2 className="section-title">WhatsApp Simulator</h2>
        </div>
      </div>

      <div className="grid lg:grid-cols-5 gap-4">
        {/* --------------------------------------------------- chat panel */}
        <div className="lg:col-span-3 card flex flex-col overflow-hidden min-h-[640px] shadow-lift stagger-in" style={{ "--d": "60ms" }}>
          {/* chat header */}
          <div className="relative flex items-center gap-3 px-5 py-4 bg-gradient-to-r from-teal to-teal-deep text-white overflow-hidden">
            <div className="absolute inset-0 bg-dots opacity-20" aria-hidden />
            <div className="w-10 h-10 rounded-full bg-white/15 grid place-items-center relative ring-2 ring-white/20">
              <Bot size={20} />
              <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald border-2 border-teal rounded-full" />
            </div>
            <div className="flex-1 relative">
              <p className="text-sm font-bold">UBTH Feedback Assistant</p>
              <p className="text-xs text-white/80 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-soft inline-block animate-pulse" />
                {recording ? "Recording…" : "Online · replies instantly"}
              </p>
            </div>
            <Phone size={18} className="opacity-80 relative" />
          </div>

          {/* messages */}
          <div className="flex-1 bg-[#EDE8DE]/50 p-4 space-y-3 overflow-y-auto max-h-[430px]">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[78%] rounded-2xl px-3.5 py-2.5 text-sm shadow-card animate-fade-slide ${
                    m.role === "user"
                      ? "bg-gradient-to-br from-teal to-teal-dark text-white rounded-br-sm"
                      : "bg-white text-ink rounded-bl-sm border border-line"
                  }`}
                >
                  <p className="leading-relaxed">{m.text}</p>
                  <div
                    className={`flex items-center justify-end gap-1 mt-1 text-[10px] ${
                      m.role === "user" ? "text-white/70" : "text-ink-faint"
                    }`}
                  >
                    {m.time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    {m.role === "user" && <CheckCheck size={12} />}
                  </div>
                </div>
              </div>
            ))}

            {processing && (
              <div className="flex justify-start">
                <div className="bg-white border border-line rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5 shadow-card">
                  <span className="typing-dot w-2 h-2 bg-ink-faint rounded-full" />
                  <span className="typing-dot w-2 h-2 bg-ink-faint rounded-full" style={{ animationDelay: "0.15s" }} />
                  <span className="typing-dot w-2 h-2 bg-ink-faint rounded-full" style={{ animationDelay: "0.3s" }} />
                </div>
              </div>
            )}

            {/* quick suggestions */}
            {!processing && messages.length <= 2 && (
              <div className="flex flex-wrap gap-2 pt-2">
                {QUICK_SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => sendText(s)}
                    className="text-xs bg-white border border-line rounded-full px-3 py-2 text-ink-muted hover:border-teal hover:text-teal transition-all duration-200 hover:-translate-y-px shadow-card"
                  >
                    {s.length > 42 ? s.slice(0, 42) + "…" : s}
                  </button>
                ))}
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* input bar */}
          <div className="border-t hairline p-3.5 bg-white">
            <div className="flex items-center gap-2">
              <input
                className="input-field flex-1"
                placeholder="Type a message…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendText()}
                disabled={processing || recording}
              />
              <button
                onClick={toggleRecording}
                disabled={processing}
                aria-label={recording ? "Stop recording" : "Record voice note"}
                className={`w-11 h-11 rounded-full grid place-items-center transition-all duration-200 shrink-0 ${
                  recording
                    ? "bg-rose text-white mic-recording"
                    : "bg-chip text-ink-muted hover:bg-line hover:text-ink"
                }`}
              >
                {recording ? <MicOff size={18} /> : <Mic size={18} />}
              </button>
              <button
                onClick={() => sendText()}
                disabled={!input.trim() || processing || recording}
                className="w-11 h-11 rounded-full bg-gradient-to-br from-teal to-teal-dark text-white grid place-items-center hover:shadow-lift hover:-translate-y-px transition-all duration-200 disabled:opacity-40 shrink-0"
                aria-label="Send"
              >
                <Send size={17} />
              </button>
            </div>
            {recording && (
              <p className="caption mt-2 text-rose font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-rose animate-pulse" />
                Recording voice note — tap stop to send
              </p>
            )}
            <div className="flex items-center gap-2 mt-2.5">
              <Phone size={12} className="text-ink-faint" />
              <input
                className="text-xs bg-transparent border-none text-ink-muted w-40 focus:outline-none"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                aria-label="Patient phone number"
                title="Patient phone number (hashed before storage)"
              />
              <span className="caption ml-auto inline-flex items-center gap-1">
                <Lock size={10} /> hashed with SHA-256
              </span>
            </div>
          </div>
        </div>

        {/* ----------------------------------------------- AI pipeline log */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="card p-6 stagger-in" style={{ "--d": "120ms" }}>
            <div className="flex items-center gap-2 mb-5">
              <span className="w-8 h-8 rounded-lg2 bg-teal-soft text-teal grid place-items-center">
                <BrainCircuit size={16} />
              </span>
              <h3 className="font-serif text-lg font-semibold text-ink tracking-tight">
                Groq AI Pipeline
              </h3>
              <span className="chip bg-teal-mist text-teal border border-teal/20 ml-auto">
                <Sparkles size={11} /> llama-3.3-70b
              </span>
            </div>

            {log.length === 0 ? (
              <div className="text-center py-10">
                <div className="w-12 h-12 rounded-2xl bg-chip text-ink-faint grid place-items-center mx-auto mb-3">
                  <ShieldCheck size={22} />
                </div>
                <p className="caption max-w-[220px] mx-auto">
                  Start a conversation — the assistant will ask a few questions, then log your feedback.
                </p>
              </div>
            ) : (
              <ol className="space-y-3">
                {log.map((entry, i) => (
                  <li
                    key={i}
                    className="animate-fade-slide rounded-lg2 border border-line bg-sand/50 p-3.5"
                    style={{ animationDelay: `${i * 120}ms` }}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-teal">
                        <span className="w-5 h-5 rounded-md bg-teal-soft grid place-items-center">
                          <CheckCheck size={11} />
                        </span>
                        Step {i + 1}
                      </span>
                      <span className="caption">{entry.time}</span>
                    </div>
                    {entry.render}
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="card p-6 stagger-in" style={{ "--d": "180ms" }}>
            <div className="flex items-center gap-2 mb-3">
              <span className="w-8 h-8 rounded-lg2 bg-amber/10 text-amber grid place-items-center">
                <User size={16} />
              </span>
              <h3 className="font-serif text-lg font-semibold text-ink tracking-tight">
                Why this matters
              </h3>
            </div>
            <ul className="space-y-2.5 caption leading-relaxed">
              {[
                "Phone numbers are never stored raw — only a salted SHA-256 hash.",
                "Medical advice requests are refused by the guardrail, never logged.",
                "Low ratings (≤ 2) auto-create HIGH/CRITICAL escalation alerts.",
                "Voice notes are transcribed with whisper-large-v3 (needs a Groq key).",
              ].map((item) => (
                <li key={item} className="flex gap-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal mt-1.5 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
            {lastHash && (
              <div className="mt-4 pt-4 border-t hairline">
                <p className="caption mb-1.5 inline-flex items-center gap-1">
                  <Lock size={10} /> Latest PII hash
                </p>
                <code className="block text-[10px] font-mono text-ink-muted break-all bg-paper border border-line rounded-lg2 px-2.5 py-2">
                  {lastHash}
                </code>
              </div>
            )}
          </div>
        </div>
      </div>

      {toast && (
        <Toast
          type={toast.type}
          title={toast.title}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
