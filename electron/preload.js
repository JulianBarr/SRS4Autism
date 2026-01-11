const { contextBridge } = require('electron');

// Expose protected methods that allow the renderer process to use
// ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electron', {
  // Add any APIs you want to expose to the frontend here
  // For now, we'll keep it minimal since the React app communicates
  // with the backend via HTTP
  platform: process.platform,
  isDev: process.env.NODE_ENV === 'development'
});
