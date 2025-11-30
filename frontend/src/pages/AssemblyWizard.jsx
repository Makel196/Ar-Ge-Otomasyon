import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft, faPlay, faPause, faSquare, faTrash, faCopy, faCheckCircle, faExclamationTriangle, faFolder, faTerminal, faLayerGroup, faListOl, faWrench, faCog, faTimes } from '@fortawesome/free-solid-svg-icons';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import PageLayout from '../components/PageLayout';

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
    const [showSettings, setShowSettings] = useState(false);

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
            setShowSettings(true);
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
        <PageLayout>
            {/* Header Section */}
            <motion.div
                initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                    <button
                        className="modern-btn"
                        onClick={() => navigate('/')}
                        style={{ width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}
                    >
                        <FontAwesomeIcon icon={faArrowLeft} style={{ fontSize: '16px' }} />
                    </button>

                    <div style={{ width: '1px', height: '30px', background: 'var(--border)' }}></div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <div className="icon-box success" style={{ width: '40px', height: '40px' }}>
                            <FontAwesomeIcon icon={faWrench} style={{ fontSize: '20px' }} />
                        </div>
                        <div>
                            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '700' }}>Montaj Sihirbazı</h2>
                            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Otomatik Montaj Oluşturucu</span>
                        </div>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: '12px',
                        background: status === 'Hata' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                        padding: '8px 16px', borderRadius: '12px',
                        border: `1px solid ${status === 'Hata' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)'}`
                    }}>
                        {status === 'Hata' ?
                            <FontAwesomeIcon icon={faExclamationTriangle} style={{ fontSize: '16px', color: '#ef4444' }} /> :
                            <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '16px', color: '#10b981' }} />
                        }
                        <span style={{ fontWeight: '700', fontSize: '13px', color: status === 'Hata' ? '#ef4444' : '#10b981' }}>{status}</span>
                    </div>

                    <button
                        className={`modern-btn ${showSettings ? 'primary' : ''}`}
                        onClick={() => setShowSettings(true)}
                        style={{ width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                        <FontAwesomeIcon icon={faCog} style={{ fontSize: '18px' }} />
                    </button>
                </div>
            </motion.div>

            {/* Stats Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', flexShrink: 0 }}>
                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.2 }}
                    className="modern-card"
                    style={{ padding: '15px 20px', display: 'flex', alignItems: 'center', gap: '16px' }}
                >
                    <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(59, 130, 246, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3b82f6' }}>
                        <FontAwesomeIcon icon={faLayerGroup} style={{ fontSize: '18px' }} />
                    </div>
                    <div>
                        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>TOPLAM</span>
                        <span style={{ fontSize: '20px', fontWeight: '800', color: 'var(--text)' }}>{displayTotal}</span>
                    </div>
                </motion.div>

                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.25 }}
                    className="modern-card"
                    style={{ padding: '15px 20px', display: 'flex', alignItems: 'center', gap: '16px' }}
                >
                    <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981' }}>
                        <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '18px' }} />
                    </div>
                    <div>
                        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>BAŞARILI</span>
                        <span style={{ fontSize: '20px', fontWeight: '800', color: '#10b981' }}>{stats.success}</span>
                    </div>
                </motion.div>

                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.3 }}
                    className="modern-card"
                    style={{ padding: '15px 20px', display: 'flex', alignItems: 'center', gap: '16px' }}
                >
                    <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
                        <FontAwesomeIcon icon={faExclamationTriangle} style={{ fontSize: '18px' }} />
                    </div>
                    <div>
                        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>HATA</span>
                        <span style={{ fontSize: '20px', fontWeight: '800', color: '#ef4444' }}>{stats.error}</span>
                    </div>
                </motion.div>
            </div>

            {/* Main Content Grid */}
            <div className="responsive-grid" style={{ flex: 1, minHeight: 0, gap: '20px' }}>
                {/* Input Section */}
                <motion.div
                    initial={{ x: -20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.3 }}
                    className="modern-card"
                    style={{ display: 'flex', flexDirection: 'column', padding: '20px', height: '100%', boxSizing: 'border-box' }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '15px', flexShrink: 0 }}>
                        <FontAwesomeIcon icon={faListOl} style={{ fontSize: '18px', color: '#6366f1' }} />
                        <span style={{ fontWeight: '700', fontSize: '15px' }}>SAP Kodları</span>
                    </div>

                    <textarea
                        className="modern-input"
                        value={codes}
                        onChange={e => setCodes(e.target.value)}
                        placeholder="SAP Kodlarını buraya yapıştırın..."
                        style={{
                            flex: 1,
                            resize: 'none',
                            fontSize: '13px',
                            lineHeight: '1.6',
                            border: '2px solid var(--border)',
                            marginBottom: '15px',
                            minHeight: '0'
                        }}
                    />

                    {/* Progress Bar */}
                    <div style={{ marginBottom: '20px', flexShrink: 0 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)' }}>
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
                    <div style={{ display: 'flex', gap: '12px', flexShrink: 0 }}>
                        <button className="modern-btn primary" onClick={handleStart} style={{ flex: 2, height: '45px', fontSize: '15px' }}>
                            <FontAwesomeIcon
                                icon={isRunning ? (isPaused ? faPlay : faPause) : faPlay}
                                style={{ fontSize: '18px', marginRight: '8px' }}
                            />
                            {isRunning ? (isPaused ? "DEVAM ET" : "DURAKLAT") : "BAŞLAT"}
                        </button>
                        <button className="modern-btn" onClick={handleClear} disabled={isRunning} style={{ flex: 1, height: '45px' }}>
                            <FontAwesomeIcon icon={faTrash} style={{ fontSize: '18px' }} />
                        </button>
                        <button className="modern-btn danger" onClick={handleStop} disabled={!isRunning} style={{ flex: 1, height: '45px' }}>
                            <FontAwesomeIcon icon={faSquare} style={{ fontSize: '18px' }} />
                        </button>
                    </div>
                </motion.div>

                {/* Logs Section */}
                <motion.div
                    initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ delay: 0.4 }}
                    className="modern-card"
                    style={{ display: 'flex', flexDirection: 'column', padding: '20px', height: '100%', boxSizing: 'border-box' }}
                >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexShrink: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <FontAwesomeIcon icon={faTerminal} style={{ fontSize: '18px', color: '#6366f1' }} />
                            <span style={{ fontWeight: '700', fontSize: '15px' }}>İşlem Kayıtları</span>
                        </div>
                        <button className="modern-btn" onClick={copyNotFound} style={{ padding: '6px 12px', fontSize: '12px', height: 'auto' }}>
                            <FontAwesomeIcon icon={faCopy} style={{ fontSize: '13px', marginRight: '6px' }} /> Kopyala
                        </button>
                    </div>

                    <div style={{
                        flex: 1,
                        padding: '15px',
                        background: 'var(--bg)',
                        borderRadius: '12px',
                        overflowY: 'auto',
                        fontFamily: "'JetBrains Mono', 'Consolas', monospace",
                        fontSize: '12px',
                        border: '1px solid var(--border)',
                        minHeight: '0'
                    }}>
                        <AnimatePresence>
                            {logs.length === 0 ? (
                                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', opacity: 0.6, flexDirection: 'column', gap: '10px' }}>
                                    <FontAwesomeIcon icon={faTerminal} style={{ fontSize: '32px', opacity: 0.2 }} />
                                    <span>Henüz işlem kaydı bulunmuyor...</span>
                                </div>
                            ) : (
                                logs.map((log, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        style={{
                                            marginBottom: '8px',
                                            color: log.color || 'var(--text)',
                                            display: 'flex',
                                            gap: '12px',
                                            lineHeight: '1.4',
                                            paddingBottom: '8px',
                                            borderBottom: '1px solid rgba(0,0,0,0.03)'
                                        }}
                                    >
                                        <span style={{ opacity: 0.5, minWidth: '60px', fontSize: '11px', paddingTop: '2px' }}>{new Date(log.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                                        <span>{log.message}</span>
                                    </motion.div>
                                ))
                            )}
                        </AnimatePresence>
                        <div ref={logsEndRef} />
                    </div>
                </motion.div>
            </div>

            {/* Settings Modal */}
            <AnimatePresence>
                {showSettings && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        style={{
                            position: 'fixed',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            background: theme === 'dark' ? 'rgba(15, 23, 42, 0.6)' : 'rgba(0,0,0,0.05)', // Darker overlay in dark mode
                            backdropFilter: 'blur(8px)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 1000,
                        }}
                        onClick={() => setShowSettings(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0, y: 20 }}
                            animate={{ scale: 1, opacity: 1, y: 0 }}
                            exit={{ scale: 0.95, opacity: 0, y: 10 }}
                            transition={{ type: "spring", damping: 25, stiffness: 300 }}
                            onClick={e => e.stopPropagation()}
                            style={{
                                padding: '32px',
                                width: '500px',
                                maxWidth: '90%',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '24px',
                                background: theme === 'dark' ? 'rgba(30, 41, 59, 0.85)' : 'rgba(255, 255, 255, 0.75)',
                                backdropFilter: 'blur(20px) saturate(180%)',
                                borderRadius: '24px',
                                border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(255, 255, 255, 0.8)',
                                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                                color: 'var(--text)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <h3 style={{ margin: 0, fontSize: '22px', fontWeight: '700', letterSpacing: '-0.5px' }}>Ayarlar</h3>
                                <button
                                    onClick={() => setShowSettings(false)}
                                    style={{
                                        background: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
                                        border: 'none',
                                        cursor: 'pointer',
                                        color: 'var(--text)',
                                        width: '32px',
                                        height: '32px',
                                        borderRadius: '50%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        transition: 'all 0.2s'
                                    }}
                                >
                                    <FontAwesomeIcon icon={faTimes} style={{ fontSize: '16px' }} />
                                </button>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                <label style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '16px',
                                    cursor: 'pointer',
                                    padding: '16px',
                                    borderRadius: '16px',
                                    background: addToExisting ? 'rgba(99, 102, 241, 0.15)' : (theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.5)'),
                                    border: addToExisting ? '1px solid rgba(99, 102, 241, 0.3)' : (theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0,0,0,0.05)'),
                                    transition: 'all 0.2s ease'
                                }}>
                                    <div style={{
                                        width: '24px', height: '24px', borderRadius: '6px',
                                        background: addToExisting ? '#6366f1' : (theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'),
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        color: 'white', transition: 'all 0.2s'
                                    }}>
                                        {addToExisting && <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '14px' }} />}
                                    </div>
                                    <input type="checkbox" checked={addToExisting} onChange={e => setAddToExisting(e.target.checked)} style={{ display: 'none' }} />
                                    <span style={{ fontSize: '15px', fontWeight: '600', color: addToExisting ? '#6366f1' : 'var(--text)' }}>Mevcut montaja ekle</span>
                                </label>

                                <label style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '16px',
                                    cursor: 'pointer',
                                    padding: '16px',
                                    borderRadius: '16px',
                                    background: stopOnNotFound ? 'rgba(99, 102, 241, 0.15)' : (theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.5)'),
                                    border: stopOnNotFound ? '1px solid rgba(99, 102, 241, 0.3)' : (theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0,0,0,0.05)'),
                                    transition: 'all 0.2s ease'
                                }}>
                                    <div style={{
                                        width: '24px', height: '24px', borderRadius: '6px',
                                        background: stopOnNotFound ? '#6366f1' : (theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'),
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        color: 'white', transition: 'all 0.2s'
                                    }}>
                                        {stopOnNotFound && <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '14px' }} />}
                                    </div>
                                    <input type="checkbox" checked={stopOnNotFound} onChange={e => setStopOnNotFound(e.target.checked)} style={{ display: 'none' }} />
                                    <span style={{ fontSize: '15px', fontWeight: '600', color: stopOnNotFound ? '#6366f1' : 'var(--text)' }}>Bulunamayan varsa durdur</span>
                                </label>

                                <label style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '16px',
                                    cursor: 'pointer',
                                    padding: '16px',
                                    borderRadius: '16px',
                                    background: dedupe ? 'rgba(99, 102, 241, 0.15)' : (theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.5)'),
                                    border: dedupe ? '1px solid rgba(99, 102, 241, 0.3)' : (theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0,0,0,0.05)'),
                                    transition: 'all 0.2s ease'
                                }}>
                                    <div style={{
                                        width: '24px', height: '24px', borderRadius: '6px',
                                        background: dedupe ? '#6366f1' : (theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'),
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        color: 'white', transition: 'all 0.2s'
                                    }}>
                                        {dedupe && <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '14px' }} />}
                                    </div>
                                    <input type="checkbox" checked={dedupe} onChange={e => setDedupe(e.target.checked)} style={{ display: 'none' }} />
                                    <span style={{ fontSize: '15px', fontWeight: '600', color: dedupe ? '#6366f1' : 'var(--text)' }}>Tekrarlı kodları sil</span>
                                </label>
                            </div>

                            <div>
                                <label style={{ fontSize: '12px', fontWeight: '800', color: 'var(--text-secondary)', display: 'block', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.8 }}>KASA YOLU</label>
                                <div
                                    onClick={handleSelectFolder}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'flex-start',
                                        background: theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.5)',
                                        border: theme === 'dark' ? '2px dashed rgba(255,255,255,0.1)' : '2px dashed rgba(0,0,0,0.1)',
                                        borderRadius: '16px',
                                        color: vaultPath ? 'var(--text)' : 'var(--text-secondary)',
                                        padding: '16px',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s'
                                    }}
                                >
                                    <FontAwesomeIcon icon={faFolder} style={{ fontSize: '20px', color: '#6366f1', marginRight: '12px' }} />
                                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '14px', fontWeight: '500' }}>
                                        {vaultPath || "Klasör Seç..."}
                                    </span>
                                </div>
                            </div>

                            <button
                                className="modern-btn primary"
                                onClick={() => setShowSettings(false)}
                                style={{
                                    marginTop: '10px',
                                    height: '50px',
                                    borderRadius: '16px',
                                    fontSize: '16px',
                                    background: '#6366f1',
                                    boxShadow: '0 10px 20px -5px rgba(99, 102, 241, 0.4)'
                                }}
                            >
                                Kaydet ve Kapat
                            </button>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </PageLayout>
    );
};

export default AssemblyWizard;
