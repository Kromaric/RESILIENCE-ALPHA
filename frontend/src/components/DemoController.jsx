import { SlidersHorizontal, RefreshCw } from 'lucide-react';
import { useApp } from '../context/useApp';

/**
 * Floating controller placed outside the mobile container.
 * Allows switching between Operational and Incident modes for demo resilience showcases.
 * Maintains real-time backend health awareness with reset to automatic polling.
 * No emojis used.
 */
export default function DemoController() {
  const {
    isIncident,
    manualOverride,
    autoHealthStatus,
    isCheckingHealth,
    toggleIncidentMode,
    resetToAutoDetection,
    pollHealth,
  } = useApp();

  return (
    <aside
      aria-label="Contrôles de démonstration de résilience"
      className="fixed bottom-4 right-4 z-50 bg-white border border-[#d5dcdf] rounded-2xl p-3.5 shadow-lg max-w-[280px] text-xs flex flex-col gap-2.5 select-none"
    >
      <div className="flex items-center justify-between gap-2 border-b border-[#d5dcdf] pb-2">
        <div className="flex items-center gap-1.5 font-semibold text-[#0f1a1d]">
          <SlidersHorizontal className="w-3.5 h-3.5 text-[#0e5a6b]" />
          <span>Démo Résilience</span>
        </div>
        <button
          type="button"
          onClick={pollHealth}
          disabled={isCheckingHealth}
          title="Vérifier l'état de l'API"
          className="p-1 rounded-md text-[#55636a] hover:text-[#0e5a6b] hover:bg-[#f5f6f4] transition-colors cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isCheckingHealth ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="flex flex-col gap-1 text-[#55636a]">
        <div className="flex items-center justify-between">
          <span>État actuel :</span>
          {isIncident ? (
            <span className="bg-[#3d1714] text-[#f47066] font-medium px-2 py-0.5 rounded-full inline-flex items-center gap-1">
              <span aria-hidden="true">■</span> Incident
            </span>
          ) : (
            <span className="bg-[#1e7a45] text-white font-medium px-2 py-0.5 rounded-full inline-flex items-center gap-1">
              <span aria-hidden="true">●</span> Opérationnel
            </span>
          )}
        </div>

        <div className="flex items-center justify-between text-[11px]">
          <span>Sonde API backend :</span>
          <span className="font-mono text-[#0f1a1d]">
            {autoHealthStatus === 'operational' ? '200 OK' : 'Indisponible'}
          </span>
        </div>

        {manualOverride !== null && (
          <div className="flex items-center justify-between text-[11px] text-[#0e5a6b] font-medium">
            <span>Mode forcé manuel</span>
            <button
              type="button"
              onClick={resetToAutoDetection}
              className="underline hover:text-[#0a4552] cursor-pointer"
            >
              Rétablir auto
            </button>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={toggleIncidentMode}
        className={`w-full py-2 px-3 rounded-xl font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-xs cursor-pointer ${
          isIncident
            ? 'bg-[#1e7a45] hover:bg-[#165c34] text-white'
            : 'bg-[#b42318] hover:bg-[#911c13] text-white'
        }`}
      >
        <span>
          {isIncident ? 'Simuler : Mode Opérationnel' : 'Simuler : Mode Incident'}
        </span>
      </button>
    </aside>
  );
}
