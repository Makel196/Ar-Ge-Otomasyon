import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faMinus, faSquare, faTimes } from '@fortawesome/free-solid-svg-icons';

const TitleBar = ({ theme }) => {
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

    return (
        <>
            {/* Draggable title bar area */}
            <div style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                height: '40px',
                WebkitAppRegion: 'drag',
                zIndex: 9999,
                pointerEvents: 'none'
            }} />

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
                    <FontAwesomeIcon icon={faSquare} style={{ fontSize: '11px' }} />
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
