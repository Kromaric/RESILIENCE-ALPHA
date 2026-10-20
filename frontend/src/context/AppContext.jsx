import { useState, useEffect, useCallback } from 'react';
import { AppContext } from './AppContextInstance';
import {
  checkBackendHealth,
  authenticateWithPin,
  sendPaymentApi,
  createPaymentRequestApi,
  getAccountInfo,
  getContacts,
  getTransactions,
  getQrCode,
} from '../services/api';

// Initial registered contacts list on Orbe matching backend seed
const INITIAL_CONTACTS = [
  {
    id: '22222222-2222-2222-2222-222222222222',
    initials: 'LM',
    name: 'Léa Martin',
    phone: '+33 6 •• •• 12 34',
    rawPhone: '+33612345677',
    email: 'lea@orbe.test',
    defaultAmount: '12,50',
    defaultReason: 'Ciné',
  },
  {
    id: '33333333-3333-3333-3333-333333333333',
    initials: 'HB',
    name: 'Hugo Bernard',
    phone: '+33 7 •• •• 56 78',
    rawPhone: '+33612345676',
    email: 'hugo@orbe.test',
    defaultAmount: '25,00',
    defaultReason: 'Pizza vendredi',
  },
  {
    id: '3',
    initials: 'IP',
    name: 'Inès Petit',
    phone: '+33 6 •• •• 90 11',
    rawPhone: '+33690119011',
    email: 'ines.petit@orbe.test',
    defaultAmount: '15,00',
    defaultReason: 'Cadeau Nathan',
  },
  {
    id: '4',
    initials: 'NM',
    name: 'Nathan Moreau',
    phone: '+33 6 •• •• 22 45',
    rawPhone: '+33622452245',
    email: 'nathan.moreau@orbe.test',
    defaultAmount: '8,00',
    defaultReason: 'Covoiturage',
  },
];

// Initial mock transactions list matching specifications
const INITIAL_TRANSACTIONS = [
  {
    id: 'tx_1',
    section: "Aujourd'hui",
    initials: 'LM',
    counterparty: 'Léa Martin',
    subtitle: 'Ciné · 10:44',
    amountFormatted: '− 12,50 €',
    amountNum: -12.5,
    type: 'sent',
    status: 'Envoyé',
    statusSymbol: '●',
    isFailed: false,
    date: new Date(),
  },
  {
    id: 'tx_2',
    section: "Aujourd'hui",
    initials: 'LM',
    counterparty: 'Léa Martin',
    subtitle: 'Ciné · 10:42',
    amountFormatted: '12,50 €',
    amountNum: 12.5,
    type: 'sent',
    status: 'Échec',
    statusSymbol: '■',
    isFailed: true,
    date: new Date(),
  },
  {
    id: 'tx_3',
    section: "Aujourd'hui",
    initials: 'HB',
    counterparty: 'Hugo Bernard',
    subtitle: 'Pizza vendredi · 09:12',
    amountFormatted: '+ 25,00 €',
    amountNum: 25.0,
    type: 'received',
    status: 'Reçu',
    statusSymbol: '●',
    isFailed: false,
    date: new Date(),
  },
  {
    id: 'tx_4',
    section: 'Hier',
    initials: 'IP',
    counterparty: 'Inès Petit',
    subtitle: 'Courses · 18:30',
    amountFormatted: '+ 18,40 €',
    amountNum: 18.4,
    type: 'request',
    status: 'Demandé',
    statusSymbol: '●',
    isFailed: false,
    date: new Date(Date.now() - 86400000),
  },
  {
    id: 'tx_5',
    section: 'Hier',
    initials: 'IP',
    counterparty: 'Inès Petit',
    subtitle: 'Cadeau Nathan · 16:05',
    amountFormatted: '− 15,00 €',
    amountNum: -15.0,
    type: 'sent',
    status: 'Envoyé',
    statusSymbol: '●',
    isFailed: false,
    date: new Date(Date.now() - 86400000),
  },
  {
    id: 'tx_6',
    section: 'Hier',
    initials: 'NM',
    counterparty: 'Nathan Moreau',
    subtitle: 'Covoiturage · 08:20',
    amountFormatted: '+ 8,00 €',
    amountNum: 8.0,
    type: 'received',
    status: 'Reçu',
    statusSymbol: '●',
    isFailed: false,
    date: new Date(Date.now() - 86400000),
  },
  {
    id: 'tx_7',
    section: '15 octobre',
    initials: 'HB',
    counterparty: 'Hugo Bernard',
    subtitle: 'Place de concert · 20:11',
    amountFormatted: '42,00 €',
    amountNum: 42.0,
    type: 'refund',
    status: 'Remboursé',
    statusSymbol: '◇',
    isFailed: false,
    date: new Date(2026, 9, 15),
  },
];

