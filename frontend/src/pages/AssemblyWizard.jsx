import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft, faPlay, faPause, faSquare, faTrash, faCopy, faCheckCircle, faExclamationTriangle, faFolder, faTerminal, faLayerGroup, faListOl, faCog, faTimes, faFileExcel, faSave, faQuestionCircle, faInfoCircle, faLock, faUser, faKey, faFolderOpen, faEye, faEyeSlash } from '@fortawesome/free-solid-svg-icons';

import { motion, AnimatePresence } from 'framer-motion';
import * as XLSX from 'xlsx';
import PageLayout from '../components/PageLayout';
import CustomAlert from '../components/CustomAlert';
import ModernTooltip from '../components/ModernTooltip';
import { useAssemblyLogic } from '../hooks/useAssemblyLogic';
import { logoAnimationVariants } from '../constants/animations';

const SettingsToggle = ({ label, checked, onChange, theme, activeColor = '#10b981', tooltip, icon = faCheckCircle, disabled = false }) => (
    <label style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        padding: '0 16px',
        height: '56px',
        borderRadius: '16px',
        background: checked ? `${activeColor}20` : (theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.5)'),
        border: checked ? `1px solid ${activeColor}40` : (theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0,0,0,0.05)'),
        transition: 'all 0.2s ease',
        boxSizing: 'border-box',
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? 'none' : 'auto'
    }}>
        <div style={{
            width: '24px', height: '24px', borderRadius: '6px',
            background: checked ? activeColor : (theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'),
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'white', transition: 'all 0.2s',
            flexShrink: 0
        }}>
            {checked && <FontAwesomeIcon icon={icon} style={{ fontSize: '14px' }} />}
        </div>
        <input type="checkbox" checked={checked} onChange={e => !disabled && onChange(e.target.checked)} style={{ display: 'none' }} disabled={disabled} />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flex: 1 }}>
            <span style={{ fontSize: '14px', fontWeight: '600', color: checked ? activeColor : 'var(--text)' }}>{label}</span>
            {tooltip && (
                <ModernTooltip text={tooltip} theme={theme}>
                    <div style={{ cursor: 'help', opacity: 0.6, display: 'flex', alignItems: 'center' }}>
                        <FontAwesomeIcon icon={faQuestionCircle} style={{ fontSize: '14px' }} />
                    </div>
                </ModernTooltip>
            )}
        </div>
    </label>
);


