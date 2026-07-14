import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import Dashboard from './components/Dashboard';
import Landing from './components/Landing';

function App() {
  const [token, setToken] = useState(localStorage.getItem('marka_token'));
  const [showAuth, setShowAuth] = useState(false);
  const [initialAuthTab, setInitialAuthTab] = useState('login');

  // If token changes (e.g. from logout), update state
  const handleLogin = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('marka_token');
    localStorage.removeItem('marka_credits');
    setToken(null);
    setShowAuth(false);
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
