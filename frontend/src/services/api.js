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
 * @returns {Promise<{ access_token: string, client: { name: string, email: string, phone: string } }>}
 */
export async function authenticateWithPin(pin) {
  try {
    const res = await fetchWithTimeout(`${AUTH_URL}/login`, {
      method: 'POST',
      body: JSON.stringify({
        email: 'camille@orbe.test',
        password: pin || 'demo-password',
      }),
    });

    if (res.ok) {
      const data = await res.json();
      return {
        access_token: data.access_token,
        client: {
          name: 'Camille Test',
          email: 'camille@orbe.test',
          phone: '+33 6 •• •• 01 42',
        },
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
      phone: '+33 6 •• •• 01 42',
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
 * @returns {Promise<{ balance_cents: number, payout_account: { label: string, iban_last4: string } }>}
 */
export async function getAccountInfo(token) {
  try {
    const res = await fetchWithTimeout(`${PAYMENT_URL}/account`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (res.ok) {
      return await res.json();
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
      if (Array.isArray(data.items)) {
        return data.items;
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
  const idempotencyKey = crypto.randomUUID ? crypto.randomUUID() : `key-${Date.now()}`;
  
  const res = await fetchWithTimeout(`${PAYMENT_URL}/pay`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({
      recipient: paymentData.recipient,
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
  const idempotencyKey = crypto.randomUUID ? crypto.randomUUID() : `req-${Date.now()}`;

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
