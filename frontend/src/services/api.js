/**
 * API client for Orbe backend services.
 * Features automatic resilience fallback when backend is unreachable or returning 5xx.
 * All comments in English only as required.
 */

// Target backend base URLs (can be proxied via Vite in dev or accessed directly)
const AUTH_URL = import.meta.env.VITE_AUTH_URL || '/api/auth';
const PAYMENT_URL = import.meta.env.VITE_PAYMENT_URL || '/api/payments';
const STATUS_URL = import.meta.env.VITE_STATUS_URL || '/api/status';

// Default timeout in milliseconds for network requests
const REQUEST_TIMEOUT_MS = 2500;

/**
 * Fetch wrapper with timeout and error interception for resilience.
 *
 * @param {string} url
 * @param {RequestInit} options
 * @returns {Promise<Response>}
 */
async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

/**
 * Health check service.
 * Probes the backend to determine if services are operational or in incident state.
 *
 * @returns {Promise<{ operational: boolean, detail: string }>}
 */
export async function checkBackendHealth() {
  try {
    // Try payment service readiness endpoint first
    const paymentReady = await fetchWithTimeout(`${PAYMENT_URL}/health/ready`, { method: 'GET' });
    if (paymentReady.ok) {
      return { operational: true, detail: 'Backend ready' };
    }

    // Try status endpoint or live endpoint
    const statusResp = await fetchWithTimeout(`${STATUS_URL}`, { method: 'GET' });
    if (statusResp.ok) {
      const data = await statusResp.json().catch(() => ({}));
      if (data.status === 'ok' || data.platform === 'operational') {
        return { operational: true, detail: 'Platform operational' };
      }
    }

    return { operational: false, detail: 'Backend returned non-200' };
  } catch (err) {
    // Backend unreachable or timeout -> incident mode
    return { operational: false, detail: err.name === 'AbortError' ? 'Timeout' : 'Network unavailable' };
  }
}

/**
 * Attempt authentication using PIN or fallback to demo account.
 *
 * @param {string} pin
 * @returns {Promise<{ access_token: string, session_id?: string, client: { name: string, email: string, phone: string, accountMasked?: string } }>}
 */
export async function authenticateWithPin(pin) {
  try {
    const res = await fetchWithTimeout(`${AUTH_URL}/login`, {
      method: 'POST',
      body: JSON.stringify({
        email: 'camille@orbe.test',
        password: pin ? 'demo-password' : 'demo-password',
      }),
    });

    if (res.ok) {
      const data = await res.json();
      const accessToken = data.token?.access_token || data.access_token;
      let clientProfile = {
        name: 'Camille Test',
        email: 'camille@orbe.test',
        phone: '+33 6 •• •• •• 78',
      };

      // Try fetching profile details with the issued token
      if (accessToken) {
        try {
          const meRes = await fetchWithTimeout(`${AUTH_URL}/me`, {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          });
          if (meRes.ok) {
            const meData = await meRes.json();
            clientProfile = {
              name: meData.display_name || 'Camille Test',
              email: meData.email || 'camille@orbe.test',
              phone: meData.phone_masked || '+33 6 •• •• •• 78',
            };
          }
        } catch {
          // Keep default profile if /me fails
        }
      }

      return {
        access_token: accessToken || 'fallback-demo-jwt-token',
        session_id: data.session_id,
        client: clientProfile,
      };
    }
  } catch {
    // Fallback smoothly to demo session
  }

  return {
    access_token: 'fallback-demo-jwt-token',
    client: {
      name: 'Camille Test',
      email: 'camille@orbe.test',
      phone: '+33 6 •• •• •• 78',
    },
  };
}

/**
 * Verify biometric 2FA face data against backend.
 * Falls back to realistic simulated biometric analysis if endpoint is unavailable.
 * If in incident mode, simulates 502 error as specified.
 *
 * @param {string} imageBase64
 * @param {string} token
 * @param {boolean} isIncident
 * @returns {Promise<{ success: boolean, confidence?: number, error?: string }>}
 */
export async function verifyFace2FA(imageBase64, token, isIncident = false) {
  if (isIncident) {
    // Simulated delay before returning 502 incident error
    await new Promise((resolve) => setTimeout(resolve, 800));
    return {
      success: false,
      error: "Service d'authentification biométrique indisponible (Erreur 502)",
    };
  }

  try {
    const res = await fetchWithTimeout(`${AUTH_URL}/verify-face`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        image_base64: imageBase64,
        client_name: 'Camille Test',
      }),
    });

    if (res.ok) {
      const data = await res.json();
      return {
        success: true,
        confidence: data.confidence || 98.4,
      };
    }
  } catch {
    // Graceful simulated fallback when endpoint is unavailable
  }

  // Realistic 1.5s simulated image analysis delay
  await new Promise((resolve) => setTimeout(resolve, 1500));

  return {
    success: true,
    confidence: 98.4,
  };
}

/**
 * Fetch linked account information.
 *
 * @param {string} token
 * @returns {Promise<{ balance_cents: number, currency: string, payout_account: { label: string, iban_last4: string } }>}
 */
export async function getAccountInfo(token) {
  try {
    const res = await fetchWithTimeout(`${PAYMENT_URL}/account`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      const data = await res.json();
      const defaultAccount =
        (data.payout_accounts || []).find((a) => a.is_default) || data.payout_accounts?.[0];
      return {
        balance_cents: data.balance_cents ?? 245000,
        currency: data.currency || 'EUR',
        payout_account: {
          label: defaultAccount?.label || 'Banque Démo',
          iban_last4: defaultAccount?.iban_last4 || '0142',
        },
      };
    }
  } catch {
    // Fallback to mock account
  }

  return {
    balance_cents: 245000,
    currency: 'EUR',
    payout_account: {
      label: 'Banque Démo',
      iban_last4: '0142',
    },
  };
}

