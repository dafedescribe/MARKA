import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import Dashboard from './components/Dashboard';
import Landing from './components/Landing';

function App() {
  const [token, setToken] = useState(localStorage.getItem('marka_token'));
  const [showAuth, setShowAuth] = useState(false);

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
            className="absolute top-4 left-4 z-50 text-gray-500 hover:text-blue-600 font-medium"
          >
            ← Back to Home
          </button>
          <Auth onLogin={handleLogin} />
        </div>
      ) : (
        <Landing onGetStarted={() => setShowAuth(true)} />
      )}
    </div>
  );
}

export default App;
