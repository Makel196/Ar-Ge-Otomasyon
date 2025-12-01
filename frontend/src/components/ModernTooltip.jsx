import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const ModernTooltip = ({ text, children, theme }) => {
    const [isVisible, setIsVisible] = useState(false);

    return (
        <div
            onMouseEnter={() => setIsVisible(true)}
            onMouseLeave={() => setIsVisible(false)}
            style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                padding: '15px',
                margin: '-15px',
                cursor: 'help'
            }}
        >
            {children}
            <AnimatePresence>
                {isVisible && (
                    <motion.div
                        initial={{ opacity: 0, y: 5, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 5, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        style={{
                            position: 'absolute',
                            bottom: '100%',
                            right: 0,
                            marginBottom: '5px',
                            padding: '8px 12px',
                            background: theme === 'dark' ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.95)',
                            color: theme === 'dark' ? '#0f172a' : '#ffffff',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: '500',
                            whiteSpace: 'nowrap',
                            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                            zIndex: 9999,
                            pointerEvents: 'auto',
                            minWidth: 'max-content'
                        }}
                    >
                        {text}
                        <div style={{
                            position: 'absolute',
                            top: '100%',
                            right: '18px',
                            borderLeft: '6px solid transparent',
                            borderRight: '6px solid transparent',
                            borderTop: `6px solid ${theme === 'dark' ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.95)'}`
                        }} />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default ModernTooltip;
