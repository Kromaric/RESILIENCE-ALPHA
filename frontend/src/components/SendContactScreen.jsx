import { useState, useMemo } from 'react';
import { Search, ChevronRight } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';

/**
 * Screen 3: Send - Choose Contact.
 * Real-time filterable contacts list registered on Orbe, or manual recipient entry.
 * No emojis used.
 */
export default function SendContactScreen() {
  const { contacts, setSelectedContact, setSendAmount, setSendReason, setCurrentScreen, navigateToTab } = useApp();
  const [searchQuery, setSearchQuery] = useState('');

  // Filter contacts in real time by name, phone or email
  const filteredContacts = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return contacts;
    return contacts.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.phone.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        (c.rawPhone && c.rawPhone.includes(q))
    );
  }, [contacts, searchQuery]);

  const handleSelectContact = (contact) => {
    setSelectedContact(contact);
    setSendAmount(contact.defaultAmount || '10,00');
    setSendReason(contact.defaultReason || 'Virement');
    setCurrentScreen('VERIFY');
  };

  const handleSelectCustom = (query) => {
    const trimmed = query.trim();
    const contact = {
      id: trimmed,
      name: trimmed,
      phone: trimmed,
      rawPhone: trimmed,
      email: trimmed.includes('@') ? trimmed : '',
      initials: (trimmed.slice(0, 2) || 'DE').toUpperCase(),
      defaultAmount: '10,00',
      defaultReason: 'Virement',
    };
    setSelectedContact(contact);
    setSendAmount('10,00');
    setSendReason('Virement');
    setCurrentScreen('VERIFY');
  };

  return (
    <div className="flex-1 flex flex-col overflow-y-auto no-scrollbar">
      {/* Top Header with Back button */}
      <Header
        showBack
        onBack={() => {
          if (navigateToTab) navigateToTab('home');
          else setCurrentScreen('HOME');
        }}
      />

      <div className="px-5 py-3 flex flex-col gap-4">
        {/* Search Field */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="contact-search"
            className="text-xs font-semibold text-[#55636a] uppercase tracking-wider"
          >
            À qui envoyer ?
          </label>
          <div className="relative">
            <Search className="w-4 h-4 text-[#7f8c93] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              id="contact-search"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Numéro de mobile, email ou nom"
              className="w-full h-11 pl-10 pr-4 bg-white border border-[#d5dcdf] rounded-xl text-[14px] text-[#0f1a1d] placeholder-[#7f8c93] focus:border-[#0e5a6b] focus:outline-none transition-colors shadow-xs"
            />
          </div>
        </div>

        {/* Contacts Section */}
        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold text-[#55636a]">
            {filteredContacts.length > 0 ? 'Contacts enregistrés' : 'Destinataire'}
          </span>

          <div className="bg-white border border-[#d5dcdf] rounded-xl overflow-hidden divide-y divide-[#d5dcdf] shadow-xs">
            {filteredContacts.length > 0 ? (
              filteredContacts.map((contact) => (
                <button
                  key={contact.id}
                  type="button"
                  onClick={() => handleSelectContact(contact)}
                  className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-[#fafaf9] active:bg-[#f0f4f5] transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#dcecef] text-[#0a4552] font-semibold text-xs flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                      {contact.initials}
                    </div>
                    <div className="flex flex-col">
                      <span className="font-semibold text-[14px] text-[#0f1a1d]">
                        {contact.name}
                      </span>
                      <span className="font-mono text-xs text-[#55636a]">
                        {contact.phone}
                      </span>
                    </div>
                  </div>

                  <div className="text-[#55636a] group-hover:text-[#0e5a6b] group-hover:translate-x-0.5 transition-all">
                    <ChevronRight className="w-5 h-5 stroke-[2]" />
                  </div>
                </button>
              ))
            ) : searchQuery.trim().length > 0 ? (
              <button
                type="button"
                onClick={() => handleSelectCustom(searchQuery)}
                className="w-full px-4 py-3.5 flex items-center justify-between text-left hover:bg-[#fafaf9] active:bg-[#f0f4f5] transition-colors cursor-pointer group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[#0e5a6b] text-white font-semibold text-xs flex items-center justify-center shrink-0">
                    {(searchQuery.trim().slice(0, 2) || 'DE').toUpperCase()}
                  </div>
                  <div className="flex flex-col">
                    <span className="font-semibold text-[14px] text-[#0f1a1d]">
                      Envoyer à &quot;{searchQuery.trim()}&quot;
                    </span>
                    <span className="text-xs text-[#55636a]">
                      Saisie manuelle du destinataire
                    </span>
                  </div>
                </div>
                <div className="text-[#0e5a6b]">
                  <ChevronRight className="w-5 h-5 stroke-[2]" />
                </div>
              </button>
            ) : (
              <div className="p-6 text-center text-xs text-[#55636a] leading-relaxed">
                Aucun contact enregistré. Saisissez un numéro de mobile ou une adresse email ci-dessus pour envoyer de l&apos;argent.
              </div>
            )}
          </div>
        </div>

        {/* Explanatory Bottom Note */}
        <p className="text-xs text-[#55636a] leading-relaxed px-1">
          L&apos;argent part directement de votre compte et arrive chez votre destinataire en quelques secondes.
        </p>
      </div>
    </div>
  );
}
