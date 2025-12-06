import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:5000/api';

const STATUS = {
  READY: 'Hazır',
  STARTING: 'Başlatılıyor...',
  RUNNING: 'Çalışıyor',
  PAUSED: 'Duraklatıldı',
  STOPPED: 'Durduruldu',
  RESUMING: 'Devam ediyor',
  DONE: 'Tamamlandı',
  ERROR: 'Hata'
};

export const useAssemblyLogic = () => {
  // Persistent Settings
  const [rememberSession, setRememberSession] = useState(() => localStorage.getItem('rememberSession') === 'true');
  const [vaultPath, setVaultPath] = useState(() => localStorage.getItem('vaultPath') || '');

  // State with optional persistence
  const [codes, setCodes] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('codes') || '' : ''));

  // Settings with optional persistence
  // Settings - Always Persistent
  const [addToExisting, setAddToExisting] = useState(() => {
    if (localStorage.getItem('rememberSession') === 'true') {
      return localStorage.getItem('addToExisting') === 'true';
    }
    return false;
  });
  const [stopOnNotFound, setStopOnNotFound] = useState(() => {
    if (localStorage.getItem('rememberSession') === 'true') {
      const saved = localStorage.getItem('stopOnNotFound');
      return saved !== null ? saved === 'true' : true;
    }
    return true;
  });
  const [dedupe, setDedupe] = useState(() => {
    if (localStorage.getItem('rememberSession') === 'true') {
      const saved = localStorage.getItem('dedupe');
      return saved !== null ? saved === 'true' : true;
    }
    return true;
  });
  const [multiKitMode, setMultiKitMode] = useState(() => localStorage.getItem('multiKitMode') === 'true');
  const [sapUsername, setSapUsername] = useState(() => localStorage.getItem('sapUsername') || '');
  const [sapPassword, setSapPassword] = useState(() => localStorage.getItem('sapPassword') || '');
  const [assemblySavePath, setAssemblySavePath] = useState(() => localStorage.getItem('assemblySavePath') || '');
  const [batchRenameMode, setBatchRenameMode] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('batchRenameMode') === 'true' : false));
  const [batchFixDataCardMode, setBatchFixDataCardMode] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('batchFixDataCardMode') === 'true' : false));
  const [batchFileLayoutMode, setBatchFileLayoutMode] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('batchFileLayoutMode') === 'true' : false));
  const [batchAssemblyWeightCorrectionMode, setBatchAssemblyWeightCorrectionMode] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('batchAssemblyWeightCorrectionMode') === 'true' : false));
  const [batchDuplicateCodeCheckMode, setBatchDuplicateCodeCheckMode] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('batchDuplicateCodeCheckMode') === 'true' : false));
  const [batchSettingsUnlocked, setBatchSettingsUnlocked] = useState(() => (localStorage.getItem('rememberSession') === 'true' ? localStorage.getItem('batchSettingsUnlocked') === 'true' : false));

  // Volatile State
  const [status, setStatus] = useState(STATUS.READY);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState(() => {
    if (localStorage.getItem('rememberSession') === 'true') {
      try {
        const saved = localStorage.getItem('savedLogs');
        return saved ? JSON.parse(saved) : [];
      } catch (e) {
        return [];
      }
    }
    return [];
  });
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [stats, setStats] = useState({ total: 0, success: 0, error: 0 });
  const [alertState, setAlertState] = useState({ isOpen: false, message: '', type: 'info' });
  const [confirmState, setConfirmState] = useState({ isOpen: false, message: '', type: 'warning', onConfirm: null });
  const [showSettings, setShowSettings] = useState(false);
  const [highlightVaultSettings, setHighlightVaultSettings] = useState(false);
  const [invalidCodes, setInvalidCodes] = useState([]);

  const logsEndRef = useRef(null);
  const lastLogIndexRef = useRef(0);
  const settingsBackup = useRef({});
  const startInFlightRef = useRef(false);

  const normalizeLog = (log) => {
    if (!log || typeof log.message !== 'string') return log;
    let message = log.message;
    let color = log.color;

    const lower = message.toLowerCase();
    if (lower.includes('durdurma iste')) {
      message = 'İşlem durduruldu.';
      color = '#f97316';
    }
    message = message.replace('??lem', 'İşlem');

    return { ...log, message, color };
  };

  const applyLogImpact = (msg) => {
    const lower = (msg || '').toLowerCase();
    if (lower.includes('başarıyla tamamlandı')) {
      setIsRunning(false);
      setIsPaused(false);
      setStatus(STATUS.DONE);
    } else if (lower.includes('durduruldu') || lower.includes('sonlandırılıyor')) {
      setIsRunning(false);
      setIsPaused(false);
      setStatus(STATUS.STOPPED);
    } else if (lower.includes('duraklatıldı')) {
      setIsRunning(true);
      setIsPaused(true);
      setStatus(STATUS.PAUSED);
    } else if (lower.includes('devam ediyor') || lower.includes('devam ettiriliyor')) {
      setIsRunning(true);
      setIsPaused(false);
      setStatus(STATUS.RESUMING);
    } else if (lower.includes('başlatılıyor')) {
      setIsRunning(true);
      setIsPaused(false);
      setStatus(STATUS.STARTING);
    } else if (lower.includes('hata') || lower.includes('başarısız')) {
      setStatus(STATUS.ERROR);
    }
  };

  // Poll status
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${API_URL}/status`, {
          params: { since: lastLogIndexRef.current }
        });

        const data = res.data;

        // Sync running/paused/status from backend
        const isFinishedStatus = data.status === STATUS.DONE || data.status === STATUS.STOPPED || data.status === STATUS.ERROR || data.status === 'İptal';

        if (data.is_running && !isFinishedStatus) {
          setIsRunning(true);
          setIsPaused(!!data.is_paused);
          if (data.is_paused) {
            setStatus(STATUS.PAUSED);
          } else {
            setStatus(data.status || STATUS.RUNNING);
          }
        } else {
          setIsRunning(false);
          setIsPaused(false);
          // Status: prefer backend status, else keep READY unless previous was DONE
          setStatus(data.status || STATUS.READY);
        }

        setProgress(data.progress);

        if (data.stats) {
          setStats(data.stats);
        }

        if (data.vault_path && !vaultPath) {
          setVaultPath(data.vault_path);
        }

        if (data.logs && data.logs.length > 0) {
          const normalized = data.logs.map(normalizeLog);
          normalized.forEach((log) => applyLogImpact(log.message));
          setLogs((prev) => {
            const newLogs = [...prev, ...normalized];
            if (rememberSession) {
              localStorage.setItem('savedLogs', JSON.stringify(newLogs));
            }
            return newLogs;
          });
          lastLogIndexRef.current += normalized.length;
        }
      } catch (err) {
        console.error('Polling error', err);
      }
    }, 500);
    return () => clearInterval(interval);
  }, [vaultPath]);

  // Auto-clear logs older than 20 seconds
  useEffect(() => {
    const cleaner = setInterval(() => {
      setLogs(prev => {
        const now = Date.now() / 1000;
        const filtered = prev.filter(log => (now - log.timestamp) <= 20);
        if (filtered.length === prev.length) return prev;

        if (rememberSession) {
          localStorage.setItem('savedLogs', JSON.stringify(filtered));
        }
        return filtered;
      });
    }, 2000);
    return () => clearInterval(cleaner);
  }, [rememberSession]);

  // Auto-save codes if rememberSession is true
  useEffect(() => {
    if (rememberSession) {
      localStorage.setItem('codes', codes);
    }
  }, [codes, rememberSession]);

  // Clear backend state on mount if persistence is disabled
  useEffect(() => {
    if (!rememberSession) {
      const resetSession = async () => {
        try {
          await axios.post(`${API_URL}/stop`);
          await axios.post(`${API_URL}/clear`);
        } catch (err) {
          console.error('Session reset error:', err);
        }
      };
      resetSession();

      resetSession();

      setLogs([]);
      localStorage.removeItem('savedLogs');
      setStats({ total: 0, success: 0, error: 0 });
      setStatus(STATUS.READY);
      setProgress(0);
      setIsRunning(false);
      setIsPaused(false);
    }
  }, []);



  const handleStart = useCallback(async () => {
    if (startInFlightRef.current) return;

    // Toggle pause/resume if already running
    if (isRunning) {
      if (isPaused) {
        try {
          await axios.post(`${API_URL}/resume`);
          setIsPaused(false);
          setStatus(STATUS.RESUMING);
          setStatus(STATUS.RESUMING);
          setLogs((prev) => {
            const newLogs = [...prev, { message: 'İşlem devam ediyor.', timestamp: Date.now() / 1000, color: '#0ea5e9' }];
            if (rememberSession) localStorage.setItem('savedLogs', JSON.stringify(newLogs));
            return newLogs;
          });
        } catch (err) {
          console.error('Resume error', err);
        }
      } else {
        try {
          await axios.post(`${API_URL}/pause`);
          setStatus(STATUS.PAUSED);
          setIsPaused(true);
          setStatus(STATUS.PAUSED);
          setIsPaused(true);
        } catch (err) {
          console.error('Pause error', err);
        }
      }
      return;
    }

    startInFlightRef.current = true;
    setIsPaused(false);
    setLogs(prev => prev); // keep log order untouched

    if (!vaultPath) {
      setAlertState({ isOpen: true, message: 'Lütfen kasa yolu seçiniz.', type: 'error' });
      setShowSettings(true);
      startInFlightRef.current = false;
      return;
    }

    let codeList = codes.split('\n').map((c) => c.trim()).filter((c) => c);
    const originalCount = codeList.length;

    // Check for codes with less than 5 characters
    const shortCodes = codeList.filter(code => code.length < 5);
    if (shortCodes.length > 0) {
      setInvalidCodes(shortCodes);
      const codesList = shortCodes.map(code => `<strong><u style="color: #ef4444; font-weight: 700;">${code}</u></strong>`).join(', ');
      setAlertState({
        isOpen: true,
        message: `SAP Kodu 5 karakterden az olamaz ${codesList} kodlarını düzeltiniz.`,
        type: 'error'
      });
      startInFlightRef.current = false;
      return;
    }
    if (dedupe) {
      codeList = [...new Set(codeList)];
      const duplicateCount = originalCount - codeList.length;
      if (duplicateCount > 0) {
        setLogs((prev) => {
          const newLog = {
            message: `Tekrarlayan ${duplicateCount} adet kod silindi.`,
            timestamp: Date.now() / 1000,
            color: '#f59e0b'
          };
          const newLogs = [...prev, newLog];
          if (rememberSession) {
            localStorage.setItem('savedLogs', JSON.stringify(newLogs));
          }
          return newLogs;
        });
      }
    }

    if (codeList.length === 0) {
      setAlertState({ isOpen: true, message: 'Lütfen SAP kodu giriniz.', type: 'warning' });
      startInFlightRef.current = false;
      return;
    }

    setStats({ total: codeList.length, success: 0, error: 0 });

    setIsRunning(true);
    setStatus(STATUS.STARTING);
    // Don't reset lastLogIndexRef - keep reading from where we left off to preserve log history

    setLogs((prev) => {
      const newLog = { message: 'İşlem başlatılıyor...', timestamp: Date.now() / 1000, color: 'var(--text-secondary)' };
      const newLogs = [...prev, newLog];
      if (rememberSession) {
        localStorage.setItem('savedLogs', JSON.stringify(newLogs));
      }
      return newLogs;
    });

    try {
      await axios.post(`${API_URL}/start`, {
        codes: codeList,
        addToExisting,
        stopOnNotFound,
        multiKitMode,
        sapUsername,
        sapPassword
      });
    } catch (err) {
      setIsRunning(false);
      const errorMessage = err.response?.data?.error || err.response?.data?.message || err.message || 'Bilinmeyen hata';
      setLogs((prev) => {
        const newLogs = [...prev, { message: 'Hata: ' + errorMessage, timestamp: Date.now() / 1000, color: '#ef4444' }];
        if (rememberSession) localStorage.setItem('savedLogs', JSON.stringify(newLogs));
        return newLogs;
      });

      if (errorMessage.toLowerCase().includes('pdm') || errorMessage.toLowerCase().includes('kasa') || errorMessage.toLowerCase().includes('vault')) {
        setAlertState({
          isOpen: true,
          message: errorMessage + "\n\nLütfen Ayarlar'ı açıp Kasa Yolu'nu seçiniz.",
          type: 'error'
        });
        setShowSettings(true);
        setHighlightVaultSettings(true);
      } else {
        setAlertState({ isOpen: true, message: 'Başlatılamadı: ' + errorMessage, type: 'error' });
      }
    } finally {
      startInFlightRef.current = false;
    }
  }, [isRunning, isPaused, vaultPath, codes, dedupe, addToExisting, stopOnNotFound, rememberSession, multiKitMode, sapUsername, sapPassword]);

  const handleStop = useCallback(async () => {
    try {
      await axios.post(`${API_URL}/stop`);
    } catch (err) {
      console.error('Stop API error', err);
    }

    if (window.electron?.stopProcess) {
      window.electron.stopProcess();
    }

    setIsRunning(false);
    setIsPaused(false);
    setStatus(STATUS.STOPPED);
  }, []);

  const handleClear = useCallback(() => {
    setConfirmState({
      isOpen: true,
      message: "Lütfen Excel'e çıkarttığınızdan emin olun!<br/><br/>Temizlemek istediğinize emin misiniz?",
      type: 'warning',
      onConfirm: () => {
        setCodes('');
        const clearLog = { message: 'Kayıtlar temizlendi.', timestamp: Date.now() / 1000, color: 'var(--text-secondary)' };
        setLogs([clearLog]);
        if (rememberSession) {
          localStorage.setItem('savedLogs', JSON.stringify([clearLog]));
        }
        setStats({ total: 0, success: 0, error: 0 });
        lastLogIndexRef.current = 0;
        setProgress(0);
        setStatus(STATUS.READY);
        axios.post(`${API_URL}/clear`);
        setConfirmState({ isOpen: false, message: '', type: 'warning', onConfirm: null });
      }
    });
  }, [rememberSession]);

  const handleSelectFolder = useCallback(async () => {
    if (window.electron) {
      const path = await window.electron.selectFolder();
      if (path) {
        setVaultPath(path);
        await axios.post(`${API_URL}/vault-path`, { path });
        setHighlightVaultSettings(false);
      }
    } else {
      const path = prompt('Lütfen Kasa Yolunu Giriniz:', vaultPath);
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
      dedupe,
      multiKitMode,
      sapUsername,
      sapPassword,
      assemblySavePath,
      batchRenameMode,
      batchFixDataCardMode,
      batchFileLayoutMode,
      batchAssemblyWeightCorrectionMode,
      batchDuplicateCodeCheckMode,
      batchSettingsUnlocked
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
      setMultiKitMode(backup.multiKitMode);
      setSapUsername(backup.sapUsername);
      setSapPassword(backup.sapPassword);
      setAssemblySavePath(backup.assemblySavePath);
      setBatchRenameMode(backup.batchRenameMode);
      setBatchFixDataCardMode(backup.batchFixDataCardMode);
      setBatchFileLayoutMode(backup.batchFileLayoutMode);
      setBatchAssemblyWeightCorrectionMode(backup.batchAssemblyWeightCorrectionMode);
      setBatchDuplicateCodeCheckMode(backup.batchDuplicateCodeCheckMode);
      setBatchSettingsUnlocked(backup.batchSettingsUnlocked);
    }
    setShowSettings(false);
  }, []);

  const saveSettings = useCallback(() => {
    if (multiKitMode) {
      if (!sapUsername || !sapPassword || !assemblySavePath) {
        setAlertState({
          isOpen: true,
          message: 'Çoklu Kit Montajı için SAP Kullanıcı Adı, Şifre ve Montaj Kayıt Yolu zorunludur.',
          type: 'warning'
        });
        return;
      }
    }

    localStorage.setItem('rememberSession', rememberSession);

    // Always save settings regardless of rememberSession
    localStorage.setItem('multiKitMode', multiKitMode);
    localStorage.setItem('sapUsername', sapUsername);
    localStorage.setItem('sapPassword', sapPassword);
    localStorage.setItem('assemblySavePath', assemblySavePath);
    localStorage.setItem('vaultPath', vaultPath);

    if (rememberSession) {
      localStorage.setItem('addToExisting', addToExisting);
      localStorage.setItem('stopOnNotFound', stopOnNotFound);
      localStorage.setItem('dedupe', dedupe);
      localStorage.setItem('codes', codes);
      localStorage.setItem('batchSettingsUnlocked', batchSettingsUnlocked);
      localStorage.setItem('batchRenameMode', batchRenameMode);
      localStorage.setItem('batchFixDataCardMode', batchFixDataCardMode);
      localStorage.setItem('batchFileLayoutMode', batchFileLayoutMode);
      localStorage.setItem('batchAssemblyWeightCorrectionMode', batchAssemblyWeightCorrectionMode);
      localStorage.setItem('batchDuplicateCodeCheckMode', batchDuplicateCodeCheckMode);
    } else {
      localStorage.removeItem('addToExisting');
      localStorage.removeItem('stopOnNotFound');
      localStorage.removeItem('dedupe');
      localStorage.removeItem('codes');
      localStorage.removeItem('savedLogs');
      localStorage.removeItem('batchSettingsUnlocked');
      localStorage.removeItem('batchRenameMode');
      localStorage.removeItem('batchFixDataCardMode');
      localStorage.removeItem('batchFileLayoutMode');
      localStorage.removeItem('batchAssemblyWeightCorrectionMode');
      localStorage.removeItem('batchDuplicateCodeCheckMode');
    }
    setShowSettings(false);
  }, [rememberSession, codes, addToExisting, stopOnNotFound, dedupe, vaultPath, multiKitMode, sapUsername, sapPassword, assemblySavePath, batchRenameMode, batchFixDataCardMode, batchFileLayoutMode, batchAssemblyWeightCorrectionMode, batchDuplicateCodeCheckMode, batchSettingsUnlocked]);

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
    assemblySavePath, setAssemblySavePath,
    batchRenameMode, setBatchRenameMode,
    batchFixDataCardMode, setBatchFixDataCardMode,
    batchFileLayoutMode, setBatchFileLayoutMode,
    batchAssemblyWeightCorrectionMode, setBatchAssemblyWeightCorrectionMode,
    batchDuplicateCodeCheckMode, setBatchDuplicateCodeCheckMode,
    batchSettingsUnlocked, setBatchSettingsUnlocked,
    status, progress, logs, isRunning, isPaused, stats,
    alertState, setAlertState,
    confirmState, setConfirmState,
    showSettings, setShowSettings,
    highlightVaultSettings, setHighlightVaultSettings,
    invalidCodes, setInvalidCodes,
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
