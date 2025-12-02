
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// --- Python Process Manager ---
class PythonProcessManager {
  constructor() {
    this.process = null;
  }

  start() {
    if (this.process) {
      console.log('Python process is already running.');
      return;
    }

    let backendPath;
    let command;
    let args;

    if (app.isPackaged) {
      // Production: Use the compiled executable
      backendPath = path.join(process.resourcesPath, 'backend.exe');
      command = backendPath;
      args = [];
      console.log('Starting packaged Python backend from:', backendPath);
    } else {
      // Development: Use the python script
      // Assuming main.cjs is in frontend/electron/
      backendPath = path.join(__dirname, '../../backend/server.py');
      command = 'python';
      args = [backendPath];
      console.log('Starting development Python backend from:', backendPath);
    }

    // Spawn the process
    // detached: false ensures the child process is terminated when the parent dies (on Windows mostly)
    // stdio: pipe allows us to capture output
    this.process = spawn(command, args, {
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    this.process.stdout.on('data', (data) => {
      const output = data.toString();
      // Log to Electron console
      console.log(`[Python]: ${output.trim()}`);
    });

    this.process.stderr.on('data', (data) => {
      const error = data.toString();
      console.error(`[Python Error]: ${error.trim()}`);
    });

    this.process.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
      this.process = null;
    });

    this.process.on('error', (err) => {
      console.error('Failed to start Python process:', err);
    });
  }

  stop() {
    if (this.process) {
      console.log('Stopping Python process...');
      this.process.kill(); // Sends SIGTERM
      this.process = null;
    }
  }
}

// --- Main Window Management ---
let mainWindow;
const pythonManager = new PythonProcessManager();
const isDev = process.env.NODE_ENV === 'development';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 850,
    minWidth: 1000,
    minHeight: 850,
    frame: false,
    transparent: false,
    roundedCorners: false,
    resizable: true,
    maximizable: true,
    minimizable: true,
    movable: true,
    thickFrame: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false // Sometimes needed for complex IPC
    },
    icon: isDev ? path.join(__dirname, '../../logo.ico') : path.join(__dirname, '../dist/logo.ico'),
    backgroundColor: '#00000000',
    title: "Ar-Ge Otomasyon"
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    // mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Window state events for renderer UI (maximize/restore icon)
  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window-state', { maximized: true });
  });

  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window-state', { maximized: false });
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// --- App Lifecycle ---

app.whenReady().then(() => {
  // 1. Start Python Backend
  pythonManager.start();

  // 2. Create Window
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  // Ensure Python process is killed
  pythonManager.stop();
});

// --- IPC Handlers ---

ipcMain.on('minimize-window', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('maximize-window', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) mainWindow.unmaximize();
    else mainWindow.maximize();
  }
});

ipcMain.on('close-window', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle('get-window-state', () => {
  if (!mainWindow) return { maximized: false };
  return {
    maximized: mainWindow.isMaximized()
  };
});

ipcMain.handle('select-folder', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.on('save-settings', (event, data) => {
  console.log('Settings received in Main:', data);
  // Future: Save to file or store
});

ipcMain.on('start-process', (event, data) => {
  console.log('Starting SAP process...');

  // Path to sap_automation.py in backend folder
  const scriptPath = path.join(__dirname, '../../backend/sap_automation.py');

  // Spawn python process
  // We pass '--headless' as an argument to signal the script (if we modify it later)
  const pythonProcess = spawn('python', [scriptPath, '--headless'], {
    stdio: ['pipe', 'pipe', 'pipe']
  });

  // Send data via stdin
  if (pythonProcess.stdin) {
    pythonProcess.stdin.write(JSON.stringify(data));
    pythonProcess.stdin.end();
  }

  // Handle stdout
  pythonProcess.stdout.on('data', (chunk) => {
    const message = chunk.toString();
    console.log('[SAP]:', message);
    if (mainWindow) {
      mainWindow.webContents.send('log-update', { type: 'info', message });
    }
  });

  // Handle stderr
  pythonProcess.stderr.on('data', (chunk) => {
    const message = chunk.toString();
    console.error('[SAP Error]:', message);
    if (mainWindow) {
      mainWindow.webContents.send('log-update', { type: 'error', message });
    }
  });

  pythonProcess.on('close', (code) => {
    console.log(`SAP process exited with code ${code}`);
    if (mainWindow) {
      mainWindow.webContents.send('log-update', { type: 'system', message: `İşlem tamamlandı (Kod: ${code})` });
    }
  });
});

ipcMain.on('stop-process', () => {
  pythonManager.stop();
});
