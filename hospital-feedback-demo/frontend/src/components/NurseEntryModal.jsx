import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Frown,
  Meh,
  ShieldCheck,
  Smile,
  UserRound,
} from "lucide-react";
import { api } from "../api";
import Toast from "./Toast";

const DEPARTMENTS = [
  { id: "OPD", name: "Outpatient Department" },
  { id: "EMERGENCY", name: "Accident & Emergency" },
  { id: "PHARMACY", name: "Main Pharmacy" },
  { id: "BILLING", name: "Accounts & Revenue" },
  { id: "WARDS", name: "Inpatient Wards" },
];

const RATING_TIERS = [
  {
    value: 1,
    label: "Poor",
    color: "rose",
    active: "border-rose bg-rose-soft text-rose",
    icon: Frown,
  },
  {
    value: 2,
    label: "Fair",
    color: "rose",
    active: "border-rose bg-rose-soft text-rose",
    icon: Frown,
  },
  {
    value: 3,
    label: "Good",
    color: "amber",
    active: "border-amber bg-amber/10 text-amber",
    icon: Meh,
  },
  {
    value: 4,
    label: "Very Good",
    color: "emerald",
    active: "border-emerald bg-emerald-soft text-emerald",
    icon: Smile,
  },
  {
    value: 5,
    label: "Excellent",
    color: "emerald",
    active: "border-emerald bg-emerald-soft text-emerald",
    icon: Smile,
  },
];

const ISSUE_CHIPS = [
  "LONG_WAIT",
  "STAFF_COURTESY",
  "DRUG_AVAILABILITY",
  "CLEANLINESS",
  "BILLING_DELAY",
  "QUALITY_OF_CARE",
];

const CHIP_LABELS = {
  LONG_WAIT: "Long Wait",
  STAFF_COURTESY: "Staff Courtesy",
  DRUG_AVAILABILITY: "Drug Availability",
  CLEANLINESS: "Cleanliness",
  BILLING_DELAY: "Billing Delay",
  QUALITY_OF_CARE: "Quality of Care",
};

function nextVisitId() {
  const n = 100 + Math.floor(Math.random() * 900);
  return `VIS-2026-${n}`;
}

