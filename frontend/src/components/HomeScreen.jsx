import { ArrowUpRight, ArrowDownLeft, QrCode } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';

/**
 * Screen 2: Home dashboard.
 * Displays greeting, linked bank account card, 3 primary quick action cards,
 * and recent 4 transactions summary with IBM Plex Mono font.
 * No emojis used.
 */
export default function HomeScreen() {
  const { setCurrentScreen, setReceiveSubTab, transactions, navigateToTab } = useApp();

  // Take the 4 most recent transactions matching specifications
  const recentTransactions = [
    transactions.find((t) => t.id === 'tx_1') || {
      initials: 'LM',
      counterparty: 'Léa Martin',
      subtitle: 'Ciné · 10:44',
      amountFormatted: '− 12,50 €',
      status: 'Envoyé',
    },
    transactions.find((t) => t.id === 'tx_3') || {
      initials: 'HB',
      counterparty: 'Hugo Bernard',
      subtitle: 'Pizza vendredi · 09:12',
      amountFormatted: '+ 25,00 €',
      status: 'Reçu',
    },
    transactions.find((t) => t.id === 'tx_5') || {
      initials: 'IP',
      counterparty: 'Inès Petit',
      subtitle: 'Cadeau Nathan · Hier',
      amountFormatted: '− 15,00 €',
      status: 'Envoyé',
    },
    transactions.find((t) => t.id === 'tx_6') || {
      initials: 'NM',
      counterparty: 'Nathan Moreau',
      subtitle: 'Covoiturage · Hier',
      amountFormatted: '+ 8,00 €',
      status: 'Reçu',
    },
  ];

  return (
    <div className="flex-1 flex flex-col overflow-y-auto no-scrollbar">
      {/* Top Header */}
      <Header />

      <div className="px-5 py-3 flex flex-col gap-4">
        {/* User Greeting */}
        <div>
          <p className="text-[#55636a] text-sm">Bonjour</p>
          <h1 className="text-2xl font-semibold text-[#0f1a1d] tracking-tight">
            Camille Test
          </h1>
        </div>

        {/* Linked Account Card */}
        <section
          aria-label="Compte lié"
          className="bg-[#0e5a6b] text-white rounded-xl p-5 flex flex-col gap-3 shadow-sm select-none"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider opacity-85 font-medium">
              Compte lié
            </span>
            <span className="bg-[#dcecef] text-[#0a4552] rounded px-1.5 py-0.5 text-xs font-medium">
              Banque Démo
            </span>
          </div>

          <div className="font-mono text-[15px] tracking-wider font-medium">
            FR76 •••• •••• 0142
          </div>

          <p className="text-[13px] opacity-85 leading-snug m-0">
            L'argent part de ce compte et arrive chez votre contact en quelques secondes.
          </p>
        </section>

        {/* 3 Action Buttons Grid */}
        <section aria-label="Actions rapides" className="grid grid-cols-3 gap-3">
          {/* Action 1: Envoyer */}
          <button
            type="button"
            onClick={() => setCurrentScreen('SEND_CONTACT')}
            className="bg-white border border-[#d5dcdf] rounded-xl p-3 flex flex-col items-center justify-center gap-2 hover:bg-[#fafaf9] active:scale-[0.98] transition-all shadow-xs cursor-pointer group"
          >
            <div className="w-11 h-11 rounded-full bg-[#0e5a6b] text-white flex items-center justify-center shadow-xs group-hover:bg-[#0a4552] transition-colors">
              <ArrowUpRight className="w-5 h-5 stroke-[2.5]" />
            </div>
            <span className="text-xs font-semibold text-[#0f1a1d]">Envoyer</span>
          </button>

          {/* Action 2: Demander */}
          <button
            type="button"
            onClick={() => {
              setReceiveSubTab('request');
              setCurrentScreen('RECEIVE');
            }}
            className="bg-white border border-[#d5dcdf] rounded-xl p-3 flex flex-col items-center justify-center gap-2 hover:bg-[#fafaf9] active:scale-[0.98] transition-all shadow-xs cursor-pointer group"
          >
            <div className="w-11 h-11 rounded-full bg-[#dcecef] text-[#0a4552] flex items-center justify-center shadow-xs group-hover:bg-[#c9e3e7] transition-colors">
              <ArrowDownLeft className="w-5 h-5 stroke-[2.5]" />
            </div>
            <span className="text-xs font-semibold text-[#0f1a1d]">Demander</span>
          </button>

          {/* Action 3: Mon QR */}
          <button
            type="button"
            onClick={() => {
              setReceiveSubTab('qr');
              setCurrentScreen('RECEIVE');
            }}
            className="bg-white border border-[#d5dcdf] rounded-xl p-3 flex flex-col items-center justify-center gap-2 hover:bg-[#fafaf9] active:scale-[0.98] transition-all shadow-xs cursor-pointer group"
          >
            <div className="w-11 h-11 rounded-full bg-[#dcecef] text-[#0a4552] flex items-center justify-center shadow-xs group-hover:bg-[#c9e3e7] transition-colors">
              <QrCode className="w-5 h-5 stroke-[2.5]" />
            </div>
            <span className="text-xs font-semibold text-[#0f1a1d]">Mon QR</span>
          </button>
        </section>

        {/* Recent Activity Card */}
        <section
          aria-label="Activité récente"
          className="bg-white border border-[#d5dcdf] rounded-xl p-4 shadow-sm flex flex-col gap-1"
        >
          <div className="flex items-center justify-between pb-3">
            <h2 className="text-lg font-semibold text-[#0f1a1d]">Activité récente</h2>
            <button
              type="button"
              onClick={() => navigateToTab('activity')}
              className="text-xs text-[#0e5a6b] font-medium hover:underline cursor-pointer"
            >
              Tout voir
            </button>
          </div>

          <div className="divide-y divide-[#d5dcdf]">
            {recentTransactions.map((tx, idx) => (
              <div
                key={`recent-${idx}`}
                className="py-2.5 flex items-center justify-between gap-3 text-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-full bg-[#dcecef] text-[#0a4552] font-semibold text-xs flex items-center justify-center shrink-0">
                    {tx.initials}
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="font-semibold text-[#0f1a1d] truncate">
                      {tx.counterparty}
                    </span>
                    <span className="text-xs text-[#55636a] truncate">{tx.subtitle}</span>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <div className="font-mono font-medium text-[14px] tabular-nums text-[#0f1a1d]">
                    {tx.amountFormatted}
                  </div>
                  <div className="text-[11px] text-[#55636a]">{tx.status}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
