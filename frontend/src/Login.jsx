export default function Login({ onLogin, lang, setLang }) {
  const text = {
    en: {
      title: "SafeArrive",
      subtitle: "Community Health Worker Portal",
      name: "Your Full Name",
      facility: "Health Facility Name",
      facilityPhone: "Facility Phone Number",
      login: "Start Assessment",
      phonePlaceholder: "e.g. 0244000000",
    },
    tw: {
      title: "SafeArrive",
      subtitle: "Omunisantahyɛ Adwumayɛfo Portal",
      name: "Wo Din Nyinaa",
      facility: "Ayarehɔ Din",
      facilityPhone: "Ayarehɔ Telefon Nɔma",
      login: "Hyɛ Ase",
      phonePlaceholder: "e.g. 0244000000",
    },
  };

  const t = text[lang];

  const handleSubmit = (e) => {
    e.preventDefault();
    const name = e.target.name.value.trim();
    const facility = e.target.facility.value.trim();
    const facilityPhone = e.target.facilityPhone.value.trim();
    if (name && facility && facilityPhone) {
      onLogin({ name, facility, facilityPhone });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🤱</div>
          <h1 className="text-3xl font-bold text-green-700">{t.title}</h1>
          <p className="text-gray-500 text-sm mt-1">{t.subtitle}</p>
        </div>

        {/* Form */}
        <div className="bg-white rounded-2xl shadow-md p-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t.name}
              </label>
              <input
                name="name"
                type="text"
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                placeholder="e.g. Akosua Mensah"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t.facility}
              </label>
              <input
                name="facility"
                type="text"
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                placeholder="e.g. Korle Bu Health Centre"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t.facilityPhone}
              </label>
              <input
                name="facilityPhone"
                type="tel"
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                placeholder={t.phonePlaceholder}
              />
            </div>
            <button
              type="submit"
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl transition"
            >
              {t.login}
            </button>
          </form>
        </div>

        {/* Language Toggle */}
        <div className="text-center mt-4">
          <button
            onClick={() => setLang(lang === "en" ? "tw" : "en")}
            className="bg-green-600 text-white px-4 py-2 rounded-full text-sm font-medium"
          >
            {lang === "en" ? "🇬🇭 Twi" : "🇬🇧 English"}
          </button>
        </div>
      </div>
    </div>
  );
}