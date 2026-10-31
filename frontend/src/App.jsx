import { useState, useEffect } from "react";
import Login from "./Login";

export default function App() {
  const [lang, setLang] = useState("en");
  const [chw, setChw] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [patients, setPatients] = useState([]);
  const [view, setView] = useState("assess");
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [form, setForm] = useState({
    name: "",
    age: "",
    gestational_age: "",
    systolic_bp: "",
    diastolic_bp: "",
    weight: "",
    hemoglobin: "",
    body_temp: "",
    heart_rate: "",
    previous_complications: false,
  });

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const text = {
    en: {
      title: "SafeArrive",
      subtitle: "Antenatal Risk Assessment",
      patientInfo: "Patient Information",
      patientName: "Patient Name",
      age: "Mother's Age",
      gestational_age: "Gestational Age (weeks)",
      systolic_bp: "Systolic BP",
      diastolic_bp: "Diastolic BP",
      weight: "Weight (kg)",
      hemoglobin: "Hemoglobin (g/dL)",
      previous_complications: "Previous Complications?",
      submit: "Assess Risk",
      loading: "Assessing...",
      risk: "Risk Level",
      sendSMS: "Send Referral SMS",
      dashboard: "Dashboard",
      assess: "New Assessment",
      logout: "Logout",
      noPatients: "No assessments yet.\nStart a new assessment to see results here.",
      smsSent: "✅ SMS Sent!",
      total: "Total",
    },
    tw: {
      title: "SafeArrive",
      subtitle: "Awoɔ Tebea Nhwehwɛmu",
      patientInfo: "Ɔyareni Nsɛm",
      patientName: "Ɔyareni Din",
      age: "Ɔba Mame Nna",
      gestational_age: "Awoɔ Nna (nnawɔtwe)",
      systolic_bp: "Mogya Tumi (Sys)",
      diastolic_bp: "Mogya Tumi (Dia)",
      weight: "Ogye (kg)",
      hemoglobin: "Mogya Tumi (g/dL)",
      previous_complications: "Ɔwɔ Mmerɛ Bi Nsɛm?",
      submit: "Hwɛ Tebea",
      loading: "Ehwɛ mu...",
      risk: "Ɔhaw Tebea",
      sendSMS: "Kɔ SMS",
      dashboard: "Dashboard",
      assess: "Nhwehwɛmu Foforo",
      logout: "Fi Mu",
      noPatients: "Nhwehwɛmu biara nni hɔ.\nHyɛ nhwehwɛmu foforo ase.",
      smsSent: "✅ SMS Akɔ!",
      total: "Nyinaa",
    },
  };

  const t = text[lang];

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm({ ...form, [name]: type === "checkbox" ? checked : value });
  };

  const handleSubmit = async () => {
    setLoading(true);
    setResult(null);
    try {
      const response = await fetch("http://127.0.0.1:8000/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          age: parseInt(form.age),
          gestational_age: parseInt(form.gestational_age),
          systolic_bp: parseInt(form.systolic_bp),
          diastolic_bp: parseInt(form.diastolic_bp),
          weight: parseFloat(form.weight),
          hemoglobin: parseFloat(form.hemoglobin),
          body_temp: parseFloat(form.body_temp),
          heart_rate: parseInt(form.heart_rate),
          previous_complications: form.previous_complications,
        }),
      });
      const data = await response.json();
      const assessment = {
        id: Date.now(),
        name: form.name || "Unknown",
        age: form.age,
        risk_level: data.risk_level,
        risk_score: data.risk_score,
        explanation: data.explanation,
        time: new Date().toLocaleTimeString(),
        smsSent: false,
      };
      setResult({ ...data, id: assessment.id });
      setPatients((prev) => [assessment, ...prev]);
    } catch (err) {
      alert("Error connecting to server. Make sure backend is running.");
    }
    setLoading(false);
  };

  // Short reference sent instead of the patient's name (data minimisation, Act 843)
  const patientRef = (id) => "HC-" + String(id).slice(-6);

  const handleSendSMS = async (patientId) => {
    const patient = patients.find((p) => p.id === patientId);
    if (!patient) return;
    try {
      const response = await fetch("http://127.0.0.1:8000/send-sms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_ref: patientRef(patient.id),
          age: patient.age,
          risk_level: patient.risk_level,
          chw_name: chw.name,
          facility: chw.facility,
          facility_phone: chw.facilityPhone,
        }),
      });
      const data = await response.json();
      if (data.success) {
        setPatients((prev) =>
          prev.map((p) => (p.id === patientId ? { ...p, smsSent: true } : p))
        );
        if (result?.id === patientId) {
          setResult((prev) => ({ ...prev, smsSent: true }));
        }
      }
    } catch (err) {
      alert("SMS failed. Check your connection.");
    }
  };

  const riskColor = {
    HIGH: "bg-red-50 border-red-400 text-red-700",
    MEDIUM: "bg-yellow-50 border-yellow-400 text-yellow-700",
    LOW: "bg-green-50 border-green-400 text-green-700",
  };

  const riskBadge = {
    HIGH: "bg-red-500 text-white",
    MEDIUM: "bg-yellow-500 text-white",
    LOW: "bg-green-500 text-white",
  };

  const riskIcon = {
    HIGH: "🚨",
    MEDIUM: "⚠️",
    LOW: "✅",
  };

  if (!chw) {
    return <Login onLogin={setChw} lang={lang} setLang={setLang} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 p-4">
      <div className="max-w-md mx-auto">

        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-xl font-bold text-green-700">🤱 {t.title}</h1>
            <p className="text-xs text-gray-500">👤 {chw.name} · {chw.facility}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setLang(lang === "en" ? "tw" : "en")}
              className="bg-green-600 text-white px-2 py-1 rounded-full text-xs font-medium"
            >
              {lang === "en" ? "🇬🇭 Twi" : "🇬🇧 EN"}
            </button>
            <button
              onClick={() => setChw(null)}
              className="bg-gray-200 text-gray-600 px-2 py-1 rounded-full text-xs font-medium"
            >
              {t.logout}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setView("assess")}
            className={`flex-1 py-2 rounded-xl text-sm font-semibold transition ${view === "assess" ? "bg-green-600 text-white shadow-md" : "bg-white text-gray-600"
              }`}
          >
            ➕ {t.assess}
          </button>
          <button
            onClick={() => setView("dashboard")}
            className={`flex-1 py-2 rounded-xl text-sm font-semibold transition ${view === "dashboard" ? "bg-green-600 text-white shadow-md" : "bg-white text-gray-600"
              }`}
          >
            📊 {t.dashboard}
          </button>
        </div>

        {/* Online/Offline Badge */}
        <div className={`rounded-lg p-2 mb-4 flex items-center gap-2 ${isOnline ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}>
          <span className={`text-sm font-medium ${isOnline ? "text-green-600" : "text-red-600"}`}>
            {isOnline ? "🟢 Online" : "🔴 Offline — Data saved locally"}
          </span>
        </div>

        {/* Assessment View */}
        {view === "assess" && (
          <>
            <div className="bg-white rounded-2xl shadow-md p-5 space-y-4">
              {/* Section Header */}
              <div className="border-b border-gray-100 pb-2">
                <h2 className="text-sm font-bold text-gray-600 uppercase tracking-wide">
                  🧾 {t.patientInfo}
                </h2>
              </div>

              {/* Patient Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t.patientName}</label>
                <input
                  type="text"
                  name="name"
                  value={form.name}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  placeholder="e.g. Abena Mensah"
                />
              </div>

              {/* Age & Gestational Age */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t.age}</label>
                  <input
                    type="number"
                    name="age"
                    value={form.age}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t.gestational_age}</label>
                  <input
                    type="number"
                    name="gestational_age"
                    value={form.gestational_age}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  />
                </div>
              </div>

              {/* BP Fields Side by Side */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Blood Pressure (mmHg)</label>
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="number"
                    name="systolic_bp"
                    value={form.systolic_bp}
                    onChange={handleChange}
                    placeholder={t.systolic_bp}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  />
                  <input
                    type="number"
                    name="diastolic_bp"
                    value={form.diastolic_bp}
                    onChange={handleChange}
                    placeholder={t.diastolic_bp}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  />
                </div>
              </div>

              {/* Weight & Hemoglobin */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t.weight}</label>
                  <input
                    type="number"
                    name="weight"
                    value={form.weight}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t.hemoglobin}</label>
                  <input
                    type="number"
                    name="hemoglobin"
                    value={form.hemoglobin}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                  />
                </div>
              </div>


              {/* Body Temp & Heart Rate */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Body Temp (°F)</label>
                  <input
                    type="number"
                    name="body_temp"
                    value={form.body_temp}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                    placeholder="e.g. 98.6"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Heart Rate (bpm)</label>
                  <input
                    type="number"
                    name="heart_rate"
                    value={form.heart_rate}
                    onChange={handleChange}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                    placeholder="e.g. 80"
                  />
                </div>
              </div>

              {/* Checkbox */}
              <div className="flex items-center gap-2 bg-gray-50 rounded-lg p-3">
                <input
                  type="checkbox"
                  name="previous_complications"
                  checked={form.previous_complications}
                  onChange={handleChange}
                  className="w-4 h-4 accent-green-600"
                />
                <label className="text-sm font-medium text-gray-700">{t.previous_complications}</label>
              </div>

              {/* Submit */}
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl transition shadow-md"
              >
                {loading ? `⏳ ${t.loading}` : `🔍 ${t.submit}`}
              </button>
            </div>

            {/* Result Card */}
            {result && (
              <div className={`mt-4 border-2 rounded-2xl p-4 ${riskColor[result.risk_level]}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl">{riskIcon[result.risk_level]}</span>
                  <h2 className="text-lg font-bold">{t.risk}: {result.risk_level}</h2>
                </div>
                <p className="text-xs mb-2">Ref: {patientRef(result.id)}</p>
                <p className="text-sm mb-3 leading-relaxed">{result.explanation}</p>
                {result.risk_level === "HIGH" && (
                  <button
                    onClick={() => handleSendSMS(result.id)}
                    disabled={result.smsSent}
                    className={`w-full font-semibold py-2 rounded-xl text-sm transition text-white ${result.smsSent ? "bg-gray-400 cursor-not-allowed" : "bg-red-600 hover:bg-red-700"
                      }`}
                  >
                    {result.smsSent ? t.smsSent : `📱 ${t.sendSMS}`}
                  </button>
                )}
              </div>
            )}
          </>
        )}

        {/* Dashboard View */}
        {view === "dashboard" && (
          <div className="space-y-3">
            {/* Stats */}
            <div className="grid grid-cols-4 gap-2 mb-2">
              <div className="bg-white rounded-xl p-3 text-center shadow-sm">
                <div className="text-lg font-bold text-blue-600">{patients.length}</div>
                <div className="text-xs text-gray-500">{t.total}</div>
              </div>
              {["HIGH", "MEDIUM", "LOW"].map((level) => (
                <div key={level} className="bg-white rounded-xl p-3 text-center shadow-sm">
                  <div className={`text-lg font-bold ${level === "HIGH" ? "text-red-600" :
                    level === "MEDIUM" ? "text-yellow-600" : "text-green-600"
                    }`}>
                    {patients.filter((p) => p.risk_level === level).length}
                  </div>
                  <div className="text-xs text-gray-500">{level}</div>
                </div>
              ))}
            </div>

            {/* Patient List */}
            {patients.length === 0 ? (
              <div className="bg-white rounded-2xl p-10 text-center shadow-sm">
                <div className="text-5xl mb-3">🤱</div>
                <p className="text-gray-400 text-sm whitespace-pre-line">{t.noPatients}</p>
              </div>
            ) : (
              patients.map((p) => (
                <div key={p.id} className="bg-white rounded-xl shadow-sm p-4 flex items-center justify-between border-l-4 border-l-transparent"
                  style={{ borderLeftColor: p.risk_level === "HIGH" ? "#ef4444" : p.risk_level === "MEDIUM" ? "#eab308" : "#22c55e" }}
                >
                  <div>
                    <p className="font-semibold text-gray-800 text-sm">{p.name}</p>
                    <p className="text-xs text-gray-400">{patientRef(p.id)} · Age {p.age} · {p.time}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {p.risk_level === "HIGH" && !p.smsSent && (
                      <button
                        onClick={() => handleSendSMS(p.id)}
                        className="text-xs bg-red-100 text-red-600 px-2 py-1 rounded-lg font-medium"
                      >
                        📱 SMS
                      </button>
                    )}
                    {p.smsSent && (
                      <span className="text-xs text-gray-400">✅ Sent</span>
                    )}
                    <span className={`text-xs px-2 py-1 rounded-full font-semibold ${riskBadge[p.risk_level]}`}>
                      {riskIcon[p.risk_level]} {p.risk_level}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}