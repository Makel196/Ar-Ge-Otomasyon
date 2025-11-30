import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft, faPlay, faPause, faSquare, faTrash, faCopy, faCheckCircle, faExclamationTriangle, faFolder, faTerminal, faLayerGroup } from '@fortawesome/free-solid-svg-icons';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';

const API_URL = 'http://localhost:5000/api';

const AssemblyWizard = ({ theme, toggleTheme }) => {
    const navigate = useNavigate();
    const [codes, setCodes] = useState('');
    const [status, setStatus] = useState('Hazır');
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState([]);
    const [isRunning, setIsRunning] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [vaultPath, setVaultPath] = useState('');
    const [stats, setStats] = useState({ total: 0, success: 0, error: 0 });

    // Settings
    const [addToExisting, setAddToExisting] = useState(false);
    const [stopOnNotFound, setStopOnNotFound] = useState(true);
    const [dedupe, setDedupe] = useState(true);

    const logsEndRef = useRef(null);
    const lastLogIndexRef = useRef(0);

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

    // Auto scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const handleStart = async () => {
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
            alert("Lütfen kasa yolu seçiniz.");
            return;
        }

        let codeList = codes.split('\n').map(c => c.trim()).filter(c => c);
        if (dedupe) {
            codeList = [...new Set(codeList)];
        }

        if (codeList.length === 0) return;

        // Clear logs locally and on server
        setLogs([{ message: "İşlem başlatılıyor...", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
        setStats({ total: codeList.length, success: 0, error: 0 });
        lastLogIndexRef.current = 0;
        await axios.post(`${API_URL}/clear`);

        try {
            await axios.post(`${API_URL}/start`, {
                codes: codeList,
                addToExisting,
                stopOnNotFound
            });
        } catch (err) {
            setLogs(prev => [...prev, { message: "Hata: " + err.message, timestamp: Date.now() / 1000, color: '#ef4444' }]);
            alert("Başlatılamadı: " + err.message);
        }
    };

    const handleStop = async () => {
        setLogs(prev => [...prev, { message: "Durdurma isteği gönderildi...", timestamp: Date.now() / 1000, color: '#f59e0b' }]);
        await axios.post(`${API_URL}/stop`);
    };

    const handleClear = () => {
        setCodes('');
        setLogs([{ message: "Kayıtlar temizlendi.", timestamp: Date.now() / 1000, color: 'var(--text-secondary)' }]);
        setStats({ total: 0, success: 0, error: 0 });
        lastLogIndexRef.current = 0;
        setProgress(0);
        setStatus('Hazır');
        axios.post(`${API_URL}/clear`);
    };

    const handleSelectFolder = async () => {
        if (window.electron) {
            const path = await window.electron.selectFolder();
            if (path) {
                setVaultPath(path);
                await axios.post(`${API_URL}/vault-path`, { path });
            }
        }
    };

    const copyNotFound = () => {
        const notFound = logs
            .filter(l => l.message.includes('Bulunamadı:'))
            .map(l => l.message.replace('Bulunamadı:', '').trim())
            .join('\n');

        if (notFound) {
            navigator.clipboard.writeText(notFound + " PDM'de yok");
            alert("Kopyalandı!");
        } else {
            alert("Bulunamayan parça yok.");
        }
    };

    // Calculate live count of valid codes
    const liveCount = codes.split('\n').map(c => c.trim()).filter(c => c).length;
    const displayTotal = isRunning ? stats.total : liveCount;

    return (
        <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="responsive-container"
        >

            {/* Sidebar */}
            <motion.div
                initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.1 }}
                className="modern-card sidebar"
                style={{ width: '300px', padding: '30px', display: 'flex', flexDirection: 'column', gap: '30px', flexShrink: 0 }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <button className="modern-btn" onClick={() => navigate('/')} style={{ padding: '10px' }}>
                        <FontAwesomeIcon icon={faArrowLeft} style={{ fontSize: '20px' }} />
                    </button>
                    <h3 style={{ margin: 0, fontSize: '20px', fontWeight: '700' }}>Ayarlar</h3>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div className="setting-item">
                        <label style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '16px',
                            cursor: 'pointer',
                            padding: '12px',
                            borderRadius: '12px',
                            background: addToExisting ? 'rgba(99, 102, 241, 0.1)' : 'var(--bg)',
                            border: addToExisting ? '1px solid #6366f1' : '1px solid var(--border)',
                            transition: 'all 0.2s ease'
                        }}>
                            <input type="checkbox" checked={addToExisting} onChange={e => setAddToExisting(e.target.checked)} style={{ width: '18px', height: '18px', accentColor: '#6366f1' }} />
                            <span style={{ fontSize: '14px', fontWeight: '600', color: addToExisting ? '#6366f1' : 'var(--text)' }}>Mevcut montaja ekle</span>
                        </label>
                    </div>

                    <div className="setting-item">
                        <label style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '16px',
                            cursor: 'pointer',
                            padding: '12px',
                            borderRadius: '12px',
                            background: stopOnNotFound ? 'rgba(99, 102, 241, 0.1)' : 'var(--bg)',
                            border: stopOnNotFound ? '1px solid #6366f1' : '1px solid var(--border)',
                            transition: 'all 0.2s ease'
                        }}>
                            <input type="checkbox" checked={stopOnNotFound} onChange={e => setStopOnNotFound(e.target.checked)} style={{ width: '18px', height: '18px', accentColor: '#6366f1' }} />
                            <span style={{ fontSize: '14px', fontWeight: '600', color: stopOnNotFound ? '#6366f1' : 'var(--text)' }}>Bulunamayan varsa durdur</span>
                        </label>
                    </div>

                    <div className="setting-item">
                        <label style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '16px',
                            cursor: 'pointer',
                            padding: '12px',
                            borderRadius: '12px',
                            background: dedupe ? 'rgba(99, 102, 241, 0.1)' : 'var(--bg)',
                            border: dedupe ? '1px solid #6366f1' : '1px solid var(--border)',
                            transition: 'all 0.2s ease'
                        }}>
                            <input type="checkbox" checked={dedupe} onChange={e => setDedupe(e.target.checked)} style={{ width: '18px', height: '18px', accentColor: '#6366f1' }} />
                            <span style={{ fontSize: '14px', fontWeight: '600', color: dedupe ? '#6366f1' : 'var(--text)' }}>Tekrarlı kodları sil</span>
                        </label>
                    </div>
                </div>

                <div style={{ marginTop: 'auto' }}>
                    <label style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>KASA YOLU</label>
                    <div
                        onClick={handleSelectFolder}
                        className="modern-btn"
                        style={{
                            justifyContent: 'flex-start',
                            background: 'var(--bg)',
                            border: '2px dashed var(--border)',
                            color: vaultPath ? 'var(--text)' : 'var(--text-secondary)'
                        }}
                    >
                        <FontAwesomeIcon icon={faFolder} style={{ fontSize: '18px', color: '#6366f1' }} />
                        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '13px' }}>
                            {vaultPath || "Klasör Seç..."}
                        </span>
                    </div>
                </div>
            </motion.div>

            {/* Main Content */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '24px', minWidth: 0 }}>

                {/* Header */}
                <motion.div
                    initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.2 }}
                    className="modern-card"
                    style={{ padding: '24px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                        <div className="icon-box success">
                            <FontAwesomeIcon icon={faLayerGroup} style={{ fontSize: '28px' }} />
                        </div>
                        <div>
                            <h2 style={{ margin: 0, fontSize: '22px', fontWeight: '700' }}>Montaj Sihirbazı</h2>
                            <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Otomatik Montaj Oluşturucu</span>
                        </div>
                    </div>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: '12px',
                        background: status === 'Hata' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                        padding: '10px 20px', borderRadius: '16px',
                        border: `1px solid ${status === 'Hata' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`
                    }}>
                        {status === 'Hata' ?
                            <FontAwesomeIcon icon={faExclamationTriangle} style={{ fontSize: '20px', color: '#ef4444' }} /> :
                            <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '20px', color: '#10b981' }} />
                        }
                        <span style={{ fontWeight: '700', fontSize: '14px', color: status === 'Hata' ? '#ef4444' : '#10b981' }}>{status}</span>
                    </div>
                </motion.div>

                {/* Stats Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '24px' }}>
                    <motion.div
                        initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.25 }}
                        className="modern-card"
                        style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '20px' }}
                    >
                        <div style={{ width: '50px', height: '50px', borderRadius: '16px', background: 'rgba(59, 130, 246, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3b82f6' }}>
                            <FontAwesomeIcon icon={faLayerGroup} style={{ fontSize: '24px' }} />
                        </div>
                        <div>
                            <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>TOPLAM</span>
                            <span style={{ fontSize: '24px', fontWeight: '800', color: 'var(--text)' }}>{displayTotal}</span>
                        </div>
                    </motion.div>

                    <motion.div
                        initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.3 }}
                        className="modern-card"
                        style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '20px' }}
                    >
                        <div style={{ width: '50px', height: '50px', borderRadius: '16px', background: 'rgba(16, 185, 129, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981' }}>
                            <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '24px' }} />
                        </div>
                        <div>
                            <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>BAŞARILI</span>
                            <span style={{ fontSize: '24px', fontWeight: '800', color: '#10b981' }}>{stats.success}</span>
                        </div>
                    </motion.div>

                    <motion.div
                        initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.35 }}
                        className="modern-card"
                        style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '20px' }}
                    >
                        <div style={{ width: '50px', height: '50px', borderRadius: '16px', background: 'rgba(239, 68, 68, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
                            <FontAwesomeIcon icon={faExclamationTriangle} style={{ fontSize: '24px' }} />
                        </div>
                        <div>
                            <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>HATA</span>
                            <span style={{ fontSize: '24px', fontWeight: '800', color: '#ef4444' }}>{stats.error}</span>
                        </div>
                    </motion.div>
                </div>

                {/* Input & Controls */}
                <div className="responsive-grid">

                    {/* Left: Input */}
                    <motion.div
                        initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.3 }}
                        className="modern-card"
                        style={{ display: 'flex', flexDirection: 'column', padding: '30px', minHeight: '400px' }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
                            <FontAwesomeIcon icon={faTerminal} style={{ fontSize: '20px', color: '#6366f1' }} />
                            <span style={{ fontWeight: '700', fontSize: '16px' }}>SAP Kodları</span>
                        </div>

                        <textarea
                            className="modern-input"
                            value={codes}
                            onChange={e => setCodes(e.target.value)}
                            placeholder="SAP Kodlarını buraya yapıştırın..."
                            style={{
                                flex: 1,
                                resize: 'none',
                                fontSize: '14px',
                                lineHeight: '1.6',
                                border: '2px solid var(--border)',
                                minHeight: '200px'
                            }}
                        />

                        {/* Liquid Bubble Progress Bar */}
                        <div style={{ marginTop: '30px', marginBottom: '30px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px', fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                <span>İlerleme Durumu</span>
                                <span>{Math.round(progress * 100)}%</span>
                            </div>
                            <div className="bubble-progress-container">
                                <div
                                    className="bubble-progress-bar"
                                    style={{ width: `${progress * 100}%` }}
                                >
                                </div>
                            </div>
                        </div>

                        {/* Buttons */}
                        <div style={{ display: 'flex', gap: '16px' }}>
                            <button className="modern-btn primary" onClick={handleStart} style={{ flex: 2, height: '50px', fontSize: '16px' }}>
                                <FontAwesomeIcon
                                    icon={isRunning ? (isPaused ? faPlay : faPause) : faPlay}
                                    style={{ fontSize: '20px', marginRight: '8px' }}
                                />
                                {isRunning ? (isPaused ? "DEVAM ET" : "DURAKLAT") : "BAŞLAT"}
                            </button>
                            <button className="modern-btn" onClick={handleClear} disabled={isRunning} style={{ flex: 1, height: '50px' }}>
                                <FontAwesomeIcon icon={faTrash} style={{ fontSize: '20px' }} />
                            </button>
                            <button className="modern-btn danger" onClick={handleStop} disabled={!isRunning} style={{ flex: 1, height: '50px' }}>
                                <FontAwesomeIcon icon={faSquare} style={{ fontSize: '20px' }} />
                            </button>
                        </div>
                    </motion.div>

                    {/* Right: Logs */}
                    <motion.div
                        initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.4 }}
                        className="modern-card"
                        style={{ display: 'flex', flexDirection: 'column', padding: '30px', minHeight: '400px' }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                            <span style={{ fontWeight: '700', fontSize: '16px' }}>İşlem Kayıtları</span>
                            <button className="modern-btn" onClick={copyNotFound} style={{ padding: '8px 16px', fontSize: '13px', height: 'auto' }}>
                                <FontAwesomeIcon icon={faCopy} style={{ fontSize: '14px', marginRight: '6px' }} /> Kopyala
                            </button>
                        </div>

                        <div style={{
                            flex: 1,
                            padding: '20px',
                            background: 'var(--bg)',
                            borderRadius: '16px',
                            overflowY: 'auto',
                            fontFamily: "'JetBrains Mono', 'Consolas', monospace",
                            fontSize: '13px',
                            border: '1px solid var(--border)',
                            minHeight: '200px'
                        }}>
                            <AnimatePresence>
                                {logs.length === 0 ? (
                                    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', opacity: 0.6, flexDirection: 'column', gap: '10px' }}>
                                        <FontAwesomeIcon icon={faTerminal} style={{ fontSize: '40px', opacity: 0.2 }} />
                                        <span>Henüz işlem kaydı bulunmuyor...</span>
                                    </div>
                                ) : (
                                    logs.map((log, i) => (
                                        <motion.div
                                            key={i}
                                            initial={{ opacity: 0, x: -10 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            style={{
                                                marginBottom: '10px',
                                                color: log.color || 'var(--text)',
                                                display: 'flex',
                                                gap: '16px',
                                                lineHeight: '1.5',
                                                paddingBottom: '10px',
                                                borderBottom: '1px solid rgba(0,0,0,0.03)'
                                            }}
                                        >
                                            <span style={{ opacity: 0.5, minWidth: '70px', fontSize: '12px', paddingTop: '2px' }}>{new Date(log.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                                            <span>{log.message}</span>
                                        </motion.div>
                                    ))
                                )}
                            </AnimatePresence>
                            <div ref={logsEndRef} />
                        </div>
                    </motion.div>

                </div>
            </div>
        </motion.div>
    );
};

export default AssemblyWizard;
