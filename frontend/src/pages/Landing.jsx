import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowRight, faChartLine, faBolt, faStar } from '@fortawesome/free-solid-svg-icons';
import PageLayout from '../components/PageLayout';

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
        },
        hover: {
            scale: 1.05,
            y: -10,
            boxShadow: "0 25px 50px -12px rgba(99, 102, 241, 0.5)",
            transition: { type: "spring", stiffness: 300, damping: 20 }
        },
        tap: { scale: 0.98 }
    };

    const shimmerVariants = {
        initial: { x: '-100%', opacity: 0 },
        animate: {
            x: '200%',
            opacity: [0, 0.3, 0],
            transition: {
                repeat: Infinity,
                duration: 3,
                ease: "linear",
                repeatDelay: 2
            }
        }
    };

    const floatingIconVariants = {
        animate: {
            y: [0, -15, 0],
            rotate: [0, 5, -5, 0],
            transition: {
                duration: 6,
                repeat: Infinity,
                ease: "easeInOut"
            }
        }
    };

    const logoAnimationVariants = {
        animate: {
            y: [0, -10, 0],
            scale: [1, 1.05, 1],
            filter: ["drop-shadow(0 0 0px rgba(0,0,0,0))", "drop-shadow(0 10px 10px rgba(0,0,0,0.2))", "drop-shadow(0 0 0px rgba(0,0,0,0))"],
            transition: {
                duration: 4,
                repeat: Infinity,
                ease: "easeInOut"
            }
        },
        hover: {
            scale: 1.1,
            rotate: [0, -5, 5, 0],
            transition: {
                duration: 0.5
            }
        }
    };

    const Stars = ({ theme }) => {
        const starColor = theme === 'dark' ? '#ffffff' : '#fbbf24';
        const stars = [
            { top: '15%', left: '25%', size: 12, delay: 0 },
            { top: '35%', left: '85%', size: 16, delay: 0.5 },
            { top: '65%', left: '15%', size: 10, delay: 1 },
            { top: '85%', left: '75%', size: 20, delay: 1.5 },
            { top: '25%', left: '65%', size: 14, delay: 0.2 },
            { top: '55%', left: '55%', size: 18, delay: 0.7 },
            { top: '90%', left: '35%', size: 10, delay: 1.2 },
            { top: '10%', left: '70%', size: 12, delay: 0.8 },
        ];

        return (
            <motion.div
                variants={{
                    hover: { opacity: 1 },
                    tap: { opacity: 1 },
                    visible: { opacity: 0 }, // default state from parent
                    hidden: { opacity: 0 }
                }}
                initial={{ opacity: 0 }}
                style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 0 }}
            >
                {stars.map((star, i) => (
                    <motion.div
                        key={i}
                        animate={{
                            opacity: [0.4, 1, 0.4],
                            scale: [0.8, 1.2, 0.8],
                            rotate: [0, 45, 0]
                        }}
                        transition={{
                            duration: 3,
                            repeat: Infinity,
                            delay: star.delay,
                            ease: "easeInOut"
                        }}
                        style={{
                            position: 'absolute',
                            top: star.top,
                            left: star.left,
                            width: star.size,
                            height: star.size,
                            color: starColor,
                            filter: `drop-shadow(0 0 ${star.size / 2}px ${starColor})`
                        }}
                    >
                        <FontAwesomeIcon icon={faStar} style={{ width: '100%', height: '100%' }} />
                    </motion.div>
                ))}
            </motion.div>
        );
    };

    return (
        <PageLayout
            initial="hidden"
            animate="visible"
            variants={containerVariants}
            style={{ background: 'radial-gradient(circle at top right, rgba(99, 102, 241, 0.1), transparent 40%)' }}
        >
            {/* Header */}
            <motion.div variants={itemVariants} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '60px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                    <motion.img
                        src="./logo.png"
                        alt="Logo"
                        style={{ height: '50px' }}
                        onError={(e) => e.target.style.display = 'none'}
                        variants={logoAnimationVariants}
                        whileHover="hover"
                    />
                    <div>
                        <h1 style={{ margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-1px', background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Ar-Ge Otomasyon</h1>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '13px', fontWeight: '600', color: '#10b981', padding: '2px 8px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '10px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>v2.0.0</span>
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
            <div style={{ flex: 1, width: '100%', margin: '0 auto', display: 'flex', gap: '40px', justifyContent: 'center', alignItems: 'center', padding: '20px' }}>

                {/* SAP Wizard Card */}
                <motion.div
                    variants={itemVariants}
                    whileHover="hover"
                    whileTap="tap"
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
                    {/* Content Container with Overflow Hidden for Shimmer */}
                    <div style={{ position: 'absolute', inset: 0, borderRadius: '24px', overflow: 'hidden', pointerEvents: 'none' }}>
                        {/* Shimmer Effect */}
                        <motion.div
                            variants={shimmerVariants}
                            initial="initial"
                            animate="animate"
                            style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '100%',
                                height: '100%',
                                background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)',
                                transform: 'skewX(-20deg)',
                            }}
                        />

                        {/* Stars Effect */}
                        <Stars theme={theme} />

                        {/* Floating Background Icon */}
                        <motion.div
                            variants={floatingIconVariants}
                            animate="animate"
                            style={{
                                position: 'absolute',
                                top: '50%',
                                left: '40%',
                                transform: 'translate(-50%, -50%)',
                                opacity: 0.05,
                                zIndex: 0,
                                filter: 'blur(4px)'
                            }}
                        >
                            <FontAwesomeIcon icon={faChartLine} style={{ fontSize: '300px' }} />
                        </motion.div>
                    </div>

                    <div style={{ position: 'relative', zIndex: 1 }}>
                        <motion.div
                            style={{ width: '80px', height: '80px', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            variants={logoAnimationVariants}
                            whileHover="hover"
                        >
                            <img src="./sslogo.png" alt="SAP Sihirbazı" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        </motion.div>
                        <h2 style={{ margin: '0 0 16px 0', fontSize: 'clamp(20px, 2.5vw, 28px)', fontWeight: '700' }}>SAP Sihirbazı</h2>
                        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 'clamp(14px, 1.5vw, 16px)', lineHeight: '1.6' }}>
                            SAP veri yönetimi, malzeme kartı oluşturma ve entegrasyon araçları.
                        </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#6366f1', fontWeight: '700', fontSize: '18px', position: 'relative', zIndex: 1 }}>
                        Keşfet <FontAwesomeIcon icon={faArrowRight} style={{ fontSize: '20px' }} />
                    </div>
                </motion.div>

                {/* Assembly Wizard Card */}
                <motion.div
                    variants={itemVariants}
                    whileHover="hover"
                    whileTap="tap"
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
                    {/* Content Container with Overflow Hidden for Shimmer */}
                    <div style={{ position: 'absolute', inset: 0, borderRadius: '24px', overflow: 'hidden', pointerEvents: 'none' }}>
                        {/* Shimmer Effect */}
                        <motion.div
                            variants={shimmerVariants}
                            initial="initial"
                            animate="animate"
                            style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '100%',
                                height: '100%',
                                background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)',
                                transform: 'skewX(-20deg)',
                            }}
                        />

                        {/* Stars Effect */}
                        <Stars theme={theme} />

                        {/* Floating Background Icon */}
                        <motion.div
                            variants={floatingIconVariants}
                            animate="animate"
                            style={{
                                position: 'absolute',
                                top: '50%',
                                left: '40%',
                                transform: 'translate(-50%, -50%)',
                                opacity: 0.05,
                                zIndex: 0,
                                filter: 'blur(4px)'
                            }}
                        >
                            <FontAwesomeIcon icon={faBolt} style={{ fontSize: '300px' }} />
                        </motion.div>
                    </div>

                    <div style={{ position: 'relative', zIndex: 1 }}>
                        <motion.div
                            style={{ width: '80px', height: '80px', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                            variants={logoAnimationVariants}
                            whileHover="hover"
                        >
                            <img src="./mslogo.png" alt="Montaj Sihirbazı" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        </motion.div>
                        <h2 style={{ margin: '0 0 16px 0', fontSize: 'clamp(20px, 2.5vw, 28px)', fontWeight: '700' }}>Montaj Sihirbazı</h2>
                        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 'clamp(14px, 1.5vw, 16px)', lineHeight: '1.6' }}>
                            Otomatik montaj oluşturma, parça doğrulama ve akıllı yerleştirme.
                        </p>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981', fontWeight: '700', fontSize: '18px', position: 'relative', zIndex: 1 }}>
                        Başlat <FontAwesomeIcon icon={faArrowRight} style={{ fontSize: '20px' }} />
                    </div>
                </motion.div>

            </div>
        </PageLayout>
    );
};

export default Landing;
