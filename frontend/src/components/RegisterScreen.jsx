import { useState } from 'react';
import { ArrowLeft, UserPlus, CheckCircle2, AlertCircle } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';
import { registerUser, loginWithPassword } from '../services/api';

/**
 * Screen: User Registration.
 * Allows creating a new customer account (name, email, phone, password),
 * then automatically initiates login to immediately proceed to facial biometric enrollment (RGPD Art. 9).
 * No emojis used.
 */
export default function RegisterScreen() {
  const { setCurrentScreen, setAuthToken, setSessionId, syncBackendData } = useApp();

  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const handleRegister = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    // Basic frontend checks
    if (displayName.trim().length < 2) {
      setErrorMessage('Veuillez saisir votre nom complet (au moins 2 caractères).');
      return;
    }
    if (!email.includes('@') || !email.includes('.')) {
      setErrorMessage('Adresse email invalide.');
      return;
    }
    if (phone.trim().length < 8) {
      setErrorMessage('Numéro de téléphone invalide (au moins 8 chiffres).');
      return;
    }
    if (password.length < 12) {
      setErrorMessage('Le mot de passe doit comporter au moins 12 caractères.');
      return;
    }
    if (password !== passwordConfirm) {
      setErrorMessage('Les mots de passe ne correspondent pas.');
      return;
    }

    setIsLoading(true);

    try {
      // 1. Create account on auth-service /register
      await registerUser({
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        display_name: displayName.trim(),
        password,
      });

      setSuccessMessage('Compte créé avec succès ! Préparation de la biométrie...');

      // 2. Automatically log in to get access token for facial enrollment
      try {
        const loginRes = await loginWithPassword(email.trim().toLowerCase(), password);

        // Account just created has no face enrolled yet -> face_enrollment_required: true
        const token = loginRes.token?.access_token;
        if (token) {
          setAuthToken(token);
          setSessionId(loginRes.session_id);
          syncBackendData(token);
        }

        // Delay for visual confirmation before transitioning to face enrollment
        setTimeout(() => {
          setCurrentScreen('FACE_ENROLL');
        }, 900);
      } catch (loginErr) {
        console.warn('Auto-login error after registration:', loginErr);
        // If login failed for some reason, navigate to login PIN screen
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
            onClick={() => setCurrentScreen('PIN')}
            className="p-1 -ml-1 text-[#0f1a1d] hover:text-[#0e5a6b] rounded-lg transition-colors cursor-pointer inline-flex items-center gap-1 text-xs text-[#55636a]"
            aria-label="Retour"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Connexion</span>
          </button>

          <span className="bg-[#dcecef] text-[#0a4552] rounded-full px-2.5 py-0.5 text-xs font-semibold inline-flex items-center gap-1 shadow-2xs">
            <UserPlus className="w-3.5 h-3.5" />
            <span>Nouveau compte</span>
          </span>
        </div>

        {/* Title */}
        <div className="px-6 pt-3 text-center">
          <h2 className="text-[22px] font-semibold text-[#0f1a1d] tracking-tight">
            Créer un compte Orbe
          </h2>
          <p className="text-xs text-[#55636a] mt-1">
            Rejoignez Orbe et activez ensuite votre reconnaissance faciale.
          </p>
        </div>

        {/* Feedback messages */}
        {errorMessage && (
          <div className="mx-6 mt-3 p-2.5 rounded-xl bg-[#fde8e8] border border-[#f8b4b4] text-[#c81e1e] text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="mx-6 mt-3 p-2.5 rounded-xl bg-[#def2e5] border border-[#bbf0ce] text-[#1e7a45] text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Registration Form */}
        <form onSubmit={handleRegister} className="px-6 mt-4 flex flex-col gap-3">
          <div>
            <label className="block text-xs font-semibold text-[#0f1a1d] mb-1">
              Nom complet
            </label>
            <input
              type="text"
              required
              placeholder="ex: Alex Dupont"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] placeholder-[#9aa5aa] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] transition-all shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0f1a1d] mb-1">
              Adresse email
            </label>
            <input
              type="email"
              required
              placeholder="ex: alex@orbe.test"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] placeholder-[#9aa5aa] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] transition-all shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0f1a1d] mb-1">
              Numéro de téléphone
            </label>
            <input
              type="tel"
              required
              placeholder="ex: 06 12 34 56 70"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
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
              placeholder="12 caractères minimum"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] placeholder-[#9aa5aa] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] transition-all shadow-2xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#0f1a1d] mb-1">
              Confirmer le mot de passe
            </label>
            <input
              type="password"
              required
              placeholder="Répétez votre mot de passe"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              className="w-full h-11 px-3.5 rounded-xl bg-white border border-[#d5dcdf] text-sm text-[#0f1a1d] placeholder-[#9aa5aa] focus:outline-none focus:border-[#0e5a6b] focus:ring-1 focus:ring-[#0e5a6b] transition-all shadow-2xs"
            />
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
          onClick={() => setCurrentScreen('PIN')}
          className="text-xs text-[#0e5a6b] font-medium hover:underline cursor-pointer"
        >
          Déjà un compte ? Se connecter
        </button>
      </div>
    </div>
  );
}