const AssemblyWizard = ({ theme, toggleTheme }) => {
    const navigate = useNavigate();
    const [showPassword, setShowPassword] = useState(false);
    const [batchPasswordInput, setBatchPasswordInput] = useState('');

    // Use custom hook for logic
    const {
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
    } = useAssemblyLogic();

    const isAnyBatchModeActive = batchRenameMode || batchFixDataCardMode || batchFileLayoutMode || batchAssemblyWeightCorrectionMode || batchDuplicateCodeCheckMode;

    const handleBatchToggle = (newValue, setter) => {
        if (newValue && isAnyBatchModeActive) {
            setAlertState({
                isOpen: true,
                message: 'Aynı anda sadece bir toplu işlem seçilebilir!',
                type: 'error'
            });
            return;
        }
        setter(newValue);
    };

    const handleExportExcel = () => {
        // Filter ONLY for "not found" (bulunamayan)
        const notFoundLogs = logs.filter(log =>
            log.message && log.message.toLowerCase().includes('bulunamadı')
        );

        if (notFoundLogs.length === 0) {
            setAlertState({ isOpen: true, message: "Dışa aktarılacak veri yok.", type: 'info' });
            return;
        }

        // Create worksheet data
        const worksheetData = [
            ["Zaman", "Bulunamayan SAP Kodu Mesajı"],
            ...notFoundLogs.map(log => {
                const time = new Date(log.timestamp * 1000).toLocaleTimeString();
                return [time, log.message];
            })
        ];

        // Create workbook and worksheet
        const wb = XLSX.utils.book_new();
        const ws = XLSX.utils.aoa_to_sheet(worksheetData);

        // Set column widths
        ws['!cols'] = [
            { wch: 12 },  // Zaman column
            { wch: 60 }   // Message column
        ];

        // Add worksheet to workbook
        XLSX.utils.book_append_sheet(wb, ws, "Bulunamayanlar");

        // Generate XLSX file and download
        const today = new Date();
        const day = String(today.getDate()).padStart(2, '0');
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const year = today.getFullYear();
        const filename = `Montaj Sihirbazı - ${day}.${month}.${year}.xlsx`;
        XLSX.writeFile(wb, filename);
    };

    // Calculate live count of valid codes
    const liveCount = codes.split('\n').map(c => c.trim()).filter(c => c).length;
    const displayTotal = isRunning ? stats.total : liveCount;

    const statusTheme = status === 'Hata'
        ? { bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }
        : status === 'Durduruldu'
            ? { bg: 'rgba(249, 115, 22, 0.12)', border: 'rgba(249, 115, 22, 0.35)', color: '#f97316' }
            : status === 'Duraklatıldı'
                ? { bg: 'rgba(148, 163, 184, 0.15)', border: 'rgba(148, 163, 184, 0.3)', color: '#475569' }
                : { bg: 'rgba(16, 185, 129, 0.1)', border: 'rgba(16, 185, 129, 0.2)', color: '#10b981' };

    const getLogIcon = (color) => {
        if (!color) return faInfoCircle;
        const c = color.toLowerCase();
        if (c.includes('#10b981') || c.includes('#2cc985')) return faCheckCircle;
        if (c.includes('#ef4444')) return faExclamationTriangle;
        if (c.includes('#f59e0b')) return faExclamationTriangle;
        return faInfoCircle;
    };

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
                        <motion.div
                            style={{ width: '50px', height: '50px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            variants={logoAnimationVariants}
                            whileHover="hover"
                        >
                            <img src="./mslogo.png" alt="Montaj Sihirbazı" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        </motion.div>
                        <div>
                            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '700' }}>Montaj Sihirbazı</h2>
                            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Otomatik Montaj Oluşturucu</span>
                        </div>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: '12px',
                        background: statusTheme.bg,
                        padding: '8px 16px', borderRadius: '12px',
                        border: `1px solid ${statusTheme.border}`
                    }}>
                        {status === 'Hata' ?
                            <FontAwesomeIcon icon={faExclamationTriangle} style={{ fontSize: '16px', color: '#ef4444' }} /> :
                            <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '16px', color: statusTheme.color }} />
                        }
                        <span style={{ fontWeight: '700', fontSize: '13px', color: statusTheme.color }}>{status}</span>
                    </div>

                    <button
                        className={`modern-btn ${showSettings ? 'primary' : ''}`}
                        onClick={openSettings}
                        style={{ width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                        <FontAwesomeIcon icon={faCog} style={{ fontSize: '18px' }} />
                    </button>
                </div>
            </motion.div>

            {/* Stats Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', flexShrink: 0 }}>
                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{
                        scale: 1,
                        opacity: 1,
                        transition: { delay: 0.2, duration: 0.3 }
                    }}

                    className="modern-card"
                    style={{ padding: '15px 20px', display: 'flex', alignItems: 'center', gap: '16px', cursor: 'default' }}
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
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{
                        scale: 1,
                        opacity: 1,
                        transition: { delay: 0.25, duration: 0.3 }
                    }}

                    className="modern-card"
                    style={{ padding: '15px 20px', display: 'flex', alignItems: 'center', gap: '16px', cursor: 'default' }}
                >
                    <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981' }}>
                        <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '18px' }} />
                    </div>
                    <div>
                        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>BULUNDU</span>
                        <span style={{ fontSize: '20px', fontWeight: '800', color: '#10b981' }}>{stats.success}</span>
                    </div>
                </motion.div>

                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{
                        scale: 1,
                        opacity: 1,
                        transition: { delay: 0.3, duration: 0.3 }
                    }}

                    className="modern-card"
                    style={{ padding: '15px 20px', display: 'flex', alignItems: 'center', gap: '16px', cursor: 'default' }}
                >
                    <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444' }}>
                        <FontAwesomeIcon icon={faExclamationTriangle} style={{ fontSize: '18px' }} />
                    </div>
                    <div>
                        <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)', display: 'block', marginBottom: '2px' }}>BULUNAMADI</span>
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
                        <button
                            className={`modern-btn ${isRunning ? (isPaused ? 'success' : 'secondary') : 'primary'}`}
                            onClick={handleStart}
                            style={{ flex: 2, height: '45px', fontSize: '15px' }}
                        >
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
                        <motion.button
                            initial="idle"
                            whileHover="hover"
                            onClick={handleExportExcel}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '8px',
                                borderRadius: '8px',
                                overflow: 'hidden'
                            }}
                        >
                            <FontAwesomeIcon icon={faFileExcel} style={{ fontSize: '20px', color: '#10b981' }} />
                            <motion.span
                                variants={{
                                    idle: { width: 0, opacity: 0, display: 'none', transition: { duration: 1.5 } },
                                    hover: { width: 'auto', opacity: 1, display: 'block', transition: { duration: 1.5 } }
                                }}
                                style={{ whiteSpace: 'nowrap', fontSize: '15px', fontWeight: '600', color: '#10b981' }}
                            >
                                Excel'e Çıkart
                            </motion.span>
                        </motion.button>
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
                                            borderBottom: theme === 'dark' ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.05)',
                                            alignItems: 'flex-start'
                                        }}
                                    >
                                        <span style={{ opacity: 0.5, minWidth: '60px', fontSize: '11px', paddingTop: '2px', flexShrink: 0 }}>{new Date(log.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                                        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                                            <FontAwesomeIcon icon={getLogIcon(log.color)} style={{ fontSize: '14px', marginTop: '2px', opacity: 0.8 }} />
                                            <span>{log.message}</span>
                                        </div>
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
                            background: theme === 'dark' ? 'rgba(15, 23, 42, 0.6)' : 'rgba(0,0,0,0.05)',
                            backdropFilter: 'blur(8px)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 1000,
                        }}
                        onClick={discardSettings}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0, y: 20 }}
                            animate={{ scale: 1, opacity: 1, y: 0 }}
                            exit={{ scale: 0.95, opacity: 0, y: 10 }}
                            transition={{ type: "spring", damping: 25, stiffness: 300 }}
                            onClick={e => e.stopPropagation()}
                            style={{
                                padding: '32px',
                                width: '800px',
                                maxWidth: '95%',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '24px',
                                background: theme === 'dark' ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.9)',
                                backdropFilter: 'blur(20px) saturate(180%)',
                                borderRadius: '24px',
                                border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(255, 255, 255, 0.8)',
                                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                                color: 'var(--text)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <h3 style={{ margin: 0, fontSize: '24px', fontWeight: '800', letterSpacing: '-0.5px' }}>Ayarlar</h3>
                                <button
                                    onClick={discardSettings}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                                        e.currentTarget.style.color = '#ef4444';
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.background = theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)';
                                        e.currentTarget.style.color = 'var(--text)';
                                    }}
                                    style={{
                                        background: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
                                        border: 'none',
                                        cursor: 'pointer',
                                        color: 'var(--text)',
                                        width: '36px',
                                        height: '36px',
                                        borderRadius: '50%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        transition: 'all 0.2s'
                                    }}
                                >
                                    <FontAwesomeIcon icon={faTimes} style={{ fontSize: '18px' }} />
                                </button>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                                {/* Left Column */}
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                                    {/* General Settings */}
                                    <div>
                                        <label style={{ fontSize: '12px', fontWeight: '800', color: 'var(--text-secondary)', display: 'block', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.8 }}>GENEL AYARLAR</label>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                            <SettingsToggle
                                                label="Oturumu Koru"
                                                checked={rememberSession}
                                                onChange={setRememberSession}
                                                theme={theme}
                                                tooltip="Kapatıldığında ayarları ve kodları hatırla"
                                                icon={faSave}
                                            />
                                            <SettingsToggle
                                                label="Mevcut Montaja Ekle"
                                                checked={addToExisting}
                                                onChange={setAddToExisting}
                                                theme={theme}
                                                activeColor="#6366f1"
                                                tooltip="Yeni montaj oluşturmak yerine açık olan montaja parça ekler"
                                                disabled={multiKitMode || isAnyBatchModeActive}
                                            />
                                            <SettingsToggle
                                                label="Bulunamayan Varsa Durdur"
                                                checked={stopOnNotFound}
                                                onChange={setStopOnNotFound}
                                                theme={theme}
                                                activeColor="#6366f1"
                                                tooltip="Parça bulunamadığında işlemi durdurur"
                                                disabled={multiKitMode || isAnyBatchModeActive}
                                            />
                                            <SettingsToggle
                                                label="Tekrarlı Kodları Sil"
                                                checked={dedupe}
                                                onChange={setDedupe}
                                                theme={theme}
                                                activeColor="#6366f1"
                                                tooltip="Listeye eklenen mükerrer (aynı) kodları otomatik temizler"
                                                disabled={multiKitMode || isAnyBatchModeActive}
                                            />
                                        </div>
                                    </div>

                                    {/* Vault Path */}
                                    <div>
                                        <label style={{ fontSize: '12px', fontWeight: '800', color: 'var(--text-secondary)', display: 'block', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.8 }}>KASA YOLU</label>
                                        <div
                                            onClick={handleSelectFolder}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'flex-start',
                                                background: theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.5)',
                                                border: highlightVaultSettings
                                                    ? '2px solid #ef4444'
                                                    : (!vaultPath ? '2px dashed #6366f1' : (theme === 'dark' ? '2px dashed rgba(255,255,255,0.1)' : '2px dashed rgba(0,0,0,0.1)')),
                                                borderRadius: '16px',
                                                color: vaultPath ? 'var(--text)' : 'var(--text-secondary)',
                                                padding: '0 16px',
                                                height: '56px',
                                                cursor: 'pointer',
                                                transition: 'all 0.2s',
                                                boxShadow: highlightVaultSettings ? '0 0 0 4px rgba(239, 68, 68, 0.2)' : 'none',
                                                animation: highlightVaultSettings ? 'pulse-red 2s infinite' : 'none',
                                                boxSizing: 'border-box'
                                            }}
                                        >
                                            <FontAwesomeIcon icon={faFolder} style={{ fontSize: '20px', color: '#6366f1', marginRight: '12px' }} />
                                            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '14px', fontWeight: '500' }}>
                                                {vaultPath || "Klasör Seç..."}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Right Column */}
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                                    {/* SAP Integration */}
                                    <div>
                                        <label style={{ fontSize: '12px', fontWeight: '800', color: 'var(--text-secondary)', display: 'block', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.8 }}>SAP ENTEGRASYONU</label>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                            <SettingsToggle
                                                label="Çoklu Kit Montajı"
                                                checked={multiKitMode}
                                                onChange={setMultiKitMode}
                                                theme={theme}
                                                activeColor="#ef4444"
                                                tooltip="Birden fazla kit için montaj oluşturur (Bu özellik diğer özelliklerden bağımsız çalışmaktadır)"
                                                disabled={isAnyBatchModeActive}
                                            />
                                            <AnimatePresence>
                                                {multiKitMode && (
                                                    <motion.div
                                                        initial={{ opacity: 0, height: 0 }}
                                                        animate={{ opacity: 1, height: 'auto' }}
                                                        exit={{ opacity: 0, height: 0 }}
                                                        style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: '12px' }}
                                                    >
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: theme === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)', padding: '0 16px', borderRadius: '16px', height: '56px', border: !sapUsername ? '1px solid #ef4444' : (theme === 'dark' ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)'), boxSizing: 'border-box' }}>
                                                            <FontAwesomeIcon icon={faUser} style={{ color: 'var(--text-secondary)', fontSize: '14px' }} />
                                                            <input
                                                                type="text"
                                                                placeholder="SAP Kullanıcı Adı"
                                                                value={sapUsername}
                                                                onChange={(e) => setSapUsername(e.target.value)}
                                                                style={{ background: 'transparent', border: 'none', color: 'var(--text)', fontSize: '14px', width: '100%', outline: 'none' }}
                                                            />
                                                        </div>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: theme === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)', padding: '0 16px', borderRadius: '16px', height: '56px', border: !sapPassword ? '1px solid #ef4444' : (theme === 'dark' ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)'), boxSizing: 'border-box' }}>
                                                            <FontAwesomeIcon icon={faKey} style={{ color: 'var(--text-secondary)', fontSize: '14px' }} />
                                                            <input
                                                                type={showPassword ? "text" : "password"}
                                                                placeholder="SAP Şifre"
                                                                value={sapPassword}
                                                                onChange={(e) => setSapPassword(e.target.value)}
                                                                style={{ background: 'transparent', border: 'none', color: 'var(--text)', fontSize: '14px', width: '100%', outline: 'none' }}
                                                            />
                                                            <FontAwesomeIcon
                                                                icon={showPassword ? faEyeSlash : faEye}
                                                                style={{ color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '14px' }}
                                                                onClick={() => setShowPassword(!showPassword)}
                                                            />
                                                        </div>
                                                        <div
                                                            onClick={async () => {
                                                                const path = await window.electron.selectFolder();
                                                                if (path) setAssemblySavePath(path);
                                                            }}
                                                            style={{
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                gap: '12px',
                                                                background: theme === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(255, 255, 255, 0.5)',
                                                                padding: '0 16px',
                                                                borderRadius: '16px',
                                                                height: '56px',
                                                                border: !assemblySavePath ? '2px dashed #ef4444' : (theme === 'dark' ? '2px dashed rgba(255,255,255,0.1)' : '2px dashed rgba(0,0,0,0.1)'),
                                                                cursor: 'pointer',
                                                                boxSizing: 'border-box'
                                                            }}
                                                        >
                                                            <FontAwesomeIcon icon={faFolderOpen} style={{ color: '#ef4444', fontSize: '16px' }} />
                                                            <span style={{ fontSize: '14px', color: assemblySavePath ? 'var(--text)' : 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                                {assemblySavePath || "Montaj Kayıt Yolu Seç..."}
                                                            </span>
                                                        </div>
                                                    </motion.div>
                                                )}
                                            </AnimatePresence>
                                        </div>
                                    </div>

                                    {/* Batch Settings (Protected) */}
                                    <div>
                                        <label style={{ fontSize: '12px', fontWeight: '800', color: 'var(--text-secondary)', display: 'block', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.8 }}>TOPLU AYARLAR</label>
                                        <div style={!batchSettingsUnlocked ? {
                                            background: theme === 'dark' ? 'rgba(0, 0, 0, 0.2)' : 'rgba(0, 0, 0, 0.03)',
                                            borderRadius: '20px',
                                            padding: '24px',
                                            border: '2px dashed var(--border)',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            gap: '16px',
                                            textAlign: 'center',
                                            opacity: multiKitMode ? 0.5 : 1,
                                            transition: 'opacity 0.3s'
                                        } : {
                                            display: 'flex',
                                            flexDirection: 'column',
                                            gap: '12px',
                                            opacity: multiKitMode ? 0.5 : 1,
                                            transition: 'opacity 0.3s'
                                        }}>
                                            {!batchSettingsUnlocked ? (
                                                <>
                                                    <div style={{ color: 'var(--text-secondary)', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                        <FontAwesomeIcon icon={faLock} style={{ fontSize: '14px' }} />
                                                        <span>Bu ayarlar korumalıdır</span>
                                                    </div>

                                                    <div style={{ display: 'flex', gap: '12px', width: '100%' }}>
                                                        <input
                                                            type="password"
                                                            placeholder="Erişim şifresi..."
                                                            className="modern-input"
                                                            value={batchPasswordInput}
                                                            onChange={(e) => setBatchPasswordInput(e.target.value)}
                                                            style={{
                                                                padding: '0 20px',
                                                                height: '56px',
                                                                borderRadius: '16px',
                                                                fontSize: '15px',
                                                                background: theme === 'dark' ? 'rgba(0,0,0,0.2)' : 'white',
                                                                border: '2px solid #3b82f6',
                                                                color: 'var(--text)',
                                                                outline: 'none',
                                                                boxSizing: 'border-box',
                                                                boxShadow: '0 0 20px rgba(59, 130, 246, 0.15)',
                                                                transition: 'all 0.2s'
                                                            }}
                                                        />
                                                        <button
                                                            className="modern-btn primary"
                                                            onClick={() => {
                                                                if (multiKitMode) {
                                                                    setAlertState({
                                                                        isOpen: true,
                                                                        message: 'Toplu Kit Montajı aktif olduğu için giriş yapılamaz',
                                                                        type: 'error'
                                                                    });
                                                                    return;
                                                                }

                                                                if (batchPasswordInput === 'KB3183') {
                                                                    setBatchSettingsUnlocked(true);
                                                                    setBatchPasswordInput('');
                                                                } else {
                                                                    setAlertState({
                                                                        isOpen: true,
                                                                        message: 'Hatalı şifre!',
                                                                        type: 'error'
                                                                    });
                                                                }
                                                            }}
                                                            style={{
                                                                padding: '0 32px',
                                                                height: '56px',
                                                                borderRadius: '16px',
                                                                background: '#3b82f6',
                                                                boxShadow: '0 8px 20px -4px rgba(59, 130, 246, 0.5)',
                                                                fontSize: '14px',
                                                                fontWeight: '800',
                                                                textTransform: 'uppercase',
                                                                letterSpacing: '1px',
                                                                cursor: multiKitMode ? 'not-allowed' : 'pointer'
                                                            }}
                                                        >
                                                            AÇ
                                                        </button>
                                                    </div>
                                                </>
                                            ) : (
                                                <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                                    <SettingsToggle
                                                        label="Toplu Dosya İsimlendir"
                                                        checked={batchRenameMode}
                                                        onChange={(val) => handleBatchToggle(val, setBatchRenameMode)}
                                                        theme={theme}
                                                        activeColor="#3b82f6"
                                                        tooltip="Dosya isimlendir yapılmayan dosyaların hepsine dosya isimlendir yapılması"
                                                    />
                                                    <SettingsToggle
                                                        label="Toplu Veri Kartı Düzeltme"
                                                        checked={batchFixDataCardMode}
                                                        onChange={(val) => handleBatchToggle(val, setBatchFixDataCardMode)}
                                                        theme={theme}
                                                        activeColor="#3b82f6"
                                                        tooltip="Bütün parçalarda arama yaptır, kütle veya malzeme yazmayan parçaların şablonlarını değiştir"
                                                    />
                                                    <SettingsToggle
                                                        label="Toplu Dosya Düzeni"
                                                        checked={batchFileLayoutMode}
                                                        onChange={(val) => handleBatchToggle(val, setBatchFileLayoutMode)}
                                                        theme={theme}
                                                        activeColor="#3b82f6"
                                                        tooltip="Bütün parçaların ve motajların arka planının beyaz olması ağaç görünümünün düzeltilmesi"
                                                    />
                                                    <SettingsToggle
                                                        label="Toplu Montaj Kilosu Düzeltme"
                                                        checked={batchAssemblyWeightCorrectionMode}
                                                        onChange={(val) => handleBatchToggle(val, setBatchAssemblyWeightCorrectionMode)}
                                                        theme={theme}
                                                        activeColor="#3b82f6"
                                                        tooltip="Montajlarda görünmez bileşenleride kiloya dahil ettiği için kütle özelliklerinden düzenlenmesi"
                                                    />
                                                    <SettingsToggle
                                                        label="Toplu Tekrarlı Kodların Belirlenmesi"
                                                        checked={batchDuplicateCodeCheckMode}
                                                        onChange={(val) => handleBatchToggle(val, setBatchDuplicateCodeCheckMode)}
                                                        theme={theme}
                                                        activeColor="#3b82f6"
                                                        tooltip="Bütün mükerrer kodların belirlenip excel olarak çekilmesi"
                                                    />
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <button
                                className="modern-btn primary"
                                onClick={saveSettings}
                                style={{
                                    marginTop: '8px',
                                    height: '56px',
                                    borderRadius: '16px',
                                    fontSize: '16px',
                                    fontWeight: '700',
                                    background: '#6366f1',
                                    boxShadow: '0 10px 20px -5px rgba(99, 102, 241, 0.4)',
                                    width: '300px',
                                    alignSelf: 'center'
                                }}
                            >
                                KAYDET VE KAPAT
                            </button>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
            <CustomAlert
                isOpen={alertState.isOpen}
                message={alertState.message}
                type={alertState.type}
                onClose={() => setAlertState(prev => ({ ...prev, isOpen: false }))}
                theme={theme}
            />
        </PageLayout>
    );
};

export default AssemblyWizard;
