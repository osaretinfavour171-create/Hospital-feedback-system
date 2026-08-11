import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Inbox,
  RefreshCw,
  ShieldAlert,
  Star,
  TrendingDown,
  TrendingUp,
  Users,
} from "lucide-react";
import { api } from "../api";
import Toast from "./Toast";

function csatSoft(score) {
  if (score === null || score === undefined) return "bg-chip text-ink-muted";
  if (score <= 2) return "bg-rose-soft text-rose";
  if (score < 4) return "bg-amber/10 text-amber";
  return "bg-emerald-soft text-emerald";
}

function severityColor(sev) {
  switch (sev) {
    case "CRITICAL":
      return "bg-rose text-white border border-rose/30";
    case "HIGH":
      return "bg-rose-soft text-rose border border-rose/25";
    case "MEDIUM":
      return "bg-amber/10 text-amber border border-amber/25";
    default:
      return "bg-chip text-ink-muted border border-line";
  }
}

function timeAgo(ts) {
  const diff = Date.now() - new Date(ts.replace(" ", "T")).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

/* Count-up animation for the KPI numerals */
function CountUp({ value, decimals = 0, duration = 900 }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const start = performance.now();
    let raf;
    const step = (ts) => {
      const progress = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(value * eased);
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return <span>{display.toFixed(decimals)}</span>;
}

export default function ExecutiveDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState(null);
  const [resolving, setResolving] = useState(null);
  const [fadingOut, setFadingOut] = useState(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [m, a] = await Promise.all([api.metrics(), api.alerts()]);
      setMetrics(m);
      setAlerts(a);
    } catch (e) {
      setToast({ type: "error", title: "Dashboard load failed", message: e.message });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => load(true), 8000);
    return () => clearInterval(t);
  }, [load]);

  const resolve = async (alertId) => {
    setResolving(alertId);
    try {
      await api.resolveAlert(alertId);
      setFadingOut(alertId);
      setTimeout(() => {
        setAlerts((prev) =>
          prev.map((a) => (a.id === alertId ? { ...a, status: "RESOLVED" } : a))
        );
        setFadingOut(null);
      }, 400);
      setToast({
        type: "success",
        title: "Alert Resolved",
        message: `Alert ${alertId} marked RESOLVED.`,
      });
      load(true);
    } catch (e) {
      setToast({ type: "error", title: "Resolve failed", message: e.message });
    } finally {
      setResolving(null);
    }
  };

  if (loading && !metrics) {
    return (
      <div className="grid place-items-center py-36">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw size={28} className="text-teal animate-spin" />
          <p className="caption">Loading quality metrics…</p>
        </div>
      </div>
    );
  }

  const openAlerts = alerts.filter((a) => a.status === "OPEN");
  const hasData = metrics?.total_responses > 0;

  return (
    <div className="space-y-6">
      {/* --------------------------------------------------------- header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <p className="eyebrow">Quality Intelligence</p>
          <div className="flex items-center gap-3 mt-1.5">
            <h2 className="section-title">Executive Quality Dashboard</h2>
            <span className="inline-flex items-center gap-1.5 caption font-semibold text-emerald">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald animate-pulse" />
              Live · auto-refresh
            </span>
          </div>
        </div>
        <button
          className="btn-ghost !py-2"
          onClick={() => {
            setRefreshing(true);
            load(true);
          }}
          disabled={refreshing}
        >
          <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* ------------------------------------------------------- KPI strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card card-hover p-6 stagger-in" style={{ "--d": "0ms" }}>
          <div className="flex items-center justify-between mb-3">
            <span className="eyebrow">Overall CSAT</span>
            <span className="w-9 h-9 rounded-lg2 bg-teal-soft text-teal grid place-items-center">
              <Star size={17} className="fill-current" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="kpi-value">
              {hasData ? <CountUp value={metrics.overall_csat} decimals={1} /> : "—"}
            </span>
            <span className="caption">/ 5.0</span>
          </div>
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            <p className="caption">
              NPS proxy: {hasData ? `${metrics.nps_proxy_percentage}%` : "—"}
            </p>
            {hasData && metrics.overall_csat >= 4 && (
              <span className="chip bg-emerald-soft text-emerald ml-auto">
                <TrendingUp size={12} /> Healthy
              </span>
            )}
            {hasData && metrics.overall_csat < 3 && (
              <span className="chip bg-rose-soft text-rose ml-auto">
                <TrendingDown size={12} /> At risk
              </span>
            )}
          </div>
        </div>

        <div className="card card-hover p-6 stagger-in" style={{ "--d": "70ms" }}>
          <div className="flex items-center justify-between mb-3">
            <span className="eyebrow">Total Responses</span>
            <span className="w-9 h-9 rounded-lg2 bg-amber/10 text-amber grid place-items-center">
              <Users size={17} />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="kpi-value">
              {hasData ? <CountUp value={metrics.total_responses} /> : "—"}
            </span>
            <span className="caption">patient reviews</span>
          </div>
          <div className="mt-4">
            <p className="caption">
              {metrics.top_department
                ? `Top dept: ${metrics.top_department}`
                : "No feedback yet — try the other tabs!"}
            </p>
          </div>
        </div>

        <div className="card card-hover p-6 stagger-in" style={{ "--d": "140ms" }}>
          <div className="flex items-center justify-between mb-3">
            <span className="eyebrow">Open Alerts</span>
            <span
              className={`w-9 h-9 rounded-lg2 grid place-items-center ${
                openAlerts.length ? "bg-rose-soft text-rose" : "bg-emerald-soft text-emerald"
              }`}
            >
              <AlertTriangle size={17} />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className={`kpi-value ${
                openAlerts.length ? "text-rose" : "text-emerald"
              }`}
            >
              <CountUp value={openAlerts.length} />
            </span>
            <span className="caption">action required</span>
          </div>
          <div className="mt-4">
            <p className="caption">
              {openAlerts.length
                ? "Escalations awaiting triage"
                : "All clear — no open escalations"}
            </p>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------ bento: heatmap + alerts */}
      <div className="grid lg:grid-cols-5 gap-4">
        {/* dept heatmap */}
        <div className="lg:col-span-2 card p-6 stagger-in" style={{ "--d": "0ms" }}>
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-serif text-lg font-semibold text-ink tracking-tight">
              Department CSAT
            </h3>
            <span className="caption">avg by service area</span>
          </div>
          <p className="caption mb-5">Average satisfaction score by department</p>
          <div className="space-y-3.5">
            {metrics.department_metrics.map((d) => {
              const hasFeedback = d.total_count > 0;
              const score = d.average_csat;
              const pct = score === null ? 0 : (score / 5) * 100;
              return (
                <div key={d.department_id} className="flex items-center gap-3">
                  <div className="w-24 shrink-0">
                    <p className="text-xs font-bold text-ink">{d.department_id}</p>
                    <p className="text-[10px] text-ink-muted truncate">{d.department_name}</p>
                  </div>
                  <div className="flex-1 h-2.5 bg-chip rounded-full overflow-hidden">
                    {hasFeedback && (
                      <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${
                          score <= 2
                            ? "bg-gradient-to-r from-rose to-rose/70"
                            : score < 4
                            ? "bg-gradient-to-r from-amber to-amber/70"
                            : "bg-gradient-to-r from-teal to-emerald"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    )}
                    {!hasFeedback && (
                      <div className="h-full w-full grid place-items-center">
                        <span className="text-[9px] text-ink-faint">no data</span>
                      </div>
                    )}
                  </div>
                  <div className="w-20 shrink-0 text-right">
                    {hasFeedback ? (
                      <span className={`chip ${csatSoft(score)} text-xs`}>
                        {score.toFixed(1)}
                      </span>
                    ) : (
                      <span className="caption">—</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* alert queue */}
        <div className="lg:col-span-3 card p-6 stagger-in" style={{ "--d": "90ms" }}>
          <div className="flex items-center gap-2 mb-5">
            <span className="w-8 h-8 rounded-lg2 bg-rose-soft text-rose grid place-items-center">
              <Inbox size={15} />
            </span>
            <h3 className="font-serif text-lg font-semibold text-ink tracking-tight">
              Escalation Alerts
            </h3>
            <span className="chip bg-rose-soft text-rose ml-auto">
              {openAlerts.length} open
            </span>
          </div>

          {alerts.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-14 h-14 rounded-2xl bg-emerald-soft text-emerald grid place-items-center mx-auto mb-4">
                <CheckCircle2 size={26} />
              </div>
              <p className="text-sm font-semibold text-ink">No alerts yet</p>
              <p className="caption mt-1 max-w-xs mx-auto">
                Submit a rating of 1–2 from the Nurse tab to see an escalation appear
                instantly.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {alerts.map((a) => {
                const fading = a.status === "OPEN" && fadingOut === a.id;
                return (
                  <div
                    key={a.id}
                    className={`flex flex-col sm:flex-row sm:items-center gap-3 rounded-lg2 border p-4 transition-all duration-300 ${
                      a.status === "OPEN"
                        ? "border-line bg-white hover:border-teal/30 hover:shadow-lift"
                        : "border-emerald/25 bg-emerald-soft/40 opacity-75"
                    } ${a.status === "OPEN" ? "animate-fade-slide" : ""} ${
                      fading ? "animate-alert-out" : ""
                    }`}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <span
                        className={`w-10 h-10 rounded-lg2 grid place-items-center shrink-0 ${
                          a.status === "OPEN"
                            ? a.severity === "CRITICAL"
                              ? "bg-rose text-white"
                              : "bg-rose-soft text-rose"
                            : "bg-emerald-soft text-emerald"
                        }`}
                      >
                        {a.status === "OPEN" ? (
                          <ShieldAlert size={18} />
                        ) : (
                          <CheckCircle2 size={18} />
                        )}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`chip ${severityColor(a.severity)}`}>
                            {a.severity}
                          </span>
                          <span
                            className={`chip ${
                              a.status === "OPEN"
                                ? "bg-rose-soft text-rose"
                                : "bg-emerald-soft text-emerald"
                            }`}
                          >
                            {a.status}
                          </span>
                          <span className="chip bg-teal-mist text-teal">{a.department_id}</span>
                        </div>
                        <p className="text-sm font-medium text-ink mt-1.5 leading-snug">
                          {a.issue_summary}
                        </p>
                        <p className="caption mt-1 flex items-center gap-1">
                          <Clock size={11} /> {timeAgo(a.created_at)} · Ref {a.feedback_id}
                        </p>
                      </div>
                    </div>

                    {a.status === "OPEN" ? (
                      <button
                        className="btn-ghost !py-2 shrink-0"
                        disabled={resolving === a.id}
                        onClick={() => resolve(a.id)}
                      >
                        {resolving === a.id ? (
                          <>
                            <RefreshCw size={15} className="animate-spin" /> Resolving…
                          </>
                        ) : (
                          <>
                            <CheckCircle2 size={15} className="text-emerald" /> Mark Resolved
                          </>
                        )}
                      </button>
                    ) : (
                      <span className="chip bg-emerald-soft text-emerald shrink-0 self-start sm:self-auto">
                        <CheckCircle2 size={12} /> Resolved
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
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
