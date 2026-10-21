import { ArrowUpRight, ArrowDownLeft, QrCode, LogOut } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';

/**
 * Screen 2: Home dashboard.
 * Displays greeting, linked bank account card, 3 primary quick action cards,
 * and recent 4 transactions summary with IBM Plex Mono font.
 * No emojis used.
 */
export default function HomeScreen() {
  const { user, setCurrentScreen, setReceiveSubTab, transactions, navigateToTab, handleLogout } = useApp();

  // Take the 4 most recent transactions
  const recentTransactions = transactions.slice(0, 4);

  return (
    <div className="flex-1 flex flex-col overflow-y-auto no-scrollbar">
      {/* Top Header */}
      <Header />

      <div className="px-5 py-3 flex flex-col gap-4">
        {/* User Greeting with Logout Option */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[#55636a] text-sm">Bonjour</p>
            <h1 className="text-2xl font-semibold text-[#0f1a1d] tracking-tight">
              {user?.name || 'Mon Compte'}
            </h1>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            title="Se déconnecter"
            className="p-2 rounded-xl text-[#55636a] hover:text-[#c81e1e] hover:bg-[#fde8e8] transition-colors cursor-pointer"
            aria-label="Déconnexion"
          >
            <LogOut className="w-5 h-5 stroke-[1.75]" />
          </button>
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
              {user?.bankLabel || 'Compte Orbe'}
            </span>
          </div>

          <div className="font-mono text-[15px] tracking-wider font-medium">
            {user?.accountMasked || 'FR76 •••• •••• 0142'}
          </div>

          <p className="text-[13px] opacity-85 leading-snug m-0">
            L&apos;argent part de ce compte et arrive chez votre contact en quelques secondes.
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
              <ArrowUpRight className="w-5 h-5 stroke-[2.5] stroke-current" />
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
            <div className="w-11 h-11 rounded-full bg-[#0e5a6b] text-white flex items-center justify-center shadow-xs group-hover:bg-[#0a4552] transition-colors">
              <ArrowDownLeft className="w-5 h-5 stroke-[2.5] stroke-current" />
            </div>
            <span className="text-xs font-semibold text-[#0f1a1d]">Demander</span>
          </button>

          {/* Action 3: QR Code */}
          <button
            type="button"
            onClick={() => {
              setReceiveSubTab('qr');
              setCurrentScreen('RECEIVE');
            }}
            className="bg-white border border-[#d5dcdf] rounded-xl p-3 flex flex-col items-center justify-center gap-2 hover:bg-[#fafaf9] active:scale-[0.98] transition-all shadow-xs cursor-pointer group"
          >
            <div className="w-11 h-11 rounded-full bg-[#0e5a6b] text-white flex items-center justify-center shadow-xs group-hover:bg-[#0a4552] transition-colors">
              <QrCode className="w-5 h-5 stroke-[2.5] stroke-current" />
            </div>
            <span className="text-xs font-semibold text-[#0f1a1d]">Mon QR</span>
          </button>
        </section>

        {/* Recent Activity Section */}
        <section aria-label="Activité récente" className="mt-1 flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#0f1a1d] tracking-tight m-0">
              Activité récente
            </h2>
            <button
              type="button"
              onClick={() => navigateToTab('activity')}
              className="text-xs text-[#0e5a6b] font-medium hover:underline cursor-pointer"
            >
              Tout voir
            </button>
          </div>

          <div className="flex flex-col gap-2">
            {recentTransactions.length > 0 ? (
              recentTransactions.map((tx) => (
                <div
                  key={tx.id}
                  className="bg-white border border-[#d5dcdf] rounded-xl p-3.5 flex items-center justify-between shadow-2xs hover:border-[#7f8c93] transition-colors select-none"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-full bg-[#dcecef] text-[#0a4552] font-semibold text-xs flex items-center justify-center shrink-0">
                      {tx.initials}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-[#0f1a1d] truncate m-0 text-sm">
                        {tx.counterparty}
                      </p>
                      <p className="text-xs text-[#55636a] truncate m-0 mt-0.5">
                        {tx.subtitle}
                      </p>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <p
                      className={`font-mono font-medium text-sm m-0 ${
                        tx.isFailed
                          ? 'text-[#55636a]'
                          : tx.type === 'received'
                          ? 'text-[#1e7a45]'
                          : 'text-[#0f1a1d]'
                      }`}
                    >
                      {tx.amountFormatted}
                    </p>
                    <p className="text-[11px] text-[#55636a] m-0 mt-0.5">
                      <span aria-hidden="true">{tx.statusSymbol}</span> {tx.status}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <div className="bg-white border border-[#d5dcdf] rounded-xl p-5 text-center text-xs text-[#55636a] shadow-2xs">
                Aucune transaction pour le moment.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
