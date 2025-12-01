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
    width: 1300,
    height: 800,
    minWidth: 1300,
    minHeight: 800,
    frame: false,
    transparent: true,
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

ipcMain.handle('select-folder', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});
