import axios from 'axios';

// Local engine (business logic) — keep in sync with CRA env
export const API_BASE = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

// Cloud control plane (auth, admin, …)
export const CLOUD_API_BASE =
  process.env.REACT_APP_CLOUD_API_URL || 'http://127.0.0.1:8080';

/** Axios instance for port 8000; attaches Bearer token from localStorage. */
export const businessApi = axios.create({
  baseURL: API_BASE,
});

businessApi.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let businessApiAuthRedirectScheduled = false;
function clearAuthAndReloadToLogin() {
  if (businessApiAuthRedirectScheduled) return;
  businessApiAuthRedirectScheduled = true;
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_info');
  window.location.href = '/';
}

businessApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuthAndReloadToLogin();
    }
    return Promise.reject(error);
  }
);

// Create Cloud API Instance
export const cloudApi = axios.create({
  baseURL: CLOUD_API_BASE,
});

// Setup axios interceptor for JWT on Cloud API
cloudApi.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => {
  return Promise.reject(error);
});

// Default export = business API (same as named `businessApi`)
export default businessApi;
