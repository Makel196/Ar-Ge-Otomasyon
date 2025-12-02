import React from 'react';
import { motion } from 'framer-motion';

const PageLayout = ({ children, className = '', style = {}, ...props }) => {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={`page-layout ${className}`}
            style={{
                height: '100vh',
                width: '100%',
                overflow: 'hidden',
                ...style
            }}
            {...props}
        >
            <div style={{
                maxWidth: '1600px',
                margin: '0 auto',
                padding: '70px 20px 20px 20px',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                gap: '24px',
                boxSizing: 'border-box',
                width: '100%'
            }}>
                {children}
            </div>
        </motion.div>
    );
};

export default PageLayout;
