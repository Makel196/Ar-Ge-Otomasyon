const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let pythonProcess;

const isDev = process.env.NODE_ENV === 'development';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 800,
    minWidth: 1300,
    minHeight: 800,
    frame: false, // We use hidden titleBarStyle for custom background + native buttons
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#00000000', // Transparent background
      symbolColor: '#64748b', // Slate-500 for symbols
      height: 32
    },
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: isDev ? path.join(__dirname, '../../logo.ico') : path.join(__dirname, '../dist/logo.ico'),
    backgroundColor: '#e0e5ec', // Light bg default
    title: "Ar-Ge Otomasyon"
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    // mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // Window controls
  ipcMain.on('minimize-window', () => mainWindow.minimize());
  ipcMain.on('maximize-window', () => {
    if (mainWindow.isMaximized()) mainWindow.unmaximize();
    else mainWindow.maximize();
  });
  ipcMain.on('close-window', () => mainWindow.close());

  ipcMain.handle('select-folder', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory']
    });
    return result.filePaths[0];
  });
}

function startPythonBackend() {
  let backendPath;
  let command;
  let args;

  if (app.isPackaged) {
    // In production, use the compiled executable in resources
    backendPath = path.join(process.resourcesPath, 'backend.exe');
    command = backendPath;
    args = [];
    console.log('Starting packaged Python backend from:', backendPath);
  } else {
    // In development, use the python script
    backendPath = path.join(__dirname, '../../backend/server.py');
    command = 'python';
    args = [backendPath];
    console.log('Starting development Python backend from:', backendPath);
  }

  pythonProcess = spawn(command, args);

  pythonProcess.stdout.on('data', (data) => {
    console.log(`Python stdout: ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python stderr: ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
