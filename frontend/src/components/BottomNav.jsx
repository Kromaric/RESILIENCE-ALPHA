import { Home, List, QrCode } from 'lucide-react';
import { useApp } from '../context/useApp';

/**
 * Bottom navigation bar with 3 tabs:
 * - Accueil (Home)
 * - Activité (Activity)
 * - Recevoir (Receive)
 * No emojis used.
 */
export default function BottomNav() {
  const { activeTab, navigateToTab } = useApp();

  const tabs = [
    { id: 'home', label: 'Accueil', icon: Home },
    { id: 'activity', label: 'Activité', icon: List },
    { id: 'receive', label: 'Recevoir', icon: QrCode },
  ];

  return (
    <nav className="min-h-[64px] bg-white border-t border-[#d5dcdf] grid grid-cols-3 items-center select-none z-10 shrink-0">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => navigateToTab(tab.id)}
            className={`flex flex-col items-center justify-center gap-1 py-1 transition-colors cursor-pointer ${
              isActive
                ? 'text-[#0e5a6b] font-semibold'
                : 'text-[#55636a] font-medium hover:text-[#0f1a1d]'
            }`}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon className={`w-5 h-5 ${isActive ? 'stroke-[2.5]' : 'stroke-2'}`} />
            <span className="text-[12px] leading-tight">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
