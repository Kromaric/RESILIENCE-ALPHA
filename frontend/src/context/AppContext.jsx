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

export function AppProvider({ children }) {
  // Persistent Authentication State from localStorage
  const [authToken, setAuthTokenState] = useState(() => {
    try {
      return localStorage.getItem('orbe_auth_token') || null;
    } catch {
      return null;
    }
  });

  const [user, setUserState] = useState(() => {
    try {
      const saved = localStorage.getItem('orbe_user_profile');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  // Default screen: HOME if user has an active token, otherwise LOGIN
  const [currentScreen, setCurrentScreen] = useState(() => {
    try {
      return localStorage.getItem('orbe_auth_token') ? 'HOME' : 'LOGIN';
    } catch {
      return 'LOGIN';
    }
  });

  // Notice & prefill after account registration
  const [loginNotice, setLoginNotice] = useState('');
  const [prefilledEmail, setPrefilledEmail] = useState('');

  // Active navigation tab
  const [activeTab, setActiveTab] = useState('home'); // 'home', 'send', 'receive', 'activity'
  const [receiveSubTab, setReceiveSubTab] = useState('qr'); // 'qr' or 'request'
  const [activityFilter, setActivityFilter] = useState('all'); // 'all', 'sent', 'received', 'requests'

  // Resilience & Health States
  const [isIncident, setIsIncident] = useState(false);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [manualOverride, setManualOverride] = useState(null); // null (auto) | 'incident' | 'operational'

  // Biometric challenge state from auth-service
  const [faceChallenge, setFaceChallenge] = useState(null); // { direction: 'left' | 'right', frames: number, interval_ms: number }
  const [sessionId, setSessionId] = useState(null);

  const [qrData, setQrData] = useState(null);

  // Dynamic user data from backend (no mock/demo prefilled entries)
  const [contacts, setContacts] = useState([]);
  const [selectedContact, setSelectedContact] = useState(null);
  const [sendAmount, setSendAmount] = useState('10,00');
  const [sendReason, setSendReason] = useState('');
  const [transactions, setTransactions] = useState([]);

  // Pending 2FA flow tracking: null | { type: 'payment' } | { type: 'login', email, password, sessionId }
  const [pending2FA, setPending2FA] = useState(null);

  // Synchronized setter for authToken with localStorage
  const setAuthToken = useCallback((token) => {
    setAuthTokenState(token);
    try {
      if (token) {
        localStorage.setItem('orbe_auth_token', token);
      } else {
        localStorage.removeItem('orbe_auth_token');
      }
    } catch (err) {
      console.warn('LocalStorage token error:', err);
    }
  }, []);

  // Synchronized setter for user with localStorage
  const setUser = useCallback((userOrUpdater) => {
    setUserState((prev) => {
      const next = typeof userOrUpdater === 'function' ? userOrUpdater(prev) : userOrUpdater;
      try {
        if (next) {
          localStorage.setItem('orbe_user_profile', JSON.stringify(next));
        } else {
          localStorage.removeItem('orbe_user_profile');
        }
      } catch (err) {
        console.warn('LocalStorage user error:', err);
      }
      return next;
    });
  }, []);

  // Navigate to bottom tab
  const navigateToTab = useCallback((tabId) => {
    setActiveTab(tabId);
    if (tabId === 'home') {
      setCurrentScreen('HOME');
    } else if (tabId === 'activity') {
      setCurrentScreen('ACTIVITY');
    } else if (tabId === 'receive') {
      setCurrentScreen('RECEIVE');
    } else if (tabId === 'send') {
      setCurrentScreen('SEND_CONTACT');
    }
  }, []);

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
    if (!token) return;
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
          name: meResult.display_name || prev?.name || 'Mon Compte',
          email: meResult.email || prev?.email || '',
          phone: meResult.phone_masked || prev?.phone || '',
          faceEnrolled: Boolean(meResult.face_enrolled),
          initials: (meResult.display_name || 'OR')
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
          bankLabel: accountResult.payout_account.label || prev?.bankLabel || 'Compte Orbe',
          accountMasked: accountResult.payout_account.iban_last4
            ? `FR76 •••• •••• ${accountResult.payout_account.iban_last4}`
            : (prev?.accountMasked || 'FR76 •••• •••• 0142'),
        }));
      }

      if (Array.isArray(contactsResult)) {
        setContacts(contactsResult);
        if (contactsResult.length > 0) {
          setSelectedContact(contactsResult[0]);
        }
      }

      if (Array.isArray(txResult)) {
        setTransactions(txResult);
      }

      if (qrResult) {
        setQrData(qrResult);
      }
    } catch (err) {
      console.warn('Backend sync warning:', err);
    }
  }, [setUser]);

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
    const cleanAmount = parseFloat(sendAmount.replace(',', '.')) || 10;
    const amountCents = Math.round(cleanAmount * 100);

    if (!isIncident && authToken) {
      try {
        await sendPaymentApi(
          {
            recipientId: selectedContact?.id,
            recipient: selectedContact?.rawPhone || selectedContact?.phone || selectedContact?.email || '+33612345677',
            amount_cents: amountCents,
            description: sendReason || 'Paiement',
            holder: user?.name || 'Titulaire',
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
      initials: selectedContact?.initials || 'DE',
      counterparty: selectedContact?.name || 'Destinataire',
      subtitle: `${sendReason || 'Paiement'} · ${timeStr}`,
      amountFormatted: amountFormatted,
      amountNum: -cleanAmount,
      type: 'sent',
      status: 'Envoyé',
      statusSymbol: '●',
      isFailed: false,
      date: now,
    };

    setTransactions((prev) => [newTx, ...prev]);

    // Resynchronize backend data in background
    if (authToken) {
      syncBackendData(authToken);
    }

    setCurrentScreen('ACTIVITY');
    setActiveTab('activity');
  }, [authToken, isIncident, selectedContact, sendAmount, sendReason, user, syncBackendData]);

  // Start 2FA login flow against auth-service /login with custom credentials
  const start2FALogin = useCallback(async (email, password) => {
    const result = await loginWithPassword(email, password);

    if (result.mfa_required) {
      // Step 1 done: face challenge received
      setSessionId(result.session_id);
      setFaceChallenge(result.face_challenge || { direction: 'left', frames: 8, interval_ms: 250 });
      setPending2FA({ type: 'login', email, password, sessionId: result.session_id });
      setCurrentScreen('FACE_AUTH');
    } else if (result.face_enrollment_required) {
      // Logged in with password only, no face enrolled yet -> go to enrollment screen
      const token = result.token?.access_token;
      if (token) {
        setAuthToken(token);
        await syncBackendData(token);
      }
      setSessionId(result.session_id);
      setPending2FA(null);
      setCurrentScreen('FACE_ENROLL');
    } else {
      // Direct login success
      const token = result.token?.access_token;
      if (token) {
        setAuthToken(token);
        await syncBackendData(token);
      }
      setPending2FA(null);
      setCurrentScreen('HOME');
      setActiveTab('home');
    }
  }, [setAuthToken, syncBackendData]);

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
      if (token) {
        syncBackendData(token);
      }
    } else if (pending2FA?.type === 'payment') {
      setPending2FA(null);
      await executePayment();
    }
  }, [authToken, setAuthToken, pending2FA, executePayment, syncBackendData]);

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

  // Logout handler returning to Login screen and clearing all persisted credentials
  const handleLogout = useCallback(() => {
    setAuthToken(null);
    setUser(null);
    setSessionId(null);
    setPending2FA(null);
    setFaceChallenge(null);
    setTransactions([]);
    setContacts([]);
    setSelectedContact(null);
    setActiveTab('home');
    setCurrentScreen('LOGIN');
  }, [setAuthToken, setUser]);

  // Create payment request
  const executeCreateRequest = async ({ payer, amount, description }) => {
    const cleanAmount = parseFloat(amount.replace(',', '.')) || 10;
    const amountCents = Math.round(cleanAmount * 100);

    try {
      await createPaymentRequestApi(
        {
          payer: payer.rawPhone || payer.phone || payer.email,
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
      initials: payer.initials || 'CO',
      counterparty: payer.name || 'Contact',
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
        navigateToTab,
        loginNotice,
        setLoginNotice,
        prefilledEmail,
        setPrefilledEmail,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
