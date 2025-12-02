import React, { useEffect, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faMinus, faSquare, faTimes, faWindowRestore } from '@fortawesome/free-solid-svg-icons';

const TitleBar = ({ theme }) => {
    const [isMaximized, setIsMaximized] = useState(false);

    const handleMinimize = () => {
        window.electron?.minimize();
    };
    const handleMaximize = () => {
        window.electron?.maximize();
    };
    const handleClose = () => {
        window.electron?.close();
    };

    const hoverColor = theme === 'light' ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)';

    useEffect(() => {
        // Sync initial state
        window.electron?.getWindowState?.().then((state) => {
            if (state && typeof state.maximized === 'boolean') {
                setIsMaximized(state.maximized);
            }
        });

        // Listen to future changes
        const unsubscribe = window.electron?.onWindowStateChange?.((state) => {
            if (state && typeof state.maximized === 'boolean') {
                setIsMaximized(state.maximized);
            }
        });

        const onDoubleClick = (e) => {
            // Only trigger when near the top bar to mimic native behavior
            if (e.clientY <= 50) {
                handleMaximize();
            }
        };

        window.addEventListener('dblclick', onDoubleClick);
        return () => {
            window.removeEventListener('dblclick', onDoubleClick);
            if (typeof unsubscribe === 'function') unsubscribe();
        };
    }, []);

    return (
        <>
            {/* Draggable title bar area */}
            <div
                onDoubleClick={handleMaximize}
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '40px',
                    WebkitAppRegion: 'drag',
                    zIndex: 9999,
                    pointerEvents: 'auto',
                    userSelect: 'none'
                }}
            />

            {/* Window controls */}
            <div style={{
                position: 'fixed',
                top: 0,
                right: 0,
                zIndex: 10000,
                display: 'flex',
                WebkitAppRegion: 'no-drag',
                padding: '8px 8px 0 0',
                pointerEvents: 'auto'
            }}>
                <button
                    onClick={handleMinimize}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text)',
                        width: '32px',
                        height: '32px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'background 0.2s',
                        borderRadius: '4px'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = hoverColor}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                    <FontAwesomeIcon icon={faMinus} style={{ fontSize: '12px' }} />
                </button>
                <button
                    onClick={handleMaximize}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text)',
                        width: '32px',
                        height: '32px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'background 0.2s',
                        borderRadius: '4px'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = hoverColor}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                    <FontAwesomeIcon icon={isMaximized ? faWindowRestore : faSquare} style={{ fontSize: '11px' }} />
                </button>
                <button
                    onClick={handleClose}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text)',
                        width: '32px',
                        height: '32px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.2s',
                        borderRadius: '4px'
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#ef4444';
                        e.currentTarget.style.color = 'white';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                        e.currentTarget.style.color = 'var(--text)';
                    }}
                >
                    <FontAwesomeIcon icon={faTimes} style={{ fontSize: '16px' }} />
                </button>
            </div>
        </>
    );
};

export default TitleBar;
