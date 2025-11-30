import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Info, CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';

const SapWizard = ({ theme, toggleTheme }) => {
    const navigate = useNavigate();

    return (
        <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            style={{ height: '100%', padding: '40px', display: 'flex', flexDirection: 'column', boxSizing: 'border-box', background: 'var(--bg)' }}
        >
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '40px' }}>
                <button className="modern-btn" onClick={() => navigate('/')} style={{ padding: '12px' }}>
                    <ArrowLeft size={24} />
                </button>
                <h1 style={{ marginLeft: '24px', fontSize: '28px', fontWeight: '700', margin: '0 0 0 24px' }}>SAP Sihirbazı</h1>
            </div>

            <div className="modern-card" style={{ flex: 1, padding: '60px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>

                {/* Background Decoration */}
                <div style={{ position: 'absolute', top: -100, right: -100, width: 300, height: 300, background: 'var(--gradient-primary)', opacity: 0.05, borderRadius: '50%', filter: 'blur(50px)' }}></div>
                <div style={{ position: 'absolute', bottom: -100, left: -100, width: 300, height: 300, background: 'var(--gradient-success)', opacity: 0.05, borderRadius: '50%', filter: 'blur(50px)' }}></div>

                <motion.div
                    initial={{ opacity: 0, scale: 0.9, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ duration: 0.5, type: "spring" }}
                    style={{ maxWidth: '600px', position: 'relative', zIndex: 1 }}
                >
                    <div className="animate-float" style={{
                        display: 'inline-flex', padding: '40px', borderRadius: '30px',
                        background: 'var(--gradient-primary)', color: 'white',
                        marginBottom: '40px',
                        boxShadow: '0 20px 40px rgba(99, 102, 241, 0.3)'
                    }}>
                        <Info size={64} />
                    </div>

                    <h2 style={{ marginBottom: '24px', fontSize: '32px', fontWeight: '800' }}>Gelecek Versiyon Bilgilendirmesi</h2>
                    <p style={{ lineHeight: '1.8', fontSize: '18px', color: 'var(--text-secondary)', marginBottom: '50px' }}>
                        SAP Sihirbazı modülü <strong style={{ color: '#6366f1' }}>v2.1.0</strong> sürümü ile birlikte aktif edilecektir.
                        Bu modül ile aşağıdaki özellikler planlanmaktadır:
                    </p>

                    <div style={{
                        background: 'var(--bg)',
                        padding: '40px',
                        borderRadius: '24px',
                        textAlign: 'left',
                        display: 'inline-block',
                        border: '1px solid var(--border)',
                        width: '100%',
                        boxSizing: 'border-box'
                    }}>
                        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                            {[
                                "Otomatik Malzeme Kartı",
                                "Toplu Veri Güncelleme",
                                "SAP - PDM Entegrasyonu",
                                "Gelişmiş Raporlama",
                                "Stok Kontrolü",
                                "Maliyet Analizi"
                            ].map((item, index) => (
                                <motion.li
                                    key={index}
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.2 + (index * 0.1) }}
                                    style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '16px', fontWeight: '500' }}
                                >
                                    <CheckCircle2 size={20} color="#10b981" />
                                    {item}
                                </motion.li>
                            ))}
                        </ul>
                    </div>
                </motion.div>
            </div>
        </motion.div>
    );
};

export default SapWizard;
