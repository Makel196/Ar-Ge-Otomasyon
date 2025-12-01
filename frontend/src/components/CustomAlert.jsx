import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheckCircle, faExclamationTriangle, faInfoCircle, faTimes } from '@fortawesome/free-solid-svg-icons';

const CustomAlert = ({ isOpen, message, type = 'info', onClose, theme = 'light' }) => {
    if (!isOpen) return null;

    const getIcon = () => {
        switch (type) {
            case 'success': return faCheckCircle;
            case 'error': return faExclamationTriangle;
            default: return faInfoCircle;
        }
    };

    const getColor = () => {
        switch (type) {
            case 'success': return '#10b981';
            case 'error': return '#ef4444';
            default: return '#3b82f6';
        }
    };

    return (
        <AnimatePresence>
            {isOpen && (
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
                        zIndex: 10001,
                    }}
                    onClick={onClose}
                >
                    <motion.div
                        initial={{ scale: 0.9, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 10 }}
                        transition={{ type: "spring", damping: 25, stiffness: 300 }}
                        onClick={e => e.stopPropagation()}
                        style={{
                            padding: '32px',
                            width: '400px',
                            maxWidth: '90%',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            textAlign: 'center',
                            gap: '20px',
                            background: theme === 'dark' ? 'rgba(30, 41, 59, 0.85)' : 'rgba(255, 255, 255, 0.75)',
                            backdropFilter: 'blur(20px) saturate(180%)',
                            borderRadius: '12px',
                            border: theme === 'dark' ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(255, 255, 255, 0.8)',
                            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                            color: 'var(--text)'
                        }}
                    >
                        <div style={{
                            width: '60px',
                            height: '60px',
                            borderRadius: '20px',
                            background: `${getColor()}20`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: getColor(),
                            marginBottom: '4px'
                        }}>
                            <FontAwesomeIcon icon={getIcon()} style={{ fontSize: '28px' }} />
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <h3 style={{ margin: 0, fontSize: '20px', fontWeight: '700' }}>
                                {type === 'error' ? 'Hata' : (type === 'success' ? 'Başarılı' : 'Bilgi')}
                            </h3>
                            <p style={{ margin: 0, fontSize: '15px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                                {message}
                            </p>
                        </div>

                        <button
                            className="modern-btn primary"
                            onClick={onClose}
                            style={{
                                width: '100%',
                                height: '45px',
                                borderRadius: '14px',
                                fontSize: '15px',
                                marginTop: '10px',
                                background: getColor(),
                                border: 'none',
                                color: 'white',
                                fontWeight: '600',
                                cursor: 'pointer',
                                boxShadow: `0 10px 20px -5px ${getColor()}40`
                            }}
                        >
                            Tamam
                        </button>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default CustomAlert;