/**
 * Fetch contacts list from payment service.
 *
 * @param {string} token
 * @returns {Promise<Array | null>}
 */
export async function getContacts(token) {
  try {
    const res = await fetchWithTimeout(`${PAYMENT_URL}/contacts`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        return data.map((c, index) => {
          const name = c.alias || c.display_name || 'Contact';
          const initials = name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);
          const isLea = name.toLowerCase().includes('léa') || name.toLowerCase().includes('lea');
          return {
            id: c.contact_id || String(index + 1),
            initials: initials || 'CT',
            name: name,
            phone: isLea ? '+33 6 •• •• 12 34' : '+33 7 •• •• 56 78',
            rawPhone: isLea ? '+33612345677' : '+33612345676',
            email: isLea ? 'lea@orbe.test' : 'hugo@orbe.test',
            defaultAmount: isLea ? '12,50' : '25,00',
            defaultReason: isLea ? 'Ciné' : 'Pizza vendredi',
          };
        });
      }
    }
  } catch {
    // Fallback handled by caller
  }
  return null;
}

/**
 * Fetch personal QR code payload from payment service.
 *
 * @param {string} token
 * @returns {Promise<{ qr_token: string, payload: string, display_name: string } | null>}
 */
export async function getQrCode(token) {
  try {
    const res = await fetchWithTimeout(`${PAYMENT_URL}/qr`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Fallback handled by caller
  }
  return null;
}

/**
 * Fetch transaction history from backend or fallback to initial dataset.
 *
 * @param {string} token
 * @returns {Promise<Array>}
 */
export async function getTransactions(token) {
  try {
    const res = await fetchWithTimeout(`${PAYMENT_URL}/transactions`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.items) && data.items.length > 0) {
        return data.items.map((item) => {
          const isDebit = item.direction === 'debit';
          const amountEur = (item.amount_cents / 100).toFixed(2).replace('.', ',');
          const formattedAmount = isDebit ? `− ${amountEur} €` : `+ ${amountEur} €`;
          const isFailed = item.status === 'declined' || item.status === 'failed';
          const isRefund = item.type === 'refund';

          let statusLabel = 'Envoyé';
          let statusSymbol = '●';
          if (isFailed) {
            statusLabel = 'Échec';
            statusSymbol = '■';
          } else if (item.direction === 'credit') {
            statusLabel = 'Reçu';
            statusSymbol = '●';
          } else if (isRefund) {
            statusLabel = 'Remboursé';
            statusSymbol = '◇';
          }

          const counterpartyName = item.counterparty || 'Destinataire';
          const initials = counterpartyName
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);

          const txDate = item.created_at ? new Date(item.created_at) : new Date();
          const timeStr = `${String(txDate.getHours()).padStart(2, '0')}:${String(txDate.getMinutes()).padStart(2, '0')}`;

          return {
            id: item.reference || `tx_${Math.random().toString(16).slice(2, 10)}`,
            section: "Aujourd'hui",
            initials: initials || 'CT',
            counterparty: counterpartyName,
            subtitle: `${item.description || 'Paiement'} · ${timeStr}`,
            amountFormatted: formattedAmount,
            amountNum: isDebit ? -(item.amount_cents / 100) : item.amount_cents / 100,
            type: isDebit ? 'sent' : 'received',
            status: statusLabel,
            statusSymbol: statusSymbol,
            isFailed: isFailed,
            date: txDate,
          };
        });
      }
    }
  } catch {
    // Return empty array to use mock dataset
  }
  return [];
}

/**
 * Create a new payment transaction.
 *
 * @param {Object} paymentData
 * @param {string} token
 * @returns {Promise<Object>}
 */
export async function sendPaymentApi(paymentData, token) {
  const idempotencyKey =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `key-${Date.now()}`;

  const recipientTarget = paymentData.recipientId
    ? { recipient_contact: paymentData.recipientId }
    : { recipient: paymentData.recipient || '+33612345677' };

  const res = await fetchWithTimeout(`${PAYMENT_URL}/pay`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({
      ...recipientTarget,
      amount_cents: paymentData.amount_cents,
      currency: 'EUR',
      description: paymentData.description || 'Ciné',
      card: {
        number: '4242 4242 4242 4242',
        exp_month: 12,
        exp_year: 2030,
        cvc: '123',
        holder: 'Camille Test',
      },
    }),
  });

  if (res.ok) {
    return await res.json();
  }
  const errData = await res.json().catch(() => ({}));
  throw new Error(errData.detail?.message || 'Payment rejected by server');
}

/**
 * Create a payment request.
 *
 * @param {Object} requestData
 * @param {string} token
 * @returns {Promise<Object>}
 */
export async function createPaymentRequestApi(requestData, token) {
  const idempotencyKey =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `req-${Date.now()}`;

  const res = await fetchWithTimeout(`${PAYMENT_URL}/requests`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({
      payer: requestData.payer,
      amount_cents: requestData.amount_cents,
      description: requestData.description,
    }),
  });

  if (res.ok) {
    return await res.json();
  }
  const errData = await res.json().catch(() => ({}));
  throw new Error(errData.detail?.message || 'Request creation failed');
}
