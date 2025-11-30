import React from 'react';

const TitleBar = () => {
    const handleMinimize = () => {
        window.electron?.minimize();
    };
    const handleMaximize = () => {
        window.electron?.maximize();
    };
    const handleClose = () => {
        window.electron?.close();
    };

    return (
        <div className="title-bar">
            <div className="title-btn min-btn" onClick={handleMinimize} title="Minimize"></div>
            <div className="title-btn max-btn" onClick={handleMaximize} title="Maximize"></div>
            <div className="title-btn close-btn" onClick={handleClose} title="Close"></div>
        </div>
    );
};

export default TitleBar;
