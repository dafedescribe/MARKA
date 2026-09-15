import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import Dashboard from './components/Dashboard';
import Landing from './components/Landing';
import { clearStoredSession, readUsableToken, tokenExpiryMs } from './lib/session';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [token, setToken] = useState(() => readUsableToken(localStorage));
  const [showAuth, setShowAuth] = useState(false);
  const [initialAuthTab, setInitialAuthTab] = useState('login');

  useEffect(() => {
    // 1. Silent Wake-up for Render Cold Starts
    // Fire a non-blocking request to wake up the API if it has spun down.
    fetch(`${API_URL}/`).catch(() => {});
  }, []);

  const handleLogout = () => {
    clearStoredSession(localStorage);
    setToken(null);
    setShowAuth(false);
  };

  useEffect(() => {
    if (!token) return undefined;
    const expiry = tokenExpiryMs(token);
    if (!expiry) {
      handleLogout();
      return undefined;
    }
    const timer = window.setTimeout(handleLogout, expiry - Date.now());
    return () => window.clearTimeout(timer);
  }, [token]);

  const handleLogin = (newToken) => {
    setToken(newToken);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {token ? (
        <Dashboard token={token} onLogout={handleLogout} />
      ) : showAuth ? (
        <div className="relative">
          <button 
            onClick={() => setShowAuth(false)}
            className="absolute top-8 right-8 z-50 text-gray-400 hover:text-[#3B0042] font-bold text-sm bg-white px-4 py-2 rounded-xl shadow-sm border border-gray-100 transition-colors"
          >
            ← Back to Home
          </button>
          <Auth onLogin={handleLogin} initialTab={initialAuthTab} />
        </div>
      ) : (
        <Landing onGetStarted={(tab = 'login') => { setInitialAuthTab(tab); setShowAuth(true); }} />
      )}
    </div>
  );
}

export default App;
