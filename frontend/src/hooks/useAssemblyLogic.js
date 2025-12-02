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
    const settingsBackup = useRef({});
    const startInFlightRef = useRef(false);

    const applyLogSideEffects = (logMessage) => {
        const lower = (logMessage || '').toLowerCase();
        if (lower.includes('başarıyla tamamlandı')) {
            setIsRunning(false);
            setIsPaused(false);
            setStatus('Tamamlandı');
        } else if (lower.includes('durduruldu')) {
            setIsRunning(false);
            setIsPaused(false);
            setStatus('Durduruldu');
        } else if (lower.includes('duraklatıldı')) {
            setIsPaused(true);
            setStatus('Duraklatıldı');
        } else if (lower.includes('devam ediyor')) {
            setIsPaused(false);
            setStatus('Devam ediyor');
        }
    };

    const normalizeLog = (log) => {
        if (!log || typeof log.message !== 'string') return log;
        let message = log.message;
        let color = log.color;

        const lower = message.toLowerCase();
        if (lower.includes('durdurma iste')) {
            message = 'Durduruldu.';
            color = '#f97316';
        }
        message = message.replace('??lem', 'İşlem');

        return { ...log, message, color };
    };

    // Poll status
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await axios.get(`${API_URL}/status`, {
                    params: { since: lastLogIndexRef.current }
                });

                const data = res.data;
                let incomingStatus = data.status;
                if (data.is_paused) {
                    incomingStatus = 'Duraklatıldı';
                } else if (!data.is_running && incomingStatus && incomingStatus.toLowerCase().includes('parça')) {
                    incomingStatus = 'Durduruldu';
                }
                setStatus(incomingStatus || 'Hazır');
                setProgress(data.progress);
                setIsRunning(data.is_running);
                setIsPaused(data.is_paused);

                if (data.stats) {
                    setStats(data.stats);
                }

                if (data.vault_path && !vaultPath) {
                    setVaultPath(data.vault_path);
                }

                if (data.logs && data.logs.length > 0) {
                    const normalized = data.logs.map(normalizeLog);
                    normalized.forEach(l => applyLogSideEffects(l.message));
                    setLogs(prev => [...prev, ...normalized]);
                    lastLogIndexRef.current += normalized.length;
                }
            } catch (err) {
                console.error("Polling error", err);
            }
        }, 500);
        return () => clearInterval(interval);
    }, [vaultPath]);

    // Manual save/discard removed automatic persistence
    // Settings are only saved when explicitly confirmed

    // Clear backend state on mount if persistence is disabled
    useEffect(() => {
        if (!rememberSession) {
            const resetSession = async () => {
                try {
                    await axios.post(`${API_URL}/stop`);
                    await axios.post(`${API_URL}/clear`);
                } catch (err) {
                    console.error("Session reset error:", err);
                }
            };
            resetSession();

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
        if (startInFlightRef.current) return;

        if (isRunning) {
            if (isPaused) {
                try {
                    await axios.post(`${API_URL}/resume`);
                    setIsPaused(false);
                    setStatus('Devam ediyor');
                    setLogs(prev => [...prev, { message: "İşlem devam ediyor.", timestamp: Date.now() / 1000, color: '#0ea5e9' }]);
                } catch (err) {
                    console.error("Resume error", err);
                }
            } else {
                try {
                    await axios.post(`${API_URL}/pause`);
                    setStatus('Duraklatıldı');
                    setIsPaused(true);
                    setLogs(prev => [...prev, { message: "İşlem duraklatıldı.", timestamp: Date.now() / 1000, color: '#475569' }]);
                } catch (err) {
                    console.error("Pause error", err);
                }
            }
            return;
        }

        startInFlightRef.current = true;
        setIsPaused(false);

        if (!vaultPath) {
            setAlertState({ isOpen: true, message: "Lütfen kasa yolu seçiniz.", type: 'error' });
            setShowSettings(true);
            startInFlightRef.current = false;
            return;
        }

        let codeList = codes.split('\n').map(c => c.trim()).filter(c => c);
        if (dedupe) {
            codeList = [...new Set(codeList)];
        }

        if (codeList.length === 0) {
            setAlertState({ isOpen: true, message: "Lütfen SAP kodu giriniz.", type: 'warning' });
            startInFlightRef.current = false;
            return;
        }

        setLogs(prev => [...prev, { message: "İşlem başlatılıyor...", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
        setStats({ total: codeList.length, success: 0, error: 0 });

        setIsRunning(true);
        setStatus('Başlatılıyor...');

        try {
            await axios.post(`${API_URL}/start`, {
                codes: codeList,
                addToExisting,
                stopOnNotFound
            });
        } catch (err) {
            setIsRunning(false);
            const errorMessage = err.response?.data?.error || err.response?.data?.message || err.message || "Bilinmeyen hata";
            setLogs(prev => [...prev, { message: "Hata: " + errorMessage, timestamp: Date.now() / 1000, color: '#ef4444' }]);

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
        } finally {
            startInFlightRef.current = false;
        }
    }, [isRunning, isPaused, vaultPath, codes, dedupe, addToExisting, stopOnNotFound]);

    const handleStop = useCallback(async () => {
        try {
            await axios.post(`${API_URL}/stop`);
        } catch (err) {
            console.error("Stop API error", err);
        }

        if (window.electron?.stopProcess) {
            window.electron.stopProcess();
        }

        setIsRunning(false);
        setIsPaused(false);
        setStatus('Durduruldu');
        setLogs(prev => [...prev, { message: "İşlem durduruldu.", timestamp: Date.now() / 1000, color: '#f97316' }]);
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
            const path = prompt("Lütfen Kasa Yolunu Giriniz:", vaultPath);
            if (path) {
                setVaultPath(path);
                await axios.post(`${API_URL}/vault-path`, { path });
                setHighlightVaultSettings(false);
            }
        }
    }, [vaultPath]);

    const openSettings = useCallback(() => {
        settingsBackup.current = {
            rememberSession,
            vaultPath,
            addToExisting,
            stopOnNotFound,
            dedupe
        };
        setShowSettings(true);
    }, [rememberSession, vaultPath, addToExisting, stopOnNotFound, dedupe]);

    const discardSettings = useCallback(() => {
        const backup = settingsBackup.current;
        if (backup) {
            setRememberSession(backup.rememberSession);
            setVaultPath(backup.vaultPath);
            setAddToExisting(backup.addToExisting);
            setStopOnNotFound(backup.stopOnNotFound);
            setDedupe(backup.dedupe);
        }
        setShowSettings(false);
    }, []);

    const saveSettings = useCallback(() => {
        localStorage.setItem('rememberSession', rememberSession);

        if (!rememberSession) {
            localStorage.removeItem('codes');
            localStorage.removeItem('addToExisting');
            localStorage.removeItem('stopOnNotFound');
            localStorage.removeItem('dedupe');
            localStorage.removeItem('vaultPath');
        } else {
            localStorage.setItem('codes', codes);
            localStorage.setItem('addToExisting', addToExisting);
            localStorage.setItem('stopOnNotFound', stopOnNotFound);
            localStorage.setItem('dedupe', dedupe);
            localStorage.setItem('vaultPath', vaultPath);
        }
        setShowSettings(false);
    }, [rememberSession, codes, addToExisting, stopOnNotFound, dedupe, vaultPath]);

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
        handleSelectFolder,
        openSettings,
        discardSettings,
        saveSettings
    };
};