export default function NurseEntryModal() {
  const [step, setStep] = useState(1);
  const [visitId, setVisitId] = useState(nextVisitId);
  const [department, setDepartment] = useState("");
  const [rating, setRating] = useState(null);
  const [chips, setChips] = useState([]);
  const [comment, setComment] = useState("");
  const [phone, setPhone] = useState("");
  const [anonymous, setAnonymous] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const toggleChip = (chip) =>
    setChips((prev) =>
      prev.includes(chip) ? prev.filter((c) => c !== chip) : [...prev, chip]
    );

  const submit = async () => {
    setSubmitting(true);
    try {
      const res = await api.nurseFeedback({
        visit_id: visitId,
        department_id: department,
        overall_rating: rating,
        category_tags: chips,
        raw_comment: comment || null,
        is_anonymous: anonymous,
        patient_phone: anonymous ? null : phone || null,
      });
      setToast({
        type: res.escalation_triggered ? "alert" : "success",
        title: res.escalation_triggered ? "Feedback logged & alert dispatched" : "Feedback Logged",
        message: res.escalation_triggered
          ? `Low rating escalated — severity HIGH alert created (${res.alert_id}).`
          : "Record saved to patient_feedback. Dashboard refreshed.",
      });
      // Reset form for next entry
      setVisitId(nextVisitId());
      setStep(1);
      setRating(null);
      setChips([]);
      setComment("");
      setPhone("");
      setAnonymous(true);
    } catch (e) {
      setToast({ type: "error", title: "Submission failed", message: e.message });
    } finally {
      setSubmitting(false);
    }
  };

  const canNext =
    step === 1 ? department !== "" : step === 2 ? rating !== null : true;

  const stepLabels = ["Patient Context", "Satisfaction Rating", "Issue Details"];

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <p className="eyebrow">SmartClinic · 3-step quick log</p>
        <div className="flex items-center gap-3 mt-1.5">
          <span className="w-9 h-9 rounded-lg2 bg-teal-soft text-teal grid place-items-center">
            <ClipboardCheck size={18} />
          </span>
          <h2 className="section-title">Nurse-Assisted Entry</h2>
        </div>
      </div>

      <div className="card overflow-hidden stagger-in" style={{ "--d": "60ms" }}>
        {/* Progress bar */}
        <div className="h-1 bg-chip">
          <div
            className="h-full bg-gradient-to-r from-teal to-emerald transition-all duration-500 ease-out relative overflow-hidden"
            style={{ width: `${(step / 3) * 100}%` }}
          >
            <div className="absolute inset-0 animate-shine bg-gradient-to-r from-transparent via-white/40 to-transparent" />
          </div>
        </div>

        <div className="p-6 sm:p-8">
          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-8">
            {[1, 2, 3].map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                {i > 0 && (
                  <div
                    className={`h-px w-8 sm:w-12 transition-colors duration-300 ${
                      s <= step ? "bg-teal" : "bg-line"
                    }`}
                  />
                )}
                <div className="flex items-center gap-2">
                  <span
                    className={`w-8 h-8 rounded-full grid place-items-center text-xs font-bold transition-all duration-300 ${
                      s < step
                        ? "bg-teal text-white"
                        : s === step
                        ? "bg-teal text-white ring-4 ring-teal/20"
                        : "bg-chip text-ink-muted"
                    }`}
                  >
                    {s < step ? <Check size={14} strokeWidth={3} /> : s}
                  </span>
                  <span
                    className={`text-xs font-semibold hidden sm:block transition-colors duration-200 ${
                      s === step ? "text-ink" : "text-ink-muted"
                    }`}
                  >
                    {stepLabels[s - 1]}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* ---------------------------------------------------- STEP 1 */}
          {step === 1 && (
            <div className="animate-fade-slide space-y-5 max-w-md">
              <div>
                <label className="label-text" htmlFor="visit">
                  Visit ID
                </label>
                <div className="relative">
                  <input
                    id="visit"
                    className="input-field font-medium font-mono text-[13px] tracking-wide"
                    value={visitId}
                    readOnly
                  />
                  <span className="absolute right-3.5 top-1/2 -translate-y-1/2 w-6 h-6 rounded-md bg-teal-soft text-teal grid place-items-center pointer-events-none">
                    <ShieldCheck size={13} />
                  </span>
                </div>
                <p className="caption mt-1.5">Auto-generated for this session.</p>
              </div>

              <div>
                <label className="label-text" htmlFor="dept">
                  Department
                </label>
                <div className="relative">
                  <select
                    id="dept"
                    className="input-field appearance-none pr-10"
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                  >
                    <option value="">Select department…</option>
                    {DEPARTMENTS.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    size={16}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-faint pointer-events-none"
                  />
                </div>
              </div>
            </div>
          )}

          {/* ---------------------------------------------------- STEP 2 */}
          {step === 2 && (
            <div className="animate-fade-slide">
              <p className="text-sm font-medium text-ink mb-5">
                How would the patient rate their overall experience?
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {RATING_TIERS.map((tier) => {
                  const Icon = tier.icon;
                  const active = rating === tier.value;
                  return (
                    <button
                      key={tier.value}
                      onClick={() => setRating(tier.value)}
                      className={`flex flex-col items-center gap-2.5 rounded-lg2 border-2 min-h-[104px] p-3.5 transition-all duration-200 ${
                        active
                          ? tier.active + " scale-[1.04] shadow-lift"
                          : "border-line bg-white hover:-translate-y-1 hover:border-ink/15 hover:shadow-card"
                      }`}
                    >
                      <span
                        className={`w-10 h-10 rounded-full grid place-items-center transition-all duration-200 ${
                          active
                            ? "bg-white/80 scale-110 shadow-card"
                            : "bg-chip text-ink-muted"
                        }`}
                      >
                        <Icon size={19} className={active ? "" : "text-ink-faint"} />
                      </span>
                      <span className="font-serif text-3xl font-semibold leading-none">
                        {tier.value}
                      </span>
                      <span className="text-xs font-semibold">{tier.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* ---------------------------------------------------- STEP 3 */}
          {step === 3 && (
            <div className="animate-fade-slide space-y-5">
              <div>
                <p className="text-sm font-medium text-ink mb-3">
                  Select issue categories <span className="caption">(multi-select)</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  {ISSUE_CHIPS.map((chip) => {
                    const on = chips.includes(chip);
                    return (
                      <button
                        key={chip}
                        onClick={() => toggleChip(chip)}
                        className={`chip border transition-all duration-200 ${
                          on
                            ? "bg-ink text-white border-ink shadow-card"
                            : "bg-chip border-transparent text-ink-muted hover:bg-line hover:-translate-y-px"
                        }`}
                      >
                        {on && <Check size={13} strokeWidth={3} />}
                        {CHIP_LABELS[chip]}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="label-text" htmlFor="comment">
                  Optional Note
                </label>
                <textarea
                  id="comment"
                  rows={3}
                  className="input-field resize-none"
                  placeholder="e.g. Patient waited 2 hours for prescriptions…"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
              </div>

              <div className="flex items-center justify-between gap-3 rounded-lg2 bg-sand/70 border border-line p-4">
                <div className="flex items-center gap-3">
                  <span className="w-9 h-9 rounded-lg2 bg-teal-soft text-teal grid place-items-center shrink-0">
                    <UserRound size={17} />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-ink">Log anonymously</p>
                    <p className="caption">Phone is hashed (SHA-256) when provided</p>
                  </div>
                </div>
                <button
                  role="switch"
                  aria-checked={anonymous}
                  onClick={() => setAnonymous((v) => !v)}
                  className={`relative w-12 h-7 rounded-full transition-colors duration-300 shrink-0 ${
                    anonymous ? "bg-teal" : "bg-line"
                  }`}
                >
                  <span
                    className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow transition-all duration-300 ${
                      anonymous ? "left-6" : "left-1"
                    }`}
                  />
                </button>
              </div>

              {!anonymous && (
                <div className="animate-fade-slide">
                  <label className="label-text" htmlFor="phone">
                    Patient Phone (E.164)
                  </label>
                  <input
                    id="phone"
                    className="input-field"
                    placeholder="+2348012345678"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                  />
                </div>
              )}
            </div>
          )}

          {/* --------------------------------------------------- actions */}
          <div className="flex items-center justify-between mt-8 pt-5 border-t hairline">
            <button
              className="btn-ghost"
              disabled={step === 1}
              onClick={() => setStep((s) => s - 1)}
            >
              <ArrowLeft size={16} /> Back
            </button>

            {step < 3 ? (
              <button
                className="btn-primary"
                disabled={!canNext}
                onClick={() => setStep((s) => s + 1)}
              >
                Continue <ArrowRight size={16} />
              </button>
            ) : (
              <button className="btn-primary" disabled={submitting} onClick={submit}>
                {submitting ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    Saving…
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={16} /> Submit Feedback Record
                  </>
                )}
              </button>
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
