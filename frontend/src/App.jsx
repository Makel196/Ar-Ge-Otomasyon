import React, { useState, useEffect } from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import TitleBar from './components/TitleBar';
import Landing from './pages/Landing';
import AssemblyWizard from './pages/AssemblyWizard';
import SapWizard from './pages/SapWizard';

function App() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  return (
    <Router>
      <div className="app-container" style={{
        height: '100vh',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '0',
        overflow: 'hidden',
        background: 'var(--bg-gradient)',
        border: '1px solid var(--border)'
      }}>
        <TitleBar theme={theme} />
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Routes>
            <Route path="/" element={<Landing theme={theme} toggleTheme={toggleTheme} />} />
            <Route path="/assembly" element={<AssemblyWizard theme={theme} toggleTheme={toggleTheme} />} />
            <Route path="/sap" element={<SapWizard theme={theme} toggleTheme={toggleTheme} />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;
