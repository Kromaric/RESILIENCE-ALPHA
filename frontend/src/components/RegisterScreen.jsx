import { useState } from 'react';
import { ArrowLeft, UserPlus, AlertCircle, ShieldCheck } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';
import { registerUser } from '../services/api';

/**
 * Screen: User Registration Screen.
 * Allows creating a new bank client account with email, phone, display name and password.
 * After successful registration, automatically redirects to login screen.
 * No emojis used.
 */
export default function RegisterScreen() {
  const { setCurrentScreen, setLoginNotice, setPrefilledEmail } = useApp();

  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('+33');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

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
      const normalizedEmail = email.trim().toLowerCase();
      const trimmedPhone = phone.trim();
      const trimmedName = displayName.trim();

      await registerUser({
        email: normalizedEmail,
        phone: trimmedPhone,
        display_name: trimmedName,
        password,
      });

      if (setLoginNotice) {
        setLoginNotice('Compte créé avec succès ! Connectez-vous avec vos identifiants.');
      }
      if (setPrefilledEmail) {
        setPrefilledEmail(normalizedEmail);
      }
      setCurrentScreen('LOGIN');
    } catch (err) {
      setIsLoading(false);
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
            Renseignez vos coordonnées pour créer votre compte
          </p>
        </div>

        {/* Status / Error Banner */}
        {errorMessage && (
          <div className="px-6 pt-2">
            <div className="p-3 rounded-xl bg-[#ffdad6] text-[#93000a] text-xs flex items-start gap-2 shadow-xs mb-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-[#ba1a1a]" />
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        {/* Registration Form */}
        <form id="register-form" onSubmit={handleSubmit} className="px-6 space-y-3.5 pt-1">
          <div>
            <label className="block text-[11px] font-semibold text-[#55636a] uppercase tracking-wider mb-1">
              Nom complet
            </label>
            <input
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="ex. Alex Dupont"
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#55636a] uppercase tracking-wider mb-1">
              Adresse email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex.dupont@orbe.test"
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#55636a] uppercase tracking-wider mb-1">
              Numéro de téléphone
            </label>
            <input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+33 6 12 34 56 78"
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#55636a] uppercase tracking-wider mb-1">
              Mot de passe (8 caractères minimum)
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#55636a] uppercase tracking-wider mb-1">
              Confirmer le mot de passe
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••••••"
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] shadow-2xs"
            />
          </div>
        </form>
      </div>

      {/* Action Buttons */}
      <div className="px-6 pt-4 space-y-2.5">
        <button
          form="register-form"
          type="submit"
          disabled={isLoading}
          className="w-full h-11 rounded-xl bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-xs disabled:opacity-50"
        >
          <UserPlus className="w-4 h-4" />
          <span>{isLoading ? 'Création en cours...' : 'Créer mon compte'}</span>
        </button>

        <p className="text-center text-xs text-[#55636a]">
          Déjà un compte ?{' '}
          <button
            type="button"
            onClick={() => setCurrentScreen('LOGIN')}
            className="text-[#0e5a6b] font-semibold hover:underline cursor-pointer"
          >
            Se connecter
          </button>
        </p>
      </div>
    </div>
  );
}
