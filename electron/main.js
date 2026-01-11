const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');

let mainWindow;
let backendProcess;
const BACKEND_PORT = 8000;
const isDev = process.env.NODE_ENV === 'development';

// Check if backend is running on port
function isBackendRunning(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();

    socket.setTimeout(1000);

    socket.on('connect', () => {
      socket.destroy();
      resolve(true); // Successfully connected, backend is running
    });

    socket.on('error', () => {
      socket.destroy();
      resolve(false); // Cannot connect, backend not running
    });

    socket.on('timeout', () => {
      socket.destroy();
      resolve(false); // Timeout, backend not running
    });

    socket.connect(port, '127.0.0.1');
  });
}

// Wait for the backend to be ready
async function waitForBackend(maxRetries = 30, retryInterval = 1000) {
  console.log(`Waiting for backend on port ${BACKEND_PORT}...`);

  for (let i = 0; i < maxRetries; i++) {
    const isRunning = await isBackendRunning(BACKEND_PORT);
    if (isRunning) {
      console.log('Backend is ready!');
      return true;
    }
    console.log(`Backend not ready yet, retrying... (${i + 1}/${maxRetries})`);
    await new Promise(resolve => setTimeout(resolve, retryInterval));
  }

  console.error('Backend failed to start within the expected time');
  return false;
}

// Spawn the Python backend process
function startBackend() {
  return new Promise((resolve, reject) => {
    let backendPath;

    if (isDev) {
      // In development, run the Python script directly
      backendPath = path.join(__dirname, '..', 'backend', 'run.py');
      console.log(`Starting backend in dev mode: python ${backendPath}`);
      backendProcess = spawn('python', [backendPath], {
        cwd: path.join(__dirname, '..', 'backend'),
        env: { ...process.env }
      });
    } else {
      // In production, run the compiled executable
      const exeName = process.platform === 'win32' ? 'api.exe' : 'api';
      backendPath = path.join(process.resourcesPath, 'backend-dist', exeName);
      console.log(`Starting backend in production mode: ${backendPath}`);
      backendProcess = spawn(backendPath, [], {
        cwd: path.join(process.resourcesPath, 'backend-dist'),
        env: { ...process.env }
      });
    }

    backendProcess.stdout.on('data', (data) => {
      console.log(`Backend stdout: ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
      console.error(`Backend stderr: ${data}`);
    });

    backendProcess.on('error', (error) => {
      console.error(`Failed to start backend: ${error}`);
      reject(error);
    });

    backendProcess.on('close', (code) => {
      console.log(`Backend process exited with code ${code}`);
      if (code !== 0 && code !== null) {
        reject(new Error(`Backend exited with code ${code}`));
      }
    });

    // Give the process a moment to start
    setTimeout(() => resolve(), 1000);
  });
}

// Stop the backend process
function stopBackend() {
  if (backendProcess) {
    console.log('Stopping backend process...');
    backendProcess.kill();
    backendProcess = null;
  }
}

// Create the main application window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true
    },
    show: false // Don't show until ready
  });

  // Load the app
  if (isDev) {
    // In development, load from the React dev server
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    // In production, load from the built files
    mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'build', 'index.html'));
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Clean up when window is closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
app.on('ready', async () => {
  try {
    // Start the backend
    await startBackend();

    // Wait for backend to be ready
    const backendReady = await waitForBackend();

    if (!backendReady) {
      console.error('Backend failed to start, exiting...');
      app.quit();
      return;
    }

    // Create the window
    createWindow();
  } catch (error) {
    console.error('Error during startup:', error);
    app.quit();
  }
});

// Quit when all windows are closed
app.on('window-all-closed', () => {
  stopBackend();
  app.quit();
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// Clean up on exit
app.on('before-quit', () => {
  stopBackend();
});

process.on('exit', () => {
  stopBackend();
});
