const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
    minimize: () => ipcRenderer.send('minimize-window'),
    maximize: () => ipcRenderer.send('maximize-window'),
    close: () => ipcRenderer.send('close-window'),
    selectFolder: () => ipcRenderer.invoke('select-folder'),
    saveSettings: (data) => ipcRenderer.send('save-settings', data),
    startProcess: (data) => ipcRenderer.send('start-process', data),
    stopProcess: () => ipcRenderer.send('stop-process'),
    onLogUpdate: (callback) => {
        const subscription = (_, data) => callback(data);
        ipcRenderer.on('log-update', subscription);
        return () => ipcRenderer.removeListener('log-update', subscription);
    },
    getWindowState: () => ipcRenderer.invoke('get-window-state'),
    onWindowStateChange: (callback) => {
        if (typeof callback !== 'function') return () => {};
        const listener = (_event, state) => callback(state);
        ipcRenderer.on('window-state', listener);
        return () => ipcRenderer.removeListener('window-state', listener);
    }
});
