import { useState } from 'react';
import { Share2, ScanLine } from 'lucide-react';
import Header from './Header';
import QrCodeSvg from './QrCodeSvg';
import { useApp } from '../context/useApp';

/**
 * Screen 5: Receive money.
 * Segmented control with 2 tabs:
 * 1) Mon QR: vector SVG QR code with share and scan actions
 * 2) Demander: payment request form
 * No emojis used.
 */
export default function ReceiveScreen() {
  const { receiveSubTab, setReceiveSubTab, user, contacts, executeCreateRequest } = useApp();

  // State for "Demander" form
  const [selectedPayerId, setSelectedPayerId] = useState(contacts[0]?.id || '1');
  const [requestAmount, setRequestAmount] = useState('15,00');
  const [requestReason, setRequestReason] = useState('Courses');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const selectedPayer = contacts.find((c) => c.id === selectedPayerId) || contacts[0];

  const handleRequestSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    try {
      setIsSubmitting(true);
      await executeCreateRequest({
        payer: selectedPayer,
        amount: requestAmount,
        description: requestReason,
      });
    } catch (err) {
      console.error('Request creation error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-y-auto no-scrollbar">
      {/* Top Header */}
      <Header />

      <div className="px-5 py-3 flex flex-col gap-4">
        {/* Segmented Control Tabs */}
        <div className="bg-[#eaedeb] p-1 rounded-xl grid grid-cols-2 gap-1 select-none shadow-xs">
          <button
            type="button"
            onClick={() => setReceiveSubTab('qr')}
            className={`py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              receiveSubTab === 'qr'
                ? 'bg-white text-[#0e5a6b] shadow-xs'
                : 'text-[#55636a] hover:text-[#0f1a1d]'
            }`}
          >
            Mon QR
          </button>
          <button
            type="button"
            onClick={() => setReceiveSubTab('request')}
            className={`py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              receiveSubTab === 'request'
                ? 'bg-white text-[#0e5a6b] shadow-xs'
                : 'text-[#55636a] hover:text-[#0f1a1d]'
            }`}
          >
            Demander
          </button>
        </div>

        {/* Tab 1: Mon QR */}
        {receiveSubTab === 'qr' && (
          <div className="flex flex-col gap-4 items-center">
            {/* White QR Code Card */}
            <div className="w-full bg-white border border-[#d5dcdf] rounded-2xl p-6 flex flex-col items-center text-center shadow-sm">
              <div className="p-2 border border-[#eaedeb] rounded-xl bg-white shadow-xs">
                <QrCodeSvg size={200} />
              </div>

              <div className="mt-4 flex flex-col items-center">
                <span className="font-semibold text-[17px] text-[#0f1a1d]">
                  {user.name}
                </span>
                <span className="font-mono text-xs text-[#55636a] mt-0.5 tracking-wider">
                  {user.phone}
                </span>
              </div>

              <p className="text-xs text-[#55636a] mt-3 max-w-[270px] leading-relaxed">
                Faites scanner ce code : l'argent arrive sur votre compte Banque Démo •••• 0142.
              </p>
            </div>

            {/* 2 Buttons Side by Side */}
            <div className="w-full grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => alert('Lien de paiement copié')}
                className="bg-white border border-[#d5dcdf] rounded-xl py-3 px-4 text-xs font-semibold text-[#0e5a6b] hover:bg-[#fafaf9] active:bg-[#f0f4f5] transition-colors flex items-center justify-center gap-2 shadow-xs cursor-pointer"
              >
                <Share2 className="w-4 h-4 stroke-[2]" />
                <span>Partager</span>
              </button>

              <button
                type="button"
                onClick={() => alert('Ouverture du lecteur QR')}
                className="bg-white border border-[#d5dcdf] rounded-xl py-3 px-4 text-xs font-semibold text-[#0e5a6b] hover:bg-[#fafaf9] active:bg-[#f0f4f5] transition-colors flex items-center justify-center gap-2 shadow-xs cursor-pointer"
              >
                <ScanLine className="w-4 h-4 stroke-[2]" />
                <span>Scanner un QR</span>
              </button>
            </div>

            {/* Disclaimer Caption */}
            <p className="text-[12px] text-[#55636a] text-center select-none">
              QR fictif, régénéré toutes les 5 min.
            </p>
          </div>
        )}

        {/* Tab 2: Demander */}
        {receiveSubTab === 'request' && (
          <form
            onSubmit={handleRequestSubmit}
            className="bg-white border border-[#d5dcdf] rounded-xl p-5 flex flex-col gap-4 shadow-sm"
          >
            <div className="flex flex-col gap-1">
              <label
                htmlFor="req-payer"
                className="text-xs font-semibold text-[#55636a] uppercase tracking-wider"
              >
                À qui demander ?
              </label>
              <select
                id="req-payer"
                value={selectedPayerId}
                onChange={(e) => setSelectedPayerId(e.target.value)}
                className="h-11 px-3 bg-[#f5f6f4] border border-[#d5dcdf] rounded-xl text-sm font-medium text-[#0f1a1d] focus:border-[#0e5a6b] focus:outline-none"
              >
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.phone})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label
                htmlFor="req-amount"
                className="text-xs font-semibold text-[#55636a] uppercase tracking-wider"
              >
                Montant (€)
              </label>
              <input
                id="req-amount"
                type="text"
                value={requestAmount}
                onChange={(e) => setRequestAmount(e.target.value)}
                placeholder="15,00"
                className="h-11 px-3 font-mono text-lg font-semibold bg-[#f5f6f4] border border-[#d5dcdf] rounded-xl text-[#0f1a1d] focus:border-[#0e5a6b] focus:outline-none"
                required
              />
            </div>

            <div className="flex flex-col gap-1">
              <label
                htmlFor="req-reason"
                className="text-xs font-semibold text-[#55636a] uppercase tracking-wider"
              >
                Motif
              </label>
              <input
                id="req-reason"
                type="text"
                value={requestReason}
                onChange={(e) => setRequestReason(e.target.value)}
                placeholder="Courses, restaurant..."
                className="h-11 px-3 bg-[#f5f6f4] border border-[#d5dcdf] rounded-xl text-sm font-medium text-[#0f1a1d] focus:border-[#0e5a6b] focus:outline-none"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-2 w-full h-12 rounded-xl bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-[15px] flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-sm disabled:opacity-50"
            >
              {isSubmitting ? 'Envoi...' : `Demander ${requestAmount} €`}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
