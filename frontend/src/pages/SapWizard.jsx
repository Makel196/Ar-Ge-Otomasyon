import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft, faInfoCircle, faCheckCircle, faMagic, faCog, faPen } from '@fortawesome/free-solid-svg-icons';
import { motion } from 'framer-motion';

const SapWizard = ({ theme, toggleTheme }) => {
    const navigate = useNavigate();

    return (
        <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            style={{
                height: '100vh',
                padding: '50px 20px 20px 20px',
                maxWidth: '1600px',
                margin: '0 auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
                boxSizing: 'border-box',
                overflow: 'hidden'
            }}
        >
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
                        <div className="icon-box primary" style={{ width: '40px', height: '40px' }}>
                            <FontAwesomeIcon icon={faPen} style={{ fontSize: '20px' }} />
                        </div>
                        <div>
                            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '700' }}>SAP Sihirbazı</h2>
                            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Otomatik SAP İşlemleri</span>
                        </div>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: '12px',
                        background: 'rgba(59, 130, 246, 0.1)',
                        padding: '8px 16px', borderRadius: '12px',
                        border: '1px solid rgba(59, 130, 246, 0.2)'
                    }}>
                        <FontAwesomeIcon icon={faInfoCircle} style={{ fontSize: '16px', color: '#3b82f6' }} />
                        <span style={{ fontWeight: '700', fontSize: '13px', color: '#3b82f6' }}>Geliştirme Aşamasında</span>
                    </div>

                    <button
                        className="modern-btn"
                        style={{ width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.5, cursor: 'not-allowed' }}
                    >
                        <FontAwesomeIcon icon={faCog} style={{ fontSize: '18px' }} />
                    </button>
                </div>
            </motion.div>

            {/* Content */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', maxWidth: '800px', width: '100%', margin: '0 auto' }}>

                <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.2, type: "spring" }}
                    style={{
                        width: '100px',
                        height: '100px',
                        background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
                        borderRadius: '30px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '32px',
                        boxShadow: '0 20px 40px -10px rgba(99, 102, 241, 0.5)'
                    }}
                >
                    <FontAwesomeIcon icon={faInfoCircle} style={{ fontSize: '48px', color: 'white' }} />
                </motion.div>

                <motion.h1
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    style={{
                        fontSize: '36px',
                        fontWeight: '800',
                        marginBottom: '16px',
                        color: 'var(--text)',
                        letterSpacing: '-1px'
                    }}
                >
                    Gelecek Versiyon Bilgilendirmesi
                </motion.h1>

                <motion.p
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    style={{
                        fontSize: '16px',
                        color: 'var(--text-secondary)',
                        marginBottom: '48px',
                        lineHeight: '1.6',
                        maxWidth: '600px'
                    }}
                >
                    SAP Sihirbazı modülü <span style={{ color: '#6366f1', fontWeight: '700' }}>v3.0.0</span> sürümü ile birlikte aktif edilecektir.
                    Bu modül ile aşağıdaki özellikler planlanmaktadır:
                </motion.p>

                <motion.div
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.5 }}
                    className="modern-card"
                    style={{
                        padding: '40px',
                        width: '100%',
                        background: 'var(--bg)',
                        border: '1px solid var(--border)'
                    }}
                >
                    <div className="responsive-grid" style={{ gap: '24px', textAlign: 'left' }}>
                        {[
                            "Otomatik Malzeme Kartı",
                            "Toplu Veri Güncelleme",
                            "SAP - PDM Entegrasyonu",
                            "Gelişmiş Raporlama",
                            "Stok Kontrolü",
                            "Otomatik Konfigürasyon"
                        ].map((item, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <div style={{
                                    width: '24px', height: '24px', borderRadius: '50%',
                                    background: 'rgba(16, 185, 129, 0.1)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    color: '#10b981'
                                }}>
                                    <FontAwesomeIcon icon={faCheckCircle} style={{ fontSize: '14px' }} />
                                </div>
                                <span style={{ fontSize: '15px', fontWeight: '500' }}>{item}</span>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </div>
        </motion.div>
    );
};

export default SapWizard;
