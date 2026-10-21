/**
 * API client for Orbe backend services.
 * Features automatic resilience fallback when backend is unreachable or returning 5xx.
 * All comments in English only as required.
 */

// Target backend base URLs (can be proxied via Vite in dev or accessed directly)
const AUTH_URL = import.meta.env.VITE_AUTH_URL || '/api/auth';
const PAYMENT_URL = import.meta.env.VITE_PAYMENT_URL || '/api/payments';
const STATUS_URL = import.meta.env.VITE_STATUS_URL || '/api/status';

// Default timeout in milliseconds for network requests (15s to allow Argon2 hashing and ONNX face inference)
const REQUEST_TIMEOUT_MS = 15000;

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
 * Register a new user account against /register.
 *
 * @param {{ email: string, phone: string, display_name: string, password: string }} userData
 * @returns {Promise<{ client_id: string, email: string, phone_masked: string, display_name: string }>}
 */
export async function registerUser({ email, phone, display_name, password }) {
  const res = await fetchWithTimeout(`${AUTH_URL}/register`, {
    method: 'POST',
    body: JSON.stringify({
      email,
      phone,
      display_name,
      password,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = err.detail?.message || "Échec de l'inscription";
    const errorObj = new Error(message);
    errorObj.code = err.detail?.code || 'registration_failed';
    errorObj.status = res.status;
    throw errorObj;
  }

  return await res.json();
}

/**
 * Perform password login step against /login.
 *
 * @param {string} email
 * @param {string} password
 * @returns {Promise<{ mfa_required: boolean, session_id: string, face_challenge?: { direction: string, frames: number, interval_ms: number }, token?: { access_token: string, expires_in: number, factors: string[] }, face_enrollment_required?: boolean }>}
 */
export async function loginWithPassword(email, password) {
  const res = await fetchWithTimeout(`${AUTH_URL}/login`, {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = err.detail?.message || 'Identifiants invalides';
    const errorObj = new Error(message);
    errorObj.code = err.detail?.code || 'invalid_credentials';
    errorObj.status = res.status;
    throw errorObj;
  }

  return await res.json();
}

/**
 * Complete biometric 2FA step against /login/face.
 *
 * @param {string} sessionId
 * @param {string[]} frames Base64 encoded JPEG strings (raw base64, without data: URI prefix)
 * @returns {Promise<{ access_token: string, token_type: string, expires_in: number, factors: string[] }>}
 */
export async function loginFace(sessionId, frames) {
  const res = await fetchWithTimeout(`${AUTH_URL}/login/face`, {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      frames,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = err.detail?.message || 'Visage non reconnu';
    const errorObj = new Error(message);
    errorObj.code = err.detail?.code || 'second_factor_failed';
    errorObj.status = res.status;
    throw errorObj;
  }

  return await res.json();
}

/**
 * Enroll user facial biometric data with explicit GDPR consent.
 *
 * @param {string[]} frames Base64 encoded JPEG strings
 * @param {string} token Bearer access token
 * @returns {Promise<{ enrolled: boolean, templates: number, model: string, consent_at: string }>}
 */
export async function enrollFace(frames, token) {
  const res = await fetchWithTimeout(`${AUTH_URL}/face/enroll`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      consent: true,
      frames,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const message = err.detail?.message || "Échec de l'enregistrement du visage";
    const errorObj = new Error(message);
    errorObj.code = err.detail?.code || 'enrollment_failed';
    errorObj.status = res.status;
    throw errorObj;
  }

  return await res.json();
}

/**
 * Fetch current biometric enrollment status.
 *
 * @param {string} token Bearer access token
 * @returns {Promise<{ enrolled: boolean, templates: number, model: string | null, consent_at: string | null }>}
 */
export async function getFaceEnrollmentStatus(token) {
  const res = await fetchWithTimeout(`${AUTH_URL}/face`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || 'Statut biométrique indisponible');
  }

  return await res.json();
}

/**
 * Helper to fetch /me user profile details.
 *
 * @param {string} token
 * @returns {Promise<{ client_id: string, email: string, phone_masked: string, display_name: string, factors: string[] } | null>}\n */
export async function getMeProfile(token) {
  try {
    const res = await fetchWithTimeout(`${AUTH_URL}/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Non-blocking fallback
  }
  return null;
}

/**
 * Helper generating simulated face frames matching auth-service FakeFaceEngine format.
 * Used for demo bypass or simulated tests.
 *
 * @param {string} identity
 * @param {string} direction 'left' | 'right'
 * @param {number} count
 * @returns {string[]}
 */
export function generateSimulatedLoginFrames(identity = 'camille', direction = 'left', count = 8) {
  const sign = direction === 'left' ? 1 : -1;
  const frames = [];
  for (let i = 0; i < count; i++) {
    const yaw = count > 1 ? sign * (20 * i / (count - 1)) : sign * 15;
    const data = {
      identity,
      yaw: Math.round(yaw * 10) / 10,
      quality: 0.9,
      n: 100 + i,
    };
    frames.push(btoa(JSON.stringify(data)));
  }
  return frames;
}

/**
 * Helper generating simulated enrollment frames matching FakeFaceEngine format.
 * Sweeps from -30deg to +30deg.
 *
 * @param {string} identity
 * @param {number} count
 * @returns {string[]}
 */
export function generateSimulatedEnrollFrames(identity = 'camille', count = 16) {
  const frames = [];
  for (let i = 0; i < count; i++) {
    const yaw = -30 + (60 * i / (count - 1));
    const data = {
      identity,
      yaw: Math.round(yaw * 10) / 10,
      quality: 0.9,
      n: i,
    };
    frames.push(btoa(JSON.stringify(data)));
  }
  return frames;
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
        balance_cents: data.balance_cents ?? 0,
        currency: data.currency || 'EUR',
        payout_account: {
          label: defaultAccount?.label || 'Compte Orbe',
          iban_last4: defaultAccount?.iban_last4 || '',
        },
      };
    }
  } catch {
    // Fallback
  }

  return {
    balance_cents: 0,
    currency: 'EUR',
    payout_account: {
      label: 'Compte Orbe',
      iban_last4: '',
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
      if (Array.isArray(data)) {
        return data.map((c, index) => {
          const name = c.alias || c.display_name || 'Contact';
          const initials = name
            .split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);
          return {
            id: c.contact_id || String(index + 1),
            initials: initials || 'CO',
            name: name,
            phone: c.display_name && c.display_name !== c.alias ? c.display_name : 'Contact Orbe',
            rawPhone: '',
            email: '',
            defaultAmount: '10,00',
            defaultReason: 'Virement',
          };
        });
      }
    }
  } catch {
    // Fallback
  }
  return [];
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

  const isUuid = paymentData.recipientId && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(paymentData.recipientId);
  const target = isUuid
    ? { recipient_contact: paymentData.recipientId }
    : { recipient: paymentData.recipient || paymentData.recipientId || '+33612345677' };

  const res = await fetchWithTimeout(`${PAYMENT_URL}/pay`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({
      ...target,
      amount_cents: paymentData.amount_cents,
      currency: 'EUR',
      description: paymentData.description || 'Paiement',
      card: {
        number: '4242 4242 4242 4242',
        exp_month: 12,
        exp_year: 2030,
        cvc: '123',
        holder: paymentData.holder || 'Client Orbe',
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
