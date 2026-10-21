import { useState, useCallback, useEffect } from 'react';
import { AppContext } from './AppContextInstance';
import {
  checkBackendHealth,
  getAccountInfo,
  getContacts,
  getTransactions,
  getQrCode,
  sendPaymentApi,
  createPaymentRequestApi,
  getMeProfile,
  loginWithPassword,
} from '../services/api';

// Initial mock contacts matching UI specification
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
    subtitle: 'Remboursement ciné · 14:32',
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
    amountFormatted: '− 45,00 €',
    amountNum: -45.0,
    type: 'sent',
    status: 'Envoyé',
    statusSymbol: '●',
    isFailed: false,
    date: new Date(Date.now() - 2 * 86400000),
  },
  {
    id: 'tx_8',
    section: '15 octobre',
    initials: 'CT',
    counterparty: 'Camille Test',
    subtitle: 'Remboursement courses · 12:00',
    amountFormatted: '+ 30,00 €',
    amountNum: 30.0,
    type: 'refund',
    status: 'Remboursé',
    statusSymbol: '◇',
    isFailed: false,
    date: new Date(Date.now() - 2 * 86400000),
  },
];

export function AppProvider({ children }) {
  // Navigation & Screen Management
  const [currentScreen, setCurrentScreen] = useState('HOME');
  const [activeTab, setActiveTab] = useState('home'); // 'home', 'send', 'receive', 'activity'
  const [receiveSubTab, setReceiveSubTab] = useState('qr'); // 'qr' or 'request'
  const [activityFilter, setActivityFilter] = useState('all'); // 'all', 'sent', 'received'

  // Resilience & Health States
  const [isIncident, setIsIncident] = useState(false);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [manualOverride, setManualOverride] = useState(null); // null (auto) | 'incident' | 'operational'

  // Biometric challenge state from auth-service
  const [faceChallenge, setFaceChallenge] = useState(null); // { direction: 'left' | 'right', frames: number, interval_ms: number }
  const [sessionId, setSessionId] = useState(null);

  // User Profile
  const [user, setUser] = useState({
    name: 'Camille Test',
    email: 'camille@orbe.test',
    phone: '+33 6 •• •• •• 78',
    accountMasked: 'FR76 •••• •••• 0142',
    bankLabel: 'Banque Démo',
    initials: 'CT',
    faceEnrolled: false,
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

  // Pending 2FA flow tracking
  const [pending2FA, setPending2FA] = useState(null); // null | { type: 'payment' } | { type: 'login', email, password, sessionId }

  // Periodic health check probe
  const pollHealth = useCallback(async () => {
    if (manualOverride !== null) {
      return;
    }
    setIsCheckingHealth(true);
    try {
      const health = await checkBackendHealth();
      setIsIncident(!health.operational);
    } catch {
      setIsIncident(true);
    } finally {
      setIsCheckingHealth(false);
    }
  }, [manualOverride]);

  useEffect(() => {
    let isMounted = true;
    const check = async () => {
      if (manualOverride !== null) return;
      try {
        const health = await checkBackendHealth();
        if (isMounted && manualOverride === null) {
          setIsIncident(!health.operational);
        }
      } catch {
        if (isMounted && manualOverride === null) {
          setIsIncident(true);
        }
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [manualOverride]);

  // Synchronize dynamic data from backend
  const syncBackendData = useCallback(async (token) => {
    try {
      const [accountResult, contactsResult, txResult, qrResult, meResult] = await Promise.all([
        getAccountInfo(token),
        getContacts(token),
        getTransactions(token),
        getQrCode(token),
        getMeProfile(token),
      ]);

      if (meResult) {
        setUser((prev) => ({
          ...prev,
          name: meResult.display_name || prev.name,
          email: meResult.email || prev.email,
          phone: meResult.phone_masked || prev.phone,
          faceEnrolled: Boolean(meResult.face_enrolled),
          initials: (meResult.display_name || 'CT')
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2),
        }));
      }

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
        setTransactions(txResult);
      }

      if (qrResult) {
        setQrData(qrResult);
      }
    } catch (err) {
      console.warn('Backend sync warning (using defaults):', err);
    }
  }, []);

  // Sync on startup with initial token
  useEffect(() => {
    let isMounted = true;
    if (authToken) {
      Promise.resolve().then(() => {
        if (isMounted) {
          syncBackendData(authToken);
        }
      });
    }
    return () => {
      isMounted = false;
    };
  }, [authToken, syncBackendData]);

  // Manual incident simulation
  const triggerIncident = useCallback(() => {
    setManualOverride('incident');
    setIsIncident(true);
  }, []);

  // Manual operational restoration
  const restoreOperational = useCallback(() => {
    setManualOverride('operational');
    setIsIncident(false);
  }, []);

  // Reset to auto health monitoring
  const resetToAutoDetection = useCallback(() => {
    setManualOverride(null);
    pollHealth();
  }, [pollHealth]);

  // Execute payment transaction
  const executePayment = useCallback(async () => {
    const cleanAmount = parseFloat(sendAmount.replace(',', '.')) || 12.5;
    const amountCents = Math.round(cleanAmount * 100);

    if (!isIncident && authToken) {
      try {
        await sendPaymentApi(
          {
            recipientId: selectedContact.id,
            amount_cents: amountCents,
            description: sendReason,
          },
          authToken
        );
      } catch (err) {
        console.warn('Backend payment rejected, recording local state:', err);
      }
    }

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

  // Start 2FA login flow against auth-service /login with custom credentials
  const start2FALogin = useCallback(async (email = 'camille@orbe.test', password = 'demo-password') => {
    const result = await loginWithPassword(email, password);

    if (result.mfa_required) {
      // Step 1 done: face challenge received
      setSessionId(result.session_id);
      setFaceChallenge(result.face_challenge || { direction: 'left', frames: 8, interval_ms: 250 });
      setPending2FA({ type: 'login', email, password, sessionId: result.session_id });
      setCurrentScreen('FACE_AUTH');
    } else if (result.face_enrollment_required) {
      // Logged in with password only, no face enrolled yet -> go to enrollment screen
      const token = result.token?.access_token || 'demo-token';
      setAuthToken(token);
      setSessionId(result.session_id);
      setPending2FA(null);
      await syncBackendData(token);
      setCurrentScreen('FACE_ENROLL');
    } else {
      // Direct login success
      const token = result.token?.access_token || 'demo-token';
      setAuthToken(token);
      setPending2FA(null);
      await syncBackendData(token);
      setCurrentScreen('HOME');
    }
  }, [syncBackendData]);

  // Retry 2FA login by renewing the session and obtaining a fresh challenge
  const retry2FALogin = useCallback(async () => {
    if (pending2FA?.email && pending2FA?.password) {
      const result = await loginWithPassword(pending2FA.email, pending2FA.password);
      if (result.mfa_required) {
        setSessionId(result.session_id);
        setFaceChallenge(result.face_challenge || { direction: 'left', frames: 8, interval_ms: 250 });
        setPending2FA((prev) => ({ ...prev, sessionId: result.session_id }));
        return result;
      }
    }
    return null;
  }, [pending2FA]);

  // Start 2FA payment flow
  const start2FAPayment = useCallback(() => {
    // For payments, present a face verification challenge
    setFaceChallenge({ direction: 'right', frames: 8, interval_ms: 250 });
    setPending2FA({ type: 'payment' });
    setCurrentScreen('FACE_AUTH');
  }, []);

  // Complete face authentication and route to next screen
  const completeFaceAuth = useCallback(async (issuedToken) => {
    const token = issuedToken || authToken;
    if (issuedToken) {
      setAuthToken(issuedToken);
    }

    if (pending2FA?.type === 'login') {
      setPending2FA(null);
      setCurrentScreen('HOME');
      setActiveTab('home');
      syncBackendData(token);
    } else if (pending2FA?.type === 'payment') {
      setPending2FA(null);
      await executePayment();
    }
  }, [authToken, pending2FA, executePayment, syncBackendData]);

  // Legacy on2FASuccess callback
  const on2FASuccess = useCallback(async () => {
    await completeFaceAuth();
  }, [completeFaceAuth]);

  // 2FA Cancel callback
  const on2FACancel = useCallback(() => {
    if (pending2FA?.type === 'login') {
      setPending2FA(null);
      setCurrentScreen('LOGIN');
    } else {
      setPending2FA(null);
      setCurrentScreen('VERIFY');
    }
  }, [pending2FA]);

  // Logout handler returning to Login screen
  const handleLogout = useCallback(() => {
    setAuthToken(null);
    setSessionId(null);
    setPending2FA(null);
    setFaceChallenge(null);
    setUser({
      name: 'Camille Test',
      email: 'camille@orbe.test',
      phone: '+33 6 •• •• •• 78',
      accountMasked: 'FR76 •••• •••• 0142',
      bankLabel: 'Banque Démo',
      initials: 'CT',
      faceEnrolled: false,
    });
    setCurrentScreen('LOGIN');
  }, []);

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
        receiveSubTab,
        setReceiveSubTab,
        user,
        setUser,
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
        isCheckingHealth,
        triggerIncident,
        restoreOperational,
        resetToAutoDetection,
        pollHealth,
        handleLogout,
        start2FALogin,
        retry2FALogin,
        start2FAPayment,
        completeFaceAuth,
        on2FASuccess,
        on2FACancel,
        pending2FA,
        faceChallenge,
        setFaceChallenge,
        sessionId,
        setSessionId,
        authToken,
        setAuthToken,
        qrData,
        syncBackendData,
        executePayment,
        executeCreateRequest,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
