import { useState, useEffect, useRef, useCallback } from 'react';

export const useAssemblyLogic = () => {
    // Persistent Settings (Unconditional)
    const [rememberSession, setRememberSession] = useState(() => localStorage.getItem('rememberSession') === 'true');
    const [vaultPath, setVaultPath] = useState(() => localStorage.getItem('vaultPath') || '');
    const [addToExisting, setAddToExisting] = useState(() => localStorage.getItem('addToExisting') === 'true');
    const [stopOnNotFound, setStopOnNotFound] = useState(() => {
        const item = localStorage.getItem('stopOnNotFound');
        return item === null ? true : item === 'true';
    });
    const [dedupe, setDedupe] = useState(() => {
        const item = localStorage.getItem('dedupe');
        return item === null ? true : item === 'true';
    });
    const [multiKitMode, setMultiKitMode] = useState(() => localStorage.getItem('multiKitMode') === 'true');
    const [sapUsername, setSapUsername] = useState(() => localStorage.getItem('sapUsername') || '');
    const [sapPassword, setSapPassword] = useState(() => localStorage.getItem('sapPassword') || '');

    // Batch Settings
    const [batchLayoutFix, setBatchLayoutFix] = useState(() => localStorage.getItem('batchLayoutFix') === 'true');
    const [batchFileNaming, setBatchFileNaming] = useState(() => localStorage.getItem('batchFileNaming') === 'true');
    const [batchMaterialCheck, setBatchMaterialCheck] = useState(() => localStorage.getItem('batchMaterialCheck') === 'true');
    const [batchDuplicateAnalysis, setBatchDuplicateAnalysis] = useState(() => localStorage.getItem('batchDuplicateAnalysis') === 'true');

    // Session Data (Controlled by rememberSession)
    const [codes, setCodes] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('codes') || '' : ''));

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

    // --- IPC Listener for Logs & Results ---
    useEffect(() => {
        let cleanup;
        if (window.electron && window.electron.onLogUpdate) {
            cleanup = window.electron.onLogUpdate((data) => {
                const { message, type } = data;

                // 1. Handle Success Result
                if (message.startsWith('[RESULT_SUCCESS]')) {
                    try {
                        const jsonStr = message.replace('[RESULT_SUCCESS]', '');
                        const result = JSON.parse(jsonStr);
                        setStatus('Tamamlandı');
                        setIsRunning(false);
                        setAlertState({
                            isOpen: true,
                            message: `İşlem Başarıyla Tamamlandı!\nDosya: ${result.file}`,
                            type: 'success'
                        });
                        setStats(prev => ({ ...prev, success: prev.success + 1 }));
                        setLogs(prev => [...prev, { message: "İşlem başarıyla tamamlandı.", timestamp: Date.now() / 1000, color: '#10b981' }]);
                    } catch (e) {
                        console.error("Success Parse Error", e);
                    }
                }
                // 2. Handle Missing Parts Result
                else if (message.startsWith('[RESULT_MISSING]')) {
                    try {
                        const jsonStr = message.replace('[RESULT_MISSING]', '');
                        const missing = JSON.parse(jsonStr);
                        setStatus('Eksik Parça');
                        setIsRunning(false);
                        setAlertState({
                            isOpen: true,
                            message: `${missing.length} adet eksik parça bulundu. Excel dosyası oluşturuldu.`,
                            type: 'warning'
                        });
                        setStats(prev => ({ ...prev, error: prev.error + missing.length }));
                        setLogs(prev => [...prev, { message: `${missing.length} adet eksik parça nedeniyle işlem durduruldu.`, timestamp: Date.now() / 1000, color: '#ef4444' }]);
                    } catch (e) {
                        console.error("Missing Parse Error", e);
                    }
                }
                // 3. Normal Logs
                else {
                    setLogs(prev => [...prev, {
                        message: message,
                        timestamp: Date.now() / 1000,
                        color: type === 'error' ? '#ef4444' : (type === 'system' ? '#3b82f6' : 'var(--text)')
                    }]);

                    // Update status based on log content (optional heuristic)
                    if (message.includes('İşlem başlıyor')) setStatus('Çalışıyor');
                    if (message.includes('Login başarılı')) setStatus('SAP Bağlı');
                }
            });
        }
        return () => {
            if (cleanup) cleanup();
        };
    }, []);

    // Unified Persistence Effect
    useEffect(() => {
        // Always save settings
        localStorage.setItem('rememberSession', rememberSession);
        localStorage.setItem('vaultPath', vaultPath);
        localStorage.setItem('addToExisting', addToExisting);
        localStorage.setItem('stopOnNotFound', stopOnNotFound);
        localStorage.setItem('dedupe', dedupe);
        localStorage.setItem('multiKitMode', multiKitMode);
        localStorage.setItem('sapUsername', sapUsername);
        localStorage.setItem('sapPassword', sapPassword);
        localStorage.setItem('batchLayoutFix', batchLayoutFix);
        localStorage.setItem('batchFileNaming', batchFileNaming);
        localStorage.setItem('batchMaterialCheck', batchMaterialCheck);
        localStorage.setItem('batchDuplicateAnalysis', batchDuplicateAnalysis);

        // Save codes only if rememberSession is true
        if (rememberSession) {
            localStorage.setItem('codes', codes);
        } else {
            localStorage.removeItem('codes');
        }
    }, [rememberSession, codes, addToExisting, stopOnNotFound, dedupe, vaultPath, multiKitMode, sapUsername, sapPassword]);

    // Clear state on mount if persistence is disabled
    useEffect(() => {
        if (!rememberSession) {
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
        if (isRunning) return;

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

        if (multiKitMode && (!sapUsername || !sapPassword)) {
            setAlertState({ isOpen: true, message: "Çoklu Kit Modu için SAP Kullanıcı Adı ve Şifresi gereklidir.", type: 'error' });
            setShowSettings(true);
            return;
        }

        // Reset and Start
        setLogs([{ message: "İşlem başlatılıyor...", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
        setStats({ total: codeList.length, success: 0, error: 0 });
        setIsRunning(true);
        setStatus('Başlatılıyor...');

        // Prepare Data
        const processData = {
            kits: codeList,
            vaultPath,
            sapUsername,
            sapPassword,
            addToExisting,
            stopOnNotFound
        };

        if (window.electron && window.electron.startProcess) {
            window.electron.startProcess(processData);
        } else {
            console.error("Electron API not found");
            setLogs(prev => [...prev, { message: "Hata: Electron API bulunamadı.", timestamp: Date.now() / 1000, color: '#ef4444' }]);
            setIsRunning(false);
        }

    }, [isRunning, vaultPath, codes, dedupe, addToExisting, stopOnNotFound, multiKitMode, sapUsername, sapPassword]);

    const handleStop = useCallback(() => {
        if (window.electron && window.electron.stopProcess) {
            window.electron.stopProcess();
            setLogs(prev => [...prev, { message: "Durdurma isteği gönderildi...", timestamp: Date.now() / 1000, color: '#f59e0b' }]);
        }
    }, []);

    const handleClear = useCallback(() => {
        setCodes('');
        setLogs([{ message: "Kayıtlar temizlendi.", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
        setStats({ total: 0, success: 0, error: 0 });
        setProgress(0);
        setStatus('Hazır');
    }, []);

    const handleSelectFolder = useCallback(async () => {
        if (window.electron) {
            const path = await window.electron.selectFolder();
            if (path) {
                setVaultPath(path);
                setHighlightVaultSettings(false);
            }
        }
    }, []);

    return {
        rememberSession, setRememberSession,
        vaultPath, setVaultPath,
        codes, setCodes,
        addToExisting, setAddToExisting,
        stopOnNotFound, setStopOnNotFound,
        dedupe, setDedupe,
        multiKitMode, setMultiKitMode,
        sapUsername, setSapUsername,
        sapPassword, setSapPassword,
        status, progress, logs, isRunning, isPaused, stats,
        alertState, setAlertState,
        showSettings, setShowSettings,
        highlightVaultSettings, setHighlightVaultSettings,
        logsEndRef,
        handleStart,
        handleStop,
        handleClear,
        handleSelectFolder,
        // Batch Settings Exports
        batchLayoutFix, setBatchLayoutFix,
        batchFileNaming, setBatchFileNaming,
        batchMaterialCheck, setBatchMaterialCheck,
        batchDuplicateAnalysis, setBatchDuplicateAnalysis
    };
};
