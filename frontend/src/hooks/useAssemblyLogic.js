import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:5000/api';

export const useAssemblyLogic = () => {
    // ==========================================
    // 1. Persistent Settings (LocalStorage)
    // ==========================================
    const [rememberSession, setRememberSession] = useState(() => localStorage.getItem('rememberSession') === 'true');

    // Helper to get initial value based on persistence
    const getPersisted = (key, defaultVal) => {
        if (localStorage.getItem('rememberSession') !== 'true') return defaultVal;
        const item = localStorage.getItem(key);
        if (item === null) return defaultVal;
        if (item === 'true') return true;
        if (item === 'false') return false;
        return item;
    };

    const [vaultPath, setVaultPath] = useState(() => getPersisted('vaultPath', ''));
    const [codes, setCodes] = useState(() => getPersisted('codes', ''));
    const [addToExisting, setAddToExisting] = useState(() => getPersisted('addToExisting', false));
    const [stopOnNotFound, setStopOnNotFound] = useState(() => getPersisted('stopOnNotFound', true));
    const [dedupe, setDedupe] = useState(() => getPersisted('dedupe', true));

    // ==========================================
    // 2. Volatile State (UI State)
    // ==========================================
    const [status, setStatus] = useState('Hazır');
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState([]);
    const [isRunning, setIsRunning] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [stats, setStats] = useState({ total: 0, success: 0, error: 0 });

    // UI Controls
    const [alertState, setAlertState] = useState({ isOpen: false, message: '', type: 'info' });
    const [showSettings, setShowSettings] = useState(false);
    const [highlightVaultSettings, setHighlightVaultSettings] = useState(false);

    // Refs
    const logsEndRef = useRef(null);
    const lastLogIndexRef = useRef(0);

    // CRITICAL: Ref to track if a user command is currently being processed.
    // This prevents the polling interval from overwriting optimistic UI updates
    // while a command is in flight or immediately after.
    const commandProcessingRef = useRef(false);

    // ==========================================
    // 3. Effects
    // ==========================================

    // Polling Effect
    useEffect(() => {
        const interval = setInterval(async () => {
            // Skip polling updates if we are in the middle of a user command
            if (commandProcessingRef.current) return;

            try {
                const res = await axios.get(`${API_URL}/status`, {
                    params: { since: lastLogIndexRef.current }
                });

                const data = res.data;

                // Only update state if we are not processing a command (double check)
                if (!commandProcessingRef.current) {
                    setStatus(data.status);
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
                        setLogs(prev => [...prev, ...data.logs]);
                        lastLogIndexRef.current += data.logs.length;

                        // USER REQUEST: Log kontrol yapısı
                        // Belirli mesajlar geldiğinde durumu resetle
                        const completionMessages = [
                            'Bulunamayan parçalar var, montaj iptal edildi.',
                            'İşlem başarıyla tamamlandı.'
                        ];

                        const hasCompletionMessage = data.logs.some(log =>
                            completionMessages.includes(log.message)
                        );

                        if (hasCompletionMessage) {
                            setIsRunning(false);
                            setIsPaused(false);
                        }
                    }
                }
            } catch (err) {
                console.error("Polling error", err);
            }
        }, 500);
        return () => clearInterval(interval);
    }, [vaultPath]);

    // Persistence Effect
    useEffect(() => {
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
    }, [rememberSession, codes, addToExisting, stopOnNotFound, dedupe, vaultPath]);

    // Cleanup on mount if no persistence
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

    // Auto-scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // ==========================================
    // 4. Action Handlers
    // ==========================================

    // Helper to execute commands safely with optimistic updates and polling suppression
    const executeCommand = async (actionName, optimisticUpdateFn, apiCallFn) => {
        // 1. Lock polling
        commandProcessingRef.current = true;

        try {
            // 2. Optimistic UI Update
            if (optimisticUpdateFn) optimisticUpdateFn();

            // 3. API Call
            await apiCallFn();
        } catch (err) {
            console.error(`${actionName} error:`, err);
            // On error, we might want to revert, but usually the next poll will fix it.
            // For now, just log it.
            const errorMessage = err.response?.data?.error || err.response?.data?.message || err.message || "Bilinmeyen hata";
            setLogs(prev => [...prev, { message: `Hata (${actionName}): ${errorMessage}`, timestamp: Date.now() / 1000, color: '#ef4444' }]);

            // If it was a start command, revert running state
            if (actionName === 'Start') {
                setIsRunning(false);
                setStatus("Hata");
            }
        } finally {
            // 4. Unlock polling after a delay to allow backend state to settle
            setTimeout(() => {
                commandProcessingRef.current = false;
            }, 1000);
        }
    };

    const handleStart = useCallback(async () => {
        // CASE 1: Resume
        if (isRunning && isPaused) {
            executeCommand('Resume',
                () => { setIsPaused(false); setStatus("Çalışıyor"); },
                () => axios.post(`${API_URL}/resume`)
            );
            return;
        }

        // CASE 2: Pause
        if (isRunning && !isPaused) {
            executeCommand('Pause',
                () => { setIsPaused(true); setStatus("Duraklatıldı"); },
                () => axios.post(`${API_URL}/pause`)
            );
            return;
        }

        // CASE 3: Start New
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

        executeCommand('Start',
            () => {
                setLogs([{ message: "İşlem başlatılıyor...", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
                setStats({ total: codeList.length, success: 0, error: 0 });
                lastLogIndexRef.current = 0;
                setIsRunning(true);
                setIsPaused(false);
                setStatus("Başlatılıyor...");
            },
            async () => {
                await axios.post(`${API_URL}/clear`);
                await axios.post(`${API_URL}/start`, {
                    codes: codeList,
                    addToExisting,
                    stopOnNotFound
                });
            }
        );
    }, [isRunning, isPaused, vaultPath, codes, dedupe, addToExisting, stopOnNotFound]);

    const handleStop = useCallback(() => {
        executeCommand('Stop',
            () => {
                setLogs(prev => [...prev, { message: "Durdurma isteği gönderildi...", timestamp: Date.now() / 1000, color: '#f59e0b' }]);
                setIsRunning(false);
                setStatus("Durduruluyor...");
            },
            () => axios.post(`${API_URL}/stop`)
        );
    }, []);

    const handleClear = useCallback(() => {
        executeCommand('Clear',
            () => {
                setCodes('');
                setLogs([{ message: "Kayıtlar temizlendi.", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
                setStats({ total: 0, success: 0, error: 0 });
                lastLogIndexRef.current = 0;
                setProgress(0);
                setStatus('Hazır');
                setIsRunning(false);
                setIsPaused(false);
            },
            () => axios.post(`${API_URL}/clear`)
        );
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
