import { ArrowLeft } from 'lucide-react';
import { useApp } from '../context/useApp';

/**
 * Top application header component.
 * Displays screen title on the left and service status indicator on the right.
 * No emojis used.
 */
export default function Header({ showBack = false, onBack = null }) {
  const { currentScreen, isIncident, setCurrentScreen } = useApp();

  // Determine header title based on current screen
  let title = 'orbe';
  if (currentScreen === 'SEND_CONTACT') title = 'Envoyer';
  else if (currentScreen === 'VERIFY') title = 'Vérifier';
  else if (currentScreen === 'RECEIVE') title = 'Recevoir';
  else if (currentScreen === 'ACTIVITY') title = 'Activité';
  else if (currentScreen === 'HOME' || currentScreen === 'PIN') title = 'orbe';

  const isHomeOrPin = currentScreen === 'HOME' || currentScreen === 'PIN';

  const handleBackClick = () => {
    if (onBack) {
      onBack();
    } else if (currentScreen === 'VERIFY') {
      setCurrentScreen('SEND_CONTACT');
    } else if (currentScreen === 'SEND_CONTACT') {
      setCurrentScreen('HOME');
    }
  };

  return (
    <header className="px-5 pt-4 pb-2 flex items-center justify-between bg-transparent select-none">
      <div className="flex items-center gap-2">
        {showBack && (
          <button
            type="button"
            onClick={handleBackClick}
            className="p-1 -ml-1 text-[#0f1a1d] hover:text-[#0e5a6b] rounded-lg transition-colors cursor-pointer"
            aria-label="Retour"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        )}
        <h1
          className={
            isHomeOrPin
              ? 'text-[24px] font-semibold text-[#0e5a6b] tracking-tight'
              : 'text-[20px] font-semibold text-[#0f1a1d]'
          }
        >
          {title}
        </h1>
      </div>

      <div>
        {currentScreen === 'PIN' ? (
          <span className="bg-[#dcecef] text-[#0a4552] rounded px-2 py-0.5 text-xs font-medium">
            Démo
          </span>
        ) : isIncident ? (
          <span className="bg-[#3d1714] text-[#f47066] rounded-full px-2.5 py-0.5 text-xs font-medium inline-flex items-center gap-1.5 shadow-xs">
            <span aria-hidden="true">■</span> Incident
          </span>
        ) : (
          <span className="bg-[#1e7a45] text-white rounded-full px-2.5 py-0.5 text-xs font-medium inline-flex items-center gap-1.5 shadow-xs">
            <span aria-hidden="true">●</span> Opérationnel
          </span>
        )}
      </div>
    </header>
  );
}
