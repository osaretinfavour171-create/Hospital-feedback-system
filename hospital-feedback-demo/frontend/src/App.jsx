import { useEffect, useState } from "react";
import {
  Activity,
  ClipboardList,
  HeartPulse,
  LayoutDashboard,
  MessageCircle,
  Stethoscope,
} from "lucide-react";
import NurseEntryModal from "./components/NurseEntryModal";
import WhatsAppSimulator from "./components/WhatsAppSimulator";
import ExecutiveDashboard from "./components/ExecutiveDashboard";
import { api } from "./api";

const TABS = [
  {
    id: "nurse",
    label: "Nurse-Assisted Entry",
    icon: Stethoscope,
  },
  {
    id: "whatsapp",
    label: "WhatsApp Simulator",
    icon: MessageCircle,
  },
  {
    id: "dashboard",
    label: "Executive Dashboard",
    icon: LayoutDashboard,
  },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("nurse");
  const [backendStatus, setBackendStatus] = useState({
    state: "checking",
    aiMode: null,
  });

  useEffect(() => {
    api
      .health()
      .then((h) => setBackendStatus({ state: "online", aiMode: h.ai_mode }))
      .catch(() => setBackendStatus({ state: "offline", aiMode: null }));
  }, []);

  const statusMeta = {
    online: {
      dot: "bg-emerald",
      pill: "bg-emerald-soft text-emerald border-emerald/30",
      label: backendStatus.aiMode === "groq" ? "Backend Online · Groq AI" : "Backend Online · Offline AI",
      ping: true,
    },
    offline: {
      dot: "bg-rose",
      pill: "bg-rose-soft text-rose border-rose/30",
      label: "Backend Offline",
      ping: false,
    },
    checking: {
      dot: "bg-ink-faint",
      pill: "bg-chip text-ink-muted border-line",
      label: "Checking backend…",
      ping: false,
    },
  }[backendStatus.state];

  return (
    <div className="min-h-screen bg-paper">
      {/* ------------------------------------------------- ambient backdrop */}
      <div className="pointer-events-none fixed inset-0 bg-ambient" aria-hidden />
      <div
        className="pointer-events-none fixed inset-0 bg-dots opacity-60"
        aria-hidden
      />

      {/* ---------------------------------------------------------- header */}
      <header className="relative z-40 border-b hairline bg-paper/85 backdrop-blur-xl sticky top-0">
        <div className="max-w-6xl mx-auto px-6 pt-5 pb-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              {/* emblem */}
              <div className="relative">
                <div className="w-11 h-11 rounded-card bg-gradient-to-br from-teal to-teal-deep text-white grid place-items-center shadow-lift">
                  <HeartPulse size={22} strokeWidth={2.2} />
                </div>
                <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-amber border-2 border-paper grid place-items-center">
                  <span className="w-1.5 h-1.5 rounded-full bg-white" />
                </div>
              </div>
              <div>
                <p className="eyebrow">University of Benin Teaching Hospital</p>
                <h1 className="font-serif text-[22px] font-semibold text-ink leading-tight tracking-tight">
                  UBTH Feedback Platform
                </h1>
                <p className="caption mt-0.5">Omnichannel Care Quality · Demo Edition</p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span
                className={`inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-xs font-semibold border transition-colors duration-300 ${statusMeta.pill}`}
              >
                <span className="relative flex w-2 h-2">
                  {statusMeta.ping && (
                    <span
                      className={`absolute inline-flex h-full w-full rounded-full ${statusMeta.dot} opacity-60 animate-ping`}
                    />
                  )}
                  <span
                    className={`relative inline-flex rounded-full w-2 h-2 ${statusMeta.dot} ${
                      backendStatus.state === "checking" ? "animate-pulse" : ""
                    }`}
                  />
                </span>
                {statusMeta.label}
              </span>
            </div>
          </div>

          {/* ------------------------------------------------------ tab bar */}
          <nav className="mt-4 -mb-px flex gap-1 overflow-x-auto">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold whitespace-nowrap transition-all duration-200 min-h-[44px] rounded-t-lg2 ${
                    active ? "text-teal" : "text-ink-muted hover:text-ink"
                  }`}
                >
                  <Icon size={17} strokeWidth={active ? 2.4 : 2} />
                  {tab.label}
                  {active && (
                    <span className="absolute inset-x-2 -bottom-px h-[2.5px] rounded-full bg-gradient-to-r from-teal to-teal/40" />
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {/* ---------------------------------------------------------- content */}
      <main className="relative max-w-6xl mx-auto px-6 py-8">
        <div key={activeTab} className="animate-float-up">
          {activeTab === "nurse" && <NurseEntryModal />}
          {activeTab === "whatsapp" && <WhatsAppSimulator />}
          {activeTab === "dashboard" && <ExecutiveDashboard />}
        </div>
      </main>

      {/* Small footer */}
      <footer className="relative max-w-6xl mx-auto px-6 pb-10">
        <div className="border-t hairline pt-6 flex items-center gap-2 caption flex-wrap">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-teal" />
            Healing Teal design system
          </span>
          <span className="text-ink-faint">·</span>
          <span className="inline-flex items-center gap-1.5">
            <ClipboardList size={13} />
            <Activity size={13} />
            Patient feedback stored locally in
            <code className="bg-chip px-1.5 py-0.5 rounded text-[11px] text-ink">
              hospital_demo.db
            </code>
          </span>
          <span className="text-ink-faint">·</span>
          <span>PII hashed with SHA-256</span>
        </div>
      </footer>
    </div>
  );
}
