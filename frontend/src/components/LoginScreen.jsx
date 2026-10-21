import { useState } from 'react';
import { LogIn, UserPlus, AlertCircle, CheckCircle } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';

/**
 * Screen 1: User Login Screen.
 * Allows user to log in with email and password to any registered account.
 * Leads to Biometric 2FA (FACE_AUTH) or Biometric Enrollment (FACE_ENROLL) depending on account state.
 * No emojis used.
 */
export default function LoginScreen() {
  const { start2FALogin, setCurrentScreen, loginNotice, setLoginNotice, prefilledEmail } = useApp();

  const [email, setEmail] = useState(() => prefilledEmail || '');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');



  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    if (setLoginNotice) {
      setLoginNotice('');
    }

    if (!email.trim() || !password) {
      setErrorMessage('Veuillez saisir votre email et votre mot de passe.');
      return;
    }

    setIsLoading(true);
    try {
      await start2FALogin(email.trim().toLowerCase(), password);
    } catch (err) {
      setIsLoading(false);
      if (err.code === 'invalid_credentials') {
        setErrorMessage('Email ou mot de passe incorrect.');
      } else if (err.code === 'account_locked') {
        setErrorMessage('Compte temporairement bloqué après trop de tentatives.');
      } else {
        setErrorMessage(err.message || 'Erreur lors de la connexion.');
      }
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between overflow-y-auto no-scrollbar pb-6 select-none">
      {/* Top Header */}
      <div>
        <Header />

        <div className="px-6 pt-3 text-center">
          <div className="w-14 h-14 mx-auto rounded-full bg-[#dcecef] text-[#0a4552] flex items-center justify-center shadow-xs mb-3">
            <LogIn className="w-6 h-6 stroke-[2]" />
          </div>
          <h2 className="text-[22px] font-semibold text-[#0f1a1d] tracking-tight">
            Connexion à Orbe
          </h2>
          <p className="text-xs text-[#55636a] mt-1">
            Saisissez vos identifiants pour accéder à votre compte.
          </p>
        </div>

        {/* Notice after registration */}
        {loginNotice && (
          <div className="mx-6 mt-3 p-3 rounded-xl bg-[#def2e5] border border-[#a3e0b6] text-[#1e7a45] text-xs flex items-center gap-2 shadow-2xs">
            <CheckCircle className="w-4 h-4 shrink-0 text-[#1e7a45]" />
            <span>{loginNotice}</span>
          </div>
        )}

        {/* Error Feedback */}
        {errorMessage && (
          <div className="mx-6 mt-3 p-2.5 rounded-xl bg-[#fde8e8] border border-[#f8b4b4] text-[#c81e1e] text-xs flex items-center gap-2 shadow-2xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="px-6 mt-3 flex flex-col gap-3">
          <div>
            <label className="block text-xs font-semibold text-[#0f1a1d] mb-1">
              Adresse email
            </label>
            <input
              type="email"
              required
              placeholder="votre-email@orbe.test"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (loginNotice && setLoginNotice) setLoginNotice('');
              }}
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] placeholder-[#9aa5aa] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] transition-all shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0f1a1d] mb-1">
              Mot de passe
            </label>
            <input
              type="password"
              required
              placeholder="Votre mot de passe"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] placeholder-[#9aa5aa] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] transition-all shadow-2xs"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full h-11 mt-1 rounded-xl bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-xs disabled:opacity-50"
          >
            <LogIn className="w-4 h-4" />
            <span>{isLoading ? 'Connexion...' : 'Se connecter'}</span>
          </button>
        </form>
      </div>

      {/* Footer Switch to Register */}
      <div className="px-6 text-center mt-6 flex flex-col gap-2">
        <div className="flex items-center justify-center gap-2 text-xs">
          <span className="text-[#55636a]">Nouveau sur Orbe ?</span>
          <button
            type="button"
            onClick={() => {
              if (setLoginNotice) setLoginNotice('');
              setCurrentScreen('REGISTER');
            }}
            className="text-[#0e5a6b] font-semibold hover:underline cursor-pointer inline-flex items-center gap-1"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Créer un compte</span>
          </button>
        </div>
        <p className="text-[11px] text-[#55636a] leading-tight">
          Après votre mot de passe, votre identité est confirmée par reconnaissance faciale.
        </p>
      </div>
    </div>
  );
}