export function AppProvider({ children }) {
  // Navigation & Views: 'PIN', 'FACE_AUTH', 'HOME', 'SEND_CONTACT', 'VERIFY', 'RECEIVE', 'ACTIVITY'
  const [currentScreen, setCurrentScreen] = useState('PIN');
  const [activeTab, setActiveTab] = useState('home'); // 'home' | 'activity' | 'receive'
  const [receiveSubTab, setReceiveSubTab] = useState('qr'); // 'qr' | 'request'

  // 2FA Biometric Context: null | { type: 'login', pin?: string } | { type: 'payment' }
  const [pending2FA, setPending2FA] = useState(null);

  // User Profile
  const [user, setUser] = useState({
    name: 'Camille Test',
    email: 'camille@orbe.test',
    phone: '+33 6 •• •• •• 78',
    accountMasked: 'FR76 •••• •••• 0142',
    bankLabel: 'Banque Démo',
    initials: 'CT',
  });

  const [authToken, setAuthToken] = useState('demo-token');
  const [qrData, setQrData] = useState(null);

  // Contacts & Active Transaction Setup
  const [contacts, setContacts] = useState(INITIAL_CONTACTS);
  const [selectedContact, setSelectedContact] = useState(INITIAL_CONTACTS[0]);
  const [sendAmount, setSendAmount] = useState('12,50');
  const [sendReason, setSendReason] = useState('Ciné');

  // Transactions State
  const [transactions, setTransactions] = useState(INITIAL_TRANSACTIONS);
  const [activityFilter, setActivityFilter] = useState('all'); // 'all' | 'sent' | 'received' | 'requests'

  // Resilience & Incident State
  // manualOverride: true (forced incident), false (forced operational), or null (auto-detect)
  const [manualOverride, setManualOverride] = useState(null);
  const [autoHealthStatus, setAutoHealthStatus] = useState('operational'); // 'operational' | 'incident'
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  // Manual health poll
  const pollHealth = useCallback(async () => {
    setIsCheckingHealth(true);
    const result = await checkBackendHealth();
    setAutoHealthStatus(result.operational ? 'operational' : 'incident');
    setIsCheckingHealth(false);
  }, []);

  // Regular health check interval
  useEffect(() => {
    let isMounted = true;
    async function runCheck() {
      const result = await checkBackendHealth();
      if (isMounted) {
        setAutoHealthStatus(result.operational ? 'operational' : 'incident');
      }
    }

    runCheck();
    const interval = setInterval(runCheck, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Combined incident state: manual override takes precedence, otherwise auto health
  const isIncident = manualOverride !== null ? manualOverride : autoHealthStatus === 'incident';

  // Toggle manual override between operational and incident
  const toggleIncidentMode = () => {
    setManualOverride((prev) => {
      if (prev === null) {
        return !isIncident;
      }
      return !prev;
    });
  };

  // Reset to auto health detection
  const resetToAutoDetection = () => {
    setManualOverride(null);
    pollHealth();
  };

  // Switch navigation tab
  const navigateToTab = (tab) => {
    setActiveTab(tab);
    if (tab === 'home') setCurrentScreen('HOME');
    if (tab === 'activity') setCurrentScreen('ACTIVITY');
    if (tab === 'receive') {
      setReceiveSubTab('qr');
      setCurrentScreen('RECEIVE');
    }
  };

  // Helper to synchronize data from live backend
  const syncBackendData = useCallback(async (token) => {
    try {
      const [accountResult, contactsResult, txResult, qrResult] = await Promise.all([
        getAccountInfo(token),
        getContacts(token),
        getTransactions(token),
        getQrCode(token),
      ]);

      if (accountResult?.payout_account) {
        setUser((prev) => ({
          ...prev,
          bankLabel: accountResult.payout_account.label || prev.bankLabel,
          accountMasked: `FR76 •••• •••• ${accountResult.payout_account.iban_last4 || '0142'}`,
        }));
      }

      if (Array.isArray(contactsResult) && contactsResult.length > 0) {
        setContacts(contactsResult);
        setSelectedContact(contactsResult[0]);
      }

      if (Array.isArray(txResult) && txResult.length > 0) {
        setTransactions((prev) => {
          const remoteIds = new Set(txResult.map((t) => t.id));
          const remainingPrev = prev.filter((t) => !remoteIds.has(t.id));
          return [...txResult, ...remainingPrev];
        });
      }

      if (qrResult) {
        setQrData(qrResult);
      }
    } catch (err) {
      console.warn('Backend data synchronization fallback:', err);
    }
  }, []);

  // Execute payment
  const executePayment = useCallback(async () => {
    if (isIncident) {
      throw new Error('Service currently unavailable due to incident');
    }

    const cleanAmount = parseFloat(sendAmount.replace(',', '.')) || 12.5;
    const amountCents = Math.round(cleanAmount * 100);

    try {
      await sendPaymentApi(
        {
          recipientId: selectedContact.id.length === 36 ? selectedContact.id : undefined,
          recipient: selectedContact.rawPhone || selectedContact.email,
          amount_cents: amountCents,
          description: sendReason,
        },
        authToken
      );
    } catch (err) {
      // In demo resilience mode, handled gracefully with fallback logging
      console.warn('Payment executed via resilience fallback:', err.message);
    }

    // Format current time HH:MM
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const amountFormatted = `− ${sendAmount.includes(',') ? sendAmount : sendAmount + ',00'} €`;

    const newTx = {
      id: `tx_${Date.now()}`,
      section: "Aujourd'hui",
      initials: selectedContact.initials,
      counterparty: selectedContact.name,
      subtitle: `${sendReason || 'Virement'} · ${timeStr}`,
      amountFormatted: amountFormatted,
      amountNum: -cleanAmount,
      type: 'sent',
      status: 'Envoyé',
      statusSymbol: '●',
      isFailed: false,
      date: now,
    };

    setTransactions((prev) => [newTx, ...prev]);
    setCurrentScreen('ACTIVITY');
    setActiveTab('activity');
  }, [authToken, isIncident, selectedContact, sendAmount, sendReason]);

  // Start 2FA login flow
  const start2FALogin = useCallback((pin) => {
    setPending2FA({ type: 'login', pin });
    setCurrentScreen('FACE_AUTH');
  }, []);

  // Start 2FA payment flow
  const start2FAPayment = useCallback(() => {
    setPending2FA({ type: 'payment' });
    setCurrentScreen('FACE_AUTH');
  }, []);

  // 2FA Success callback
  const on2FASuccess = useCallback(async () => {
    if (pending2FA?.type === 'login') {
      const authResult = await authenticateWithPin(pending2FA.pin);
      const token = authResult.access_token;
      setAuthToken(token);

      if (authResult.client) {
        setUser((prev) => ({
          ...prev,
          name: authResult.client.name,
          email: authResult.client.email,
          phone: authResult.client.phone,
          initials: authResult.client.name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2),
        }));
      }

      setPending2FA(null);
      setCurrentScreen('HOME');
      setActiveTab('home');

      // Fetch dynamic backend resources
      syncBackendData(token);
    } else if (pending2FA?.type === 'payment') {
      setPending2FA(null);
      await executePayment();
    }
  }, [pending2FA, executePayment, syncBackendData]);

  // 2FA Cancel callback
  const on2FACancel = useCallback(() => {
    if (pending2FA?.type === 'login') {
      setPending2FA(null);
      setCurrentScreen('PIN');
    } else {
      setPending2FA(null);
      setCurrentScreen('VERIFY');
    }
  }, [pending2FA]);

  // Direct login handler (as a shortcut if needed)
  const handleLogin = async (pin) => {
    start2FALogin(pin);
  };

  // Create payment request
  const executeCreateRequest = async ({ payer, amount, description }) => {
    const cleanAmount = parseFloat(amount.replace(',', '.')) || 10;
    const amountCents = Math.round(cleanAmount * 100);

    try {
      await createPaymentRequestApi(
        {
          payer: payer.rawPhone || payer.email,
          amount_cents: amountCents,
          description,
        },
        authToken
      );
    } catch {
      // Fallback
    }

    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const amountFormatted = `+ ${amount.includes(',') ? amount : amount + ',00'} €`;

    const newReqTx = {
      id: `rq_${Date.now()}`,
      section: "Aujourd'hui",
      initials: payer.initials,
      counterparty: payer.name,
      subtitle: `${description || 'Demande'} · ${timeStr}`,
      amountFormatted: amountFormatted,
      amountNum: cleanAmount,
      type: 'request',
      status: 'Demandé',
      statusSymbol: '●',
      isFailed: false,
      date: now,
    };

    setTransactions((prev) => [newReqTx, ...prev]);
    setCurrentScreen('ACTIVITY');
    setActiveTab('activity');
  };

  return (
    <AppContext.Provider
      value={{
        currentScreen,
        setCurrentScreen,
        activeTab,
        setActiveTab,
        navigateToTab,
        receiveSubTab,
        setReceiveSubTab,
        user,
        contacts,
        selectedContact,
        setSelectedContact,
        sendAmount,
        setSendAmount,
        sendReason,
        setSendReason,
        transactions,
        activityFilter,
        setActivityFilter,
        isIncident,
        manualOverride,
        autoHealthStatus,
        isCheckingHealth,
        toggleIncidentMode,
        resetToAutoDetection,
        pollHealth,
        handleLogin,
        start2FALogin,
        start2FAPayment,
        on2FASuccess,
        on2FACancel,
        pending2FA,
        authToken,
        qrData,
        executePayment,
        executeCreateRequest,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
