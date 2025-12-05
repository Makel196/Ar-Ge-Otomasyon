const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// --- Python Process Manager (long-lived backend) ---
class PythonProcessManager {
  constructor() {
    this.process = null;
  }

  start() {
    if (this.process) {
      console.log('Python süreci zaten çalışıyor.');
      return;
    }

    let backendPath;
    let command;
    let args;

    if (app.isPackaged) {
      backendPath = path.join(process.resourcesPath, 'backend.exe');
      command = backendPath;
      args = [];
      console.log('Paketlenmiş Python backend başlatılıyor:', backendPath);
    } else {
      backendPath = path.join(__dirname, '../../backend/server.py');
      command = 'python';
      args = [backendPath];
      console.log('Geliştirme Python backend başlatılıyor:', backendPath);
    }

    this.process = spawn(command, args, {
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    this.process.stdout.on('data', (data) => {
      console.log(`[Python]: ${data.toString().trim()}`);
    });

    this.process.stderr.on('data', (data) => {
      console.error(`[Python Error]: ${data.toString().trim()}`);
    });

    this.process.on('close', (code) => {
      console.log(`Python süreci kod ${code} ile kapandı`);
      this.process = null;
    });

    this.process.on('error', (err) => {
      console.error('Python süreci başlatılamadı:', err);
    });
  }

  stop() {
    if (this.process) {
      console.log('Python süreci durduruluyor...');
      this.process.kill();
      this.process = null;
    }
  }
}

// --- SAP Automation Runner (per-run) ---
class SapAutomationRunner {
  constructor() {
    this.process = null;
  }

  start(processData, mainWindow) {
    if (this.process) {
      this._sendLog(mainWindow, { type: 'system', message: 'İşlem zaten çalışıyor.' });
      return;
    }

    const scriptPath = path.join(__dirname, '../../backend/sap_automation.py');
    this.process = spawn('python', [scriptPath, '--headless'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    try {
      if (this.process.stdin) {
        this.process.stdin.write(JSON.stringify(processData));
        this.process.stdin.end();
      }
    } catch (err) {
      this._sendLog(mainWindow, { type: 'error', message: `Veri gönderilemedi: ${err.message}` });
    }

    this.process.stdout.on('data', (chunk) => {
      this._sendLog(mainWindow, { type: 'info', message: chunk.toString() });
    });

    this.process.stderr.on('data', (chunk) => {
      this._sendLog(mainWindow, { type: 'error', message: chunk.toString() });
    });

    this.process.on('close', (code) => {
      this._sendLog(mainWindow, { type: 'system', message: `İşlem tamamlandı (Kod: ${code})` });
      this.process = null;
    });

    this.process.on('error', (err) => {
      console.error('[SAP Runner Error]:', err);
      this._sendLog(mainWindow, { type: 'error', message: `Başlatılamadı: ${err.message}` });
      this.process = null;
    });
  }

  stop(mainWindow) {
    if (this.process) {
      const pid = this.process.pid;
      if (process.platform === 'win32') {
        try {
          spawn('taskkill', ['/PID', `${pid}`, '/T', '/F']);
        } catch (err) {
          console.error('taskkill başarısız:', err);
          try { this.process.kill(); } catch { /* ignore */ }
        }
      } else {
        try {
          this.process.kill('SIGKILL');
        } catch {
          this.process.kill();
        }
      }
      this.process = null;
      this._sendLog(mainWindow, { type: 'system', message: 'İşlem durduruldu.' });
    }
  }

  _sendLog(mainWindow, payload) {
    if (!mainWindow) return;
    mainWindow.webContents.send('log-update', payload);
  }
}

// --- Main Window Management ---
let mainWindow;
const pythonManager = new PythonProcessManager();
const sapRunner = new SapAutomationRunner();
const isDev = process.env.NODE_ENV === 'development';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 850,
    minWidth: 1200,
    minHeight: 850,
    frame: false,
    transparent: false,
    resizable: true,
    roundedCorners: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    },
    icon: isDev ? path.join(__dirname, '../../logo.ico') : path.join(__dirname, '../dist/logo.ico'),
    backgroundColor: '#1a1a1a',
    title: "Ar-Ge Otomasyon"
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window-state', { maximized: true });
  });

  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window-state', { maximized: false });
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// --- App Lifecycle ---
app.whenReady().then(() => {
  pythonManager.start();
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
  pythonManager.stop();
  sapRunner.stop(mainWindow);
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
  return { maximized: mainWindow.isMaximized() };
});

ipcMain.handle('select-folder', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.on('save-settings', (_event, data) => {
  console.log('Ayarlar alındı:', data);
});

ipcMain.on('start-process', (_event, data) => {
  sapRunner.start(data, mainWindow);
});

ipcMain.on('stop-process', () => {
  sapRunner.stop(mainWindow);
});
