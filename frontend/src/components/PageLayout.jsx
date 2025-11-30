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
                maxWidth: '1600px',
                margin: '0 auto',
                padding: '50px 20px 20px 20px', // Standard padding: Top 50px for TitleBar
                display: 'flex',
                flexDirection: 'column',
                gap: '24px', // Standard gap between elements
                boxSizing: 'border-box',
                overflow: 'hidden',
                ...style
            }}
            {...props}
        >
            {children}
        </motion.div>
    );
};

export default PageLayout;
