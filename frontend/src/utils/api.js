import axios from 'axios';

// Default API Base for Fat Client Backend (Business Logic)
export const API_BASE = 'http://127.0.0.1:8000';

// Cloud API Base for 4A System (Auth, Admin, etc.)
export const CLOUD_API_BASE = 'http://127.0.0.1:8080';

// Create Business API Instance
const businessApi = axios.create({
  baseURL: API_BASE,
});

// Setup axios interceptor for JWT on Business API
businessApi.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, error => {
  return Promise.reject(error);
});

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

export default businessApi;
