import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:5000/api';

export const useAssemblyLogic = () => {
    // Persistent Settings
    const [rememberSession, setRememberSession] = useState(() => localStorage.getItem('rememberSession') === 'true');
    const [vaultPath, setVaultPath] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('vaultPath') || '' : ''));

    // State with optional persistence
    const [codes, setCodes] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('codes') || '' : ''));

    // Settings with optional persistence
    const [addToExisting, setAddToExisting] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('addToExisting') === 'true' : false));
    const [stopOnNotFound, setStopOnNotFound] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('stopOnNotFound') === 'true' : true));
    const [dedupe, setDedupe] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('dedupe') === 'true' : true));

    // Volatile State
    const [status, setStatus] = useState('Hazır');
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState([]);
    const [isRunning, setIsRunning] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [stats, setStats] = useState({ total: 0, success: 0, error: 0 });
    const [alertState, setAlertState] = useState({ isOpen: false, message: '', type: 'info' });
    const [showSettings, setShowSettings] = useState(false);
    const [highlightVaultSettings, setHighlightVaultSettings] = useState(false);

    const logsEndRef = useRef(null);
    const lastLogIndexRef = useRef(0);

    // Reset stats on mount if session is not persisted
    useEffect(() => {
        if (localStorage.getItem('rememberSession') !== 'true') {
            setStats({ total: 0, success: 0, error: 0 });
        }
    }, []);

    // Poll status
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await axios.get(`${API_URL}/status`, {
                    params: { since: lastLogIndexRef.current }
                });

                const data = res.data;
                setStatus(data.status);
                setProgress(data.progress);
                setIsRunning(data.is_running);
                setIsPaused(data.is_paused);
                if (data.stats) {
                    console.log("Frontend received stats:", data.stats);
                    setStats(data.stats);
                }

                if (data.vault_path && !vaultPath) {
                    setVaultPath(data.vault_path);
                }

                if (data.logs && data.logs.length > 0) {
                    setLogs(prev => [...prev, ...data.logs]);
                    lastLogIndexRef.current += data.logs.length;
                }
            } catch (err) {
                console.error("Polling error", err);
            }
        }, 500);
        return () => clearInterval(interval);
    }, [vaultPath]);

    // Persistence Effects
    useEffect(() => {
        if (rememberSession) {
            localStorage.setItem('vaultPath', vaultPath);
        }
    }, [vaultPath, rememberSession]);

    useEffect(() => {
        localStorage.setItem('rememberSession', rememberSession);
        if (!rememberSession) {
            // Clear volatile settings if persistence is disabled
            localStorage.removeItem('codes');
            localStorage.removeItem('addToExisting');
            localStorage.removeItem('stopOnNotFound');
            localStorage.removeItem('dedupe');
            localStorage.removeItem('vaultPath');
        } else {
            // Save current state if enabled
            localStorage.setItem('codes', codes);
            localStorage.setItem('addToExisting', addToExisting);
            localStorage.setItem('stopOnNotFound', stopOnNotFound);
            localStorage.setItem('dedupe', dedupe);
            localStorage.setItem('vaultPath', vaultPath);
        }
    }, [rememberSession]);

    useEffect(() => {
        if (rememberSession) {
            localStorage.setItem('codes', codes);
        }
    }, [codes, rememberSession]);

    useEffect(() => {
        if (rememberSession) {
            localStorage.setItem('addToExisting', addToExisting);
            localStorage.setItem('stopOnNotFound', stopOnNotFound);
            localStorage.setItem('dedupe', dedupe);
        }
    }, [addToExisting, stopOnNotFound, dedupe, rememberSession]);

    // Clear backend state on mount if persistence is disabled
    useEffect(() => {
        if (!rememberSession) {
            const resetSession = async () => {
                try {
                    // Force stop any running process first
                    await axios.post(`${API_URL}/stop`);
                    // Then clear logs and stats
                    await axios.post(`${API_URL}/clear`);
                } catch (err) {
                    console.error("Session reset error:", err);
                }
            };
            resetSession();

            // Reset frontend state immediately
            setLogs([]);
            setStats({ total: 0, success: 0, error: 0 });
            setStatus('Hazır');
            setProgress(0);
            setIsRunning(false);
            setIsPaused(false);
        }
    }, []);

    // Auto scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const handleStart = useCallback(async () => {
        if (isRunning) {
            if (isPaused) {
                // Resume
                try {
                    await axios.post(`${API_URL}/resume`);
                } catch (err) {
                    console.error("Resume error", err);
                }
            } else {
                // Pause
                try {
                    await axios.post(`${API_URL}/pause`);
                } catch (err) {
                    console.error("Pause error", err);
                }
            }
            return;
        }

        if (!vaultPath) {
            setAlertState({ isOpen: true, message: "Lütfen kasa yolu seçiniz.", type: 'error' });
            setShowSettings(true);
            return;
        }

        let codeList = codes.split('\n').map(c => c.trim()).filter(c => c);
        if (dedupe) {
            codeList = [...new Set(codeList)];
        }

        if (codeList.length === 0) {
            setAlertState({ isOpen: true, message: "Lütfen SAP kodu giriniz.", type: 'warning' });
            return;
        }

        // Clear logs locally and on server
        setLogs([{ message: "İşlem başlatılıyor...", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
        setStats({ total: codeList.length, success: 0, error: 0 });
        lastLogIndexRef.current = 0;

        // Optimistically set running to prevent double clicks
        setIsRunning(true);

        await axios.post(`${API_URL}/clear`);

        try {
            await axios.post(`${API_URL}/start`, {
                codes: codeList,
                addToExisting,
                stopOnNotFound
            });
        } catch (err) {
            setIsRunning(false); // Revert state on error
            const errorMessage = err.response?.data?.error || err.response?.data?.message || err.message || "Bilinmeyen hata";
            setLogs(prev => [...prev, { message: "Hata: " + errorMessage, timestamp: Date.now() / 1000, color: '#ef4444' }]);

            // Check for PDM/Vault errors and open settings
            if (errorMessage.toLowerCase().includes('pdm') || errorMessage.toLowerCase().includes('kasa') || errorMessage.toLowerCase().includes('vault')) {
                setAlertState({
                    isOpen: true,
                    message: errorMessage + "\n\nLütfen Ayarlar'ı açıp Kasa Yolu'nu seçiniz.",
                    type: 'error'
                });
                setShowSettings(true);
                setHighlightVaultSettings(true);
            } else {
                setAlertState({ isOpen: true, message: "Başlatılamadı: " + errorMessage, type: 'error' });
            }
        }
    }, [isRunning, isPaused, vaultPath, codes, dedupe, addToExisting, stopOnNotFound]);

    const handleStop = useCallback(async () => {
        setLogs(prev => [...prev, { message: "Durdurma isteği gönderildi...", timestamp: Date.now() / 1000, color: '#f59e0b' }]);
        await axios.post(`${API_URL}/stop`);
    }, []);

    const handleClear = useCallback(() => {
        setCodes('');
        setLogs([{ message: "Kayıtlar temizlendi.", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
        setStats({ total: 0, success: 0, error: 0 });
        lastLogIndexRef.current = 0;
        setProgress(0);
        setStatus('Hazır');
        axios.post(`${API_URL}/clear`);
    }, []);

    const handleSelectFolder = useCallback(async () => {
        if (window.electron) {
            const path = await window.electron.selectFolder();
            if (path) {
                setVaultPath(path);
                await axios.post(`${API_URL}/vault-path`, { path });
                setHighlightVaultSettings(false);
            }
        } else {
            // Fallback for browser environment
            const path = prompt("Lütfen Kasa Yolunu Giriniz:", vaultPath);
            if (path) {
                setVaultPath(path);
                await axios.post(`${API_URL}/vault-path`, { path });
                setHighlightVaultSettings(false);
            }
        }
    }, [vaultPath]);

    return {
        rememberSession, setRememberSession,
        vaultPath, setVaultPath,
        codes, setCodes,
        addToExisting, setAddToExisting,
        stopOnNotFound, setStopOnNotFound,
        dedupe, setDedupe,
        status, progress, logs, isRunning, isPaused, stats,
        alertState, setAlertState,
        showSettings, setShowSettings,
        highlightVaultSettings, setHighlightVaultSettings,
        logsEndRef,
        handleStart,
        handleStop,
        handleClear,
        handleSelectFolder
    };
};
