import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faDatabase, faArrowRight, faChartLine, faWrench, faBolt } from '@fortawesome/free-solid-svg-icons';

const Landing = ({ theme, toggleTheme }) => {
    const navigate = useNavigate();

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.2,
                delayChildren: 0.1
            }
        }
    };

    const itemVariants = {
        hidden: { y: 20, opacity: 0 },
        visible: {
            y: 0,
            opacity: 1,
            transition: { type: "spring", stiffness: 100 }
        }
    };

    return (
        <motion.div
            initial="hidden"
            animate="visible"
            variants={containerVariants}
            style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '40px', boxSizing: 'border-box', background: 'radial-gradient(circle at top right, rgba(99, 102, 241, 0.1), transparent 40%)' }}
        >
            {/* Header */}
            <motion.div variants={itemVariants} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '60px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <img src="/logo.png" alt="Logo" style={{ height: '50px' }} onError={(e) => e.target.style.display = 'none'} />
                    <div>
                        <h1 style={{ margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-1px', background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Ar-Ge Otomasyon</h1>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-secondary)', padding: '2px 8px', background: 'var(--border)', borderRadius: '10px' }}>v2.0.0</span>
                        </div>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                    <div className="day-night-toggle" onClick={toggleTheme}>
                        <div className="toggle-circle"></div>
                        <div className="toggle-decoration">
                            <div className="star star-1"></div>
                            <div className="star star-2"></div>
                            <div className="star star-3"></div>
                            <div className="cloud cloud-1"></div>
                            <div className="cloud cloud-2"></div>
                        </div>
                    </div>
                </div>
            </motion.div>

            {/* Main Content */}
            <div style={{ flex: 1, width: '100%', maxWidth: '1200px', margin: '0 auto', display: 'flex', gap: '40px', justifyContent: 'center', alignItems: 'center', padding: '20px' }}>

                {/* SAP Wizard Card */}
                <motion.div
                    variants={itemVariants}
                    className="modern-card"
                    onClick={() => navigate('/sap')}
                    style={{
                        flex: 1,
                        maxWidth: '400px',
                        minWidth: '280px',
                        aspectRatio: '3/4',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        padding: '40px',
                        position: 'relative'
                    }}
                >
                    <div>
                        <div className="icon-box primary" style={{ width: '70px', height: '70px', borderRadius: '20px', marginBottom: '30px' }}>
                            <FontAwesomeIcon icon={faDatabase} style={{ fontSize: '32px' }} />
                        </div>
                        <h2 style={{ margin: '0 0 16px 0', fontSize: 'clamp(20px, 2.5vw, 28px)', fontWeight: '700' }}>SAP Sihirbazı</h2>
                        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 'clamp(14px, 1.5vw, 16px)', lineHeight: '1.6' }}>
                            SAP veri yönetimi, malzeme kartı oluşturma ve entegrasyon araçları.
                        </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#6366f1', fontWeight: '600', fontSize: '14px' }}>
                        Keşfet <FontAwesomeIcon icon={faArrowRight} style={{ fontSize: '16px' }} />
                    </div>

                    <div style={{ position: 'absolute', top: '20px', right: '20px', opacity: 0.1 }}>
                        <FontAwesomeIcon icon={faChartLine} style={{ fontSize: '120px' }} />
                    </div>
                </motion.div>

                {/* Assembly Wizard Card */}
                <motion.div
                    variants={itemVariants}
                    className="modern-card"
                    onClick={() => navigate('/assembly')}
                    style={{
                        flex: 1,
                        maxWidth: '400px',
                        minWidth: '280px',
                        aspectRatio: '3/4',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        padding: '40px',
                        position: 'relative',
                        border: '2px solid rgba(16, 185, 129, 0.1)'
                    }}
                >
                    <div>
                        <div className="icon-box success" style={{ width: '70px', height: '70px', borderRadius: '20px', marginBottom: '30px' }}>
                            <FontAwesomeIcon icon={faWrench} style={{ fontSize: '32px' }} />
                        </div>
                        <h2 style={{ margin: '0 0 16px 0', fontSize: 'clamp(20px, 2.5vw, 28px)', fontWeight: '700' }}>Montaj Sihirbazı</h2>
                        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 'clamp(14px, 1.5vw, 16px)', lineHeight: '1.6' }}>
                            Otomatik montaj oluşturma, parça doğrulama ve akıllı yerleştirme.
                        </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981', fontWeight: '600', fontSize: '14px' }}>
                        Başlat <FontAwesomeIcon icon={faArrowRight} style={{ fontSize: '16px' }} />
                    </div>

                    <div style={{ position: 'absolute', top: '20px', right: '20px', opacity: 0.1 }}>
                        <FontAwesomeIcon icon={faBolt} style={{ fontSize: '120px' }} />
                    </div>
                </motion.div>

            </div>
        </motion.div>
    );
};

export default Landing;
