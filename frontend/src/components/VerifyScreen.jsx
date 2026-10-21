import { useState } from 'react';
import { AlertCircle } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';

/**
 * Screen 4: Verify & Send transfer.
 * Handles Normal vs Incident state.
 * When in Incident mode, shows outage alert banner and disables submission.
 * Clicking send initiates 2FA Facial Recognition verification before completion.
 * No emojis used.
 */
export default function VerifyScreen() {
  const {
    isIncident,
    selectedContact,
    sendAmount,
    setSendAmount,
    sendReason,
    setSendReason,
    start2FAPayment,
    paymentError,
    setPaymentError,
    setCurrentScreen,
  } = useApp();

  const [isEditingAmount, setIsEditingAmount] = useState(false);

  const handleSend = () => {
    if (isIncident) return;
    if (setPaymentError) setPaymentError('');
    // Launch 2FA biometric verification step before money transfer
    start2FAPayment();
  };

  const formattedDisplayAmount = sendAmount?.includes('€')
    ? sendAmount
    : `${sendAmount || '10,00'} €`;

  return (
    <div className="flex-1 flex flex-col justify-between overflow-y-auto no-scrollbar">
      {/* Top Header */}
      <div>
        <Header showBack onBack={() => setCurrentScreen('SEND_CONTACT')} />

        <div className="px-5 py-3 flex flex-col gap-4">
          {/* Payment Error Banner */}
          {paymentError && (
            <div
              role="alert"
              className="bg-[#fde8e8] text-[#c81e1e] border border-[#f8b4b4] rounded-xl p-3.5 flex items-start gap-2.5 shadow-xs animate-fadeIn text-xs"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex flex-col gap-0.5">
                <span className="font-semibold text-sm leading-snug">
                  Échec de l&apos;envoi
                </span>
                <span className="leading-relaxed">{paymentError}</span>
              </div>
            </div>
          )}

          {/* Incident Alert Banner */}
          {isIncident && (
            <div
              role="alert"
              className="bg-[#3d1714] text-[#f47066] border border-[#5c2b2e] rounded-xl p-4 flex items-start gap-3 shadow-xs animate-fadeIn"
            >
              <span aria-hidden="true" className="text-sm font-bold mt-0.5 select-none">
                ■
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="font-semibold text-sm leading-snug text-white">
                  Envois momentanément indisponibles.
                </span>
                <span className="text-xs text-[#f47066] leading-relaxed">
                  Anomalie détectée à{' '}
                  <span className="font-mono text-white">10:42:07</span>. Votre argent n&apos;a
                  pas quitté votre compte.
                </span>
              </div>
            </div>
          )}

          {/* Transfer Summary Card */}
          <section
            aria-label="Récapitulatif de transfert"
            className="bg-white border border-[#d5dcdf] rounded-xl p-5 flex flex-col gap-4 shadow-sm"
          >
            {/* Amount Section */}
            <div className="flex flex-col gap-1 border-b border-[#d5dcdf] pb-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[#55636a] uppercase tracking-wider">
                  Vous envoyez
                </span>
                <button
                  type="button"
                  onClick={() => setIsEditingAmount(!isEditingAmount)}
                  className="text-xs text-[#0e5a6b] font-medium hover:underline cursor-pointer"
                >
                  {isEditingAmount ? 'Valider' : 'Modifier'}
                </button>
              </div>

              {isEditingAmount ? (
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="text"
                    value={sendAmount}
                    onChange={(e) => setSendAmount(e.target.value)}
                    className="font-mono text-2xl font-semibold text-[#0f1a1d] bg-[#f5f6f4] px-2 py-1 rounded-lg border border-[#7f8c93] w-36 focus:outline-none focus:border-[#0e5a6b]"
                    autoFocus
                  />
                  <span className="font-mono text-2xl font-semibold text-[#0f1a1d]">€</span>
                </div>
              ) : (
                <div className="font-mono text-3xl font-semibold text-[#0f1a1d] tracking-tight mt-0.5">
                  {formattedDisplayAmount}
                </div>
              )}
            </div>

            {/* Recipient Details */}
            <div className="flex flex-col gap-1 border-b border-[#d5dcdf] pb-4">
              <span className="text-xs font-semibold text-[#55636a] uppercase tracking-wider">
                À
              </span>
              <div className="flex items-center gap-3 mt-1">
                <div className="w-10 h-10 rounded-full bg-[#dcecef] text-[#0a4552] font-semibold text-xs flex items-center justify-center shrink-0">
                  {selectedContact?.initials || 'DE'}
                </div>
                <div className="flex flex-col">
                  <span className="font-semibold text-[15px] text-[#0f1a1d]">
                    {selectedContact?.name || 'Destinataire'}
                  </span>
                  <span className="font-mono text-xs text-[#55636a]">
                    {selectedContact?.phone || selectedContact?.email || ''}
                  </span>
                </div>
              </div>
            </div>

            {/* Transfer Reason / Motif */}
            <div className="flex flex-col gap-1 border-b border-[#d5dcdf] pb-4">
              <span className="text-xs font-semibold text-[#55636a] uppercase tracking-wider">
                Motif
              </span>
              <input
                type="text"
                value={sendReason}
                onChange={(e) => setSendReason(e.target.value)}
                placeholder="Motif du paiement"
                className="text-[14px] font-medium text-[#0f1a1d] bg-transparent border-0 p-0 focus:outline-none focus:ring-0 placeholder-[#7f8c93]"
              />
            </div>

            {/* Service Status Row */}
            <div className="flex items-center justify-between pt-0.5">
              <span className="text-xs font-semibold text-[#55636a] uppercase tracking-wider">
                Service d&apos;envoi
              </span>
              {isIncident ? (
                <span className="text-[#c81e1e] font-semibold text-xs inline-flex items-center gap-1.5">
                  <span aria-hidden="true">■</span> Incident
                </span>
              ) : (
                <span className="text-[#1e7a45] font-semibold text-xs inline-flex items-center gap-1.5">
                  <span aria-hidden="true">●</span> Opérationnel
                </span>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* Action Button at Bottom */}
      <div className="p-5 flex flex-col gap-2">
        {isIncident ? (
          <>
            <button
              type="button"
              disabled
              className="w-full h-12 rounded-xl bg-[#eaedeb] text-[#55636a] border border-[#d5dcdf] font-semibold text-[15px] flex items-center justify-center cursor-not-allowed select-none shadow-xs"
            >
              Envoi suspendu
            </button>
            <p className="text-xs text-[#55636a] text-center leading-tight">
              Nos équipes analysent l&apos;incident technique en cours.
            </p>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={handleSend}
              className="w-full h-12 rounded-xl bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-[15px] flex items-center justify-center transition-colors shadow-xs cursor-pointer"
            >
              Envoyer {formattedDisplayAmount}
            </button>
            <p className="text-xs text-[#55636a] text-center leading-tight">
              Validation par reconnaissance faciale à l&apos;étape suivante.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
