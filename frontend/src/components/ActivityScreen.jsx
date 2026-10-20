import Header from './Header';
import { useApp } from '../context/useApp';

/**
 * Screen 6: Activity History.
 * Filterable by pills: Tout, Envoyés, Reçus, Demandes.
 * Chronological sections: Aujourd'hui, Hier, 15 octobre.
 * Includes failed transaction incident trace in red.
 * Amounts formatted with IBM Plex Mono and tabular-nums.
 * No emojis used.
 */
export default function ActivityScreen() {
  const { transactions, activityFilter, setActivityFilter } = useApp();

  const filterPills = [
    { id: 'all', label: 'Tout' },
    { id: 'sent', label: 'Envoyés' },
    { id: 'received', label: 'Reçus' },
    { id: 'requests', label: 'Demandes' },
  ];

  // Filter transactions based on selected pill
  const filteredTransactions = transactions.filter((tx) => {
    if (activityFilter === 'all') return true;
    if (activityFilter === 'sent') return tx.type === 'sent';
    if (activityFilter === 'received') return tx.type === 'received' || tx.type === 'refund';
    if (activityFilter === 'requests') return tx.type === 'request';
    return true;
  });

  // Group by chronological sections
  const sections = ["Aujourd'hui", 'Hier', '15 octobre'];
  const grouped = sections.reduce((acc, sectionName) => {
    acc[sectionName] = filteredTransactions.filter((tx) => tx.section === sectionName);
    return acc;
  }, {});

  return (
    <div className="flex-1 flex flex-col overflow-y-auto no-scrollbar">
      {/* Top Header */}
      <Header />

      <div className="px-5 py-3 flex flex-col gap-4">
        {/* Filter Pills Bar */}
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5 select-none">
          {filterPills.map((pill) => {
            const isActive = activityFilter === pill.id;
            return (
              <button
                key={pill.id}
                type="button"
                onClick={() => setActivityFilter(pill.id)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all cursor-pointer ${
                  isActive
                    ? 'bg-[#0e5a6b] text-white shadow-xs'
                    : 'bg-white border border-[#d5dcdf] text-[#55636a] hover:bg-[#f5f6f4] hover:text-[#0f1a1d]'
                }`}
              >
                {pill.label}
              </button>
            );
          })}
        </div>

        {/* Chronological List of Transactions */}
        <div className="flex flex-col gap-4">
          {sections.map((sectionName) => {
            const items = grouped[sectionName] || [];
            if (items.length === 0) return null;

            return (
              <div key={sectionName} className="flex flex-col gap-2">
                {/* Section Header */}
                <h3 className="text-xs font-semibold text-[#55636a] uppercase tracking-wider px-1">
                  {sectionName}
                </h3>

                {/* Section Card */}
                <div className="bg-white border border-[#d5dcdf] rounded-xl overflow-hidden divide-y divide-[#d5dcdf] shadow-xs">
                  {items.map((tx) => {
                    const isFailed = tx.isFailed || tx.status === 'Échec';

                    return (
                      <div
                        key={tx.id}
                        className={`p-3.5 flex items-center justify-between gap-3 text-sm transition-colors ${
                          isFailed ? 'bg-[#fff8f8]' : 'hover:bg-[#fafaf9]'
                        }`}
                      >
                        {/* Counterparty avatar and subtitle */}
                        <div className="flex items-center gap-3 min-w-0">
                          <div
                            className={`w-9 h-9 rounded-full font-semibold text-xs flex items-center justify-center shrink-0 ${
                              isFailed
                                ? 'bg-[#fde8e8] text-[#c81e1e]'
                                : 'bg-[#dcecef] text-[#0a4552]'
                            }`}
                          >
                            {tx.initials}
                          </div>
                          <div className="flex flex-col min-w-0">
                            <span className="font-semibold text-[#0f1a1d] truncate">
                              {tx.counterparty}
                            </span>
                            <span className="text-xs text-[#55636a] truncate">
                              {tx.subtitle}
                            </span>
                          </div>
                        </div>

                        {/* Amount & Status */}
                        <div className="text-right shrink-0">
                          <div
                            className={`font-mono font-medium text-[14px] tabular-nums ${
                              isFailed ? 'text-[#c81e1e]' : 'text-[#0f1a1d]'
                            }`}
                          >
                            {tx.amountFormatted}
                          </div>

                          <div className="text-[11px] font-medium flex items-center justify-end gap-1 mt-0.5">
                            {isFailed ? (
                              <span className="text-[#c81e1e] font-semibold inline-flex items-center gap-1">
                                <span aria-hidden="true">■</span> {tx.status}
                              </span>
                            ) : tx.status === 'Remboursé' ? (
                              <span className="text-[#55636a] inline-flex items-center gap-1">
                                <span aria-hidden="true">◇</span> {tx.status}
                              </span>
                            ) : (
                              <span
                                className={`inline-flex items-center gap-1 ${
                                  tx.type === 'received'
                                    ? 'text-[#1e7a45]'
                                    : tx.type === 'request'
                                    ? 'text-[#0e5a6b]'
                                    : 'text-[#55636a]'
                                }`}
                              >
                                <span aria-hidden="true">●</span> {tx.status}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {filteredTransactions.length === 0 && (
            <div className="bg-white border border-[#d5dcdf] rounded-xl p-8 text-center text-xs text-[#55636a] shadow-xs">
              Aucune transaction pour ce filtre.
            </div>
          )}
        </div>

        {/* Footer Note */}
        <div className="text-center py-3 select-none">
          <p className="text-xs text-[#55636a]">Données fictives de démonstration</p>
        </div>
      </div>
    </div>
  );
}
