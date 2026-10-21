import { useState } from 'react';
import { ArrowLeft, UserPlus, AlertCircle, CheckCircle, ShieldCheck } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';
import { registerUser, loginWithPassword } from '../services/api';

/**
 * Screen: User Registration Screen.
 * Allows creating a new bank client account with email, phone, display name and password.
 * After successful registration, automatically logs in and transitions to biometric enrollment.
 * No emojis used.
 */
export default function RegisterScreen() {
  const { setCurrentScreen, setAuthToken, setSessionId, setPending2FA, syncBackendData } = useApp();

  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('+33');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    if (!displayName.trim()) {
      setErrorMessage('Veuillez renseigner votre nom complet.');
      return;
    }
    if (!email.trim() || !email.includes('@')) {
      setErrorMessage('Veuillez renseigner une adresse email valide.');
      return;
    }
    if (!phone.trim() || phone.length < 8) {
      setErrorMessage('Veuillez renseigner un numéro de téléphone valide.');
      return;
    }
    if (!password || password.length < 8) {
      setErrorMessage('Le mot de passe doit contenir au moins 8 caractères.');
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage('Les mots de passe ne correspondent pas.');
      return;
    }

    setIsLoading(true);
    try {
      await registerUser({
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        display_name: displayName.trim(),
        password,
      });

      setSuccessMessage('Compte créé avec succès ! Connexion automatique...');

      // Auto login with the newly created account to get session / token for biometric enrollment
      try {
        const loginRes = await loginWithPassword(email.trim().toLowerCase(), password);
        const token = loginRes.token?.access_token || 'demo-token';
        setAuthToken(token);
        setSessionId(loginRes.session_id);
        setPending2FA(null);

        if (token) {
          syncBackendData(token);
        }

        // Delay for visual confirmation before transitioning to face enrollment
        setTimeout(() => {
          setCurrentScreen('FACE_ENROLL');
        }, 900);
      } catch (loginErr) {
        console.warn('Auto-login error after registration:', loginErr);
        // If login failed for some reason, prompt user to log in
        setErrorMessage('Compte créé, mais échec de la connexion automatique. Veuillez vous connecter.');
        setIsLoading(false);
      }
    } catch (err) {
      setIsLoading(false);
      setSuccessMessage('');
      if (err.code === 'email_taken') {
        setErrorMessage('Cette adresse email est déjà utilisée.');
      } else if (err.code === 'phone_taken') {
        setErrorMessage('Ce numéro de téléphone est déjà utilisé.');
      } else if (err.code === 'weak_password') {
        setErrorMessage(err.message || 'Mot de passe trop simple ou trop courant.');
      } else {
        setErrorMessage(err.message || "Erreur lors de la création du compte.");
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between overflow-y-auto no-scrollbar pb-6 select-none">
      {/* Top Header */}
      <div>
        <Header />

        <div className="px-5 pt-2 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setCurrentScreen('LOGIN')}
            className="p-1 -ml-1 text-[#0f1a1d] hover:text-[#0e5a6b] rounded-lg transition-colors cursor-pointer inline-flex items-center gap-1 text-xs text-[#55636a]"
            aria-label="Retour"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Connexion</span>
          </button>

          <span className="bg-[#dcecef] text-[#0a4552] rounded-full px-2.5 py-0.5 text-xs font-semibold inline-flex items-center gap-1 shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5" />
            Inscription sécurisée
          </span>
        </div>

        <div className="px-6 pt-3 pb-2 text-center">
          <h2 className="text-[17px] font-semibold text-[#0f1a1d] tracking-tight">
            Créer un compte orbe
          </h2>
          <p className="text-xs text-[#55636a] mt-1">
            Renseignez vos coordonnées puis enregistrez votre visage
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 mt-2 space-y-3">
          {errorMessage && (
            <div className="bg-[#ffdad6] text-[#93000a] text-xs p-3 rounded-xl flex items-start gap-2 shadow-xs">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="bg-[#d4edd9] text-[#13532a] text-xs p-3 rounded-xl flex items-start gap-2 shadow-xs">
              <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          <div>
            <label className="block text-[11px] font-semibold text-[#293538] uppercase tracking-wider mb-1">
              Nom complet
            </label>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="ex: Alex Dupont"
              className="w-full h-10 px-3 rounded-xl border border-[#b8c9cd] bg-white text-xs text-[#0f1a1d] placeholder:text-[#839396] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#293538] uppercase tracking-wider mb-1">
              Adresse email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ex: alex@orbe.test"
              className="w-full h-10 px-3 rounded-xl border border-[#b8c9cd] bg-white text-xs text-[#0f1a1d] placeholder:text-[#839396] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#293538] uppercase tracking-wider mb-1">
              Numéro de téléphone
            </label>
            <input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+33 6 12 34 56 78"
              className="w-full h-10 px-3 rounded-xl border border-[#b8c9cd] bg-white text-xs text-[#0f1a1d] placeholder:text-[#839396] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#293538] uppercase tracking-wider mb-1">
              Mot de passe (8 caractères minimum)
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full h-10 px-3 rounded-xl border border-[#b8c9cd] bg-white text-xs text-[#0f1a1d] placeholder:text-[#839396] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#293538] uppercase tracking-wider mb-1">
              Confirmer le mot de passe
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full h-10 px-3 rounded-xl border border-[#b8c9cd] bg-white text-xs text-[#0f1a1d] placeholder:text-[#839396] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b]"
            />
          </div>

          <div className="pt-1 text-[11px] text-[#55636a] leading-relaxed">
            En créant votre compte, vous serez invité à capturer votre empreinte faciale pour sécuriser vos connexions et paiements.
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full h-11 mt-2 rounded-xl bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-xs disabled:opacity-50"
          >
            <UserPlus className="w-4 h-4" />
            <span>{isLoading ? 'Création en cours...' : 'Créer mon compte'}</span>
          </button>
        </form>
      </div>

      {/* Footer Switch to Login */}
      <div className="px-6 text-center mt-4">
        <button
          type="button"
          onClick={() => setCurrentScreen('LOGIN')}
          className="text-xs text-[#0e5a6b] font-medium hover:underline cursor-pointer"
        >
          Déjà un compte ? Se connecter
        </button>
      </div>
    </div>
  );
}
