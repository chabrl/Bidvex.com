/**
 * Extract a user-friendly error message from API error responses
 * Handles various error formats from FastAPI/Pydantic validation
 * 
 * @param {Error} error - The axios error object
 * @returns {string} - A user-friendly error message
 */
export const extractErrorMessage = (error) => {
  // Log full error for debugging
  console.error('API Error:', error);

  if (!error.response) {
    // Network error or no response
    return 'Network error. Please check your connection.';
  }

  const { data } = error.response;

  // Case 1: Simple string detail
  if (typeof data?.detail === 'string') {
    return data.detail;
  }

  // Case 2: Pydantic validation error (array of error objects)
  if (Array.isArray(data?.detail)) {
    // Extract all error messages
    const messages = data.detail
      .map(err => {
        if (typeof err === 'string') return err;
        if (err.msg) {
          // Include field location if available
          const field = err.loc ? err.loc.join('.') : '';
          return field ? `${field}: ${err.msg}` : err.msg;
        }
        return null;
      })
      .filter(Boolean);

    return messages.length > 0 
      ? messages.join(', ') 
      : 'Validation error occurred';
  }

  // Case 3: Single error object (e.g., {type, loc, msg, input, url})
  if (typeof data?.detail === 'object' && data.detail.msg) {
    const field = data.detail.loc ? data.detail.loc.join('.') : '';
    return field ? `${field}: ${data.detail.msg}` : data.detail.msg;
  }

  // Case 3b (iter203): Custom server error envelope { error, message, signals }
  // Used by the vehicle-listing compliance gate. Return the bilingual message
  // so any catch site that doesn't have a custom handler still gets a clean
  // user-facing string instead of a raw JSON dump.
  if (typeof data?.detail === 'object' && data.detail.error && data.detail.message) {
    return data.detail.message;
  }

  // Case 3c (iter400): Bilingual server error envelope
  //   { error, missing, message_en, message_fr, cta_path, ... }
  // Emitted by the Trust Gate (`services/trust_gate.py`) and the rate-limit
  // handler. Rendering the raw object as a React child crashes with
  // "Objects are not valid as a React child (found: object with keys
  // {error, missing, message_en, message_fr, ...})" (React error #31).
  // Prefer French message when the current UI locale is French; fall back
  // to English otherwise.
  if (typeof data?.detail === 'object' && (data.detail.message_en || data.detail.message_fr)) {
    let lang = 'en';
    try {
      if (typeof document !== 'undefined') {
        lang = (document.documentElement.getAttribute('lang')
                || (typeof localStorage !== 'undefined' && localStorage.getItem('i18nextLng'))
                || 'en').toLowerCase().slice(0, 2);
      }
    } catch (_) { /* ignore */ }
    return lang === 'fr'
      ? (data.detail.message_fr || data.detail.message_en)
      : (data.detail.message_en || data.detail.message_fr);
  }

  // Case 4: Error message at root level
  if (data?.message) {
    return data.message;
  }

  // Case 5: Generic error object
  if (typeof data?.detail === 'object') {
    return JSON.stringify(data.detail);
  }

  // Fallback
  return 'An unexpected error occurred';
};

/**
 * Show a toast error with proper message extraction
 * 
 * @param {Error} error - The axios error object
 * @param {string} fallbackMessage - Optional fallback message
 * @param {Function} toastFunction - The toast.error function
 */
export const showErrorToast = (error, fallbackMessage = 'Operation failed', toastFunction) => {
  const message = extractErrorMessage(error);
  toastFunction(message || fallbackMessage);
};
