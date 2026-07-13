import React, { useState, useEffect } from 'react';
import { Download, Loader2 } from 'lucide-react';
import './Auth.css';

export default function Auth({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);
  const [markaId, setMarkaId] = useState('');
  const [pin, setPin] = useState('');
  const [email, setEmail] = useState('');
  const [amount, setAmount] = useState(5000); // Naira; matches the Starter pack
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [successData, setSuccessData] = useState(null);
  const [showForgotPin, setShowForgotPin] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotMsg, setForgotMsg] = useState('');

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const PAYSTACK_PUBLIC_KEY = import.meta.env.VITE_PAYSTACK_PUBLIC_KEY || 'pk_test_replace_with_your_key_here'; // Replace in .env

  useEffect(() => {
    // Dynamically load Paystack JS
    const script = document.createElement('script');
    script.src = 'https://js.paystack.co/v1/inline.js';
    script.async = true;
    document.body.appendChild(script);
    return () => {
      document.body.removeChild(script);
    };
  }, []);

  const handleForgotPin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setForgotMsg('');
    try {
      const res = await fetch(`${API_URL}/auth/forgot-pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setForgotMsg(data.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ marka_id: markaId, pin }),
      });
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Login failed');
      }
      
      localStorage.setItem('marka_token', data.access_token);
      localStorage.setItem('marka_credits', data.credits);
      onLogin(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = (e) => {
    e.preventDefault();
    if (!email) {
      setError("Email is required to purchase credits.");
      return;
    }
    
    setError('');
    
    if (typeof PaystackPop === 'undefined') {
      setError("Payment system is loading. Please try again in a second.");
      return;
    }

    const handler = PaystackPop.setup({
      key: PAYSTACK_PUBLIC_KEY,
      email: email,
      amount: amount * 100, // Dynamic amount in kobo
      currency: 'NGN',
      metadata: {
        custom_fields: [
          {
            display_name: "Action",
            variable_name: "action",
            value: "new_id_generation"
          }
        ]
      },
      // NOTE: Paystack rejects an async callback ("callback must be a valid
      // function"), so keep this sync and run the async work in an IIFE.
      callback: (response) => {
        (async () => {
          setLoading(true);
          try {
            const res = await fetch(`${API_URL}/auth/purchase-id`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                reference: response.reference,
                email: email
              }),
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'Failed to verify payment and generate ID');

            setSuccessData(data);
          } catch (err) {
            setError(err.message);
          } finally {
            setLoading(false);
          }
        })();
      },
      onClose: () => {
        setLoading(false);
      }
    });
    
    handler.openIframe();
  };

  if (successData) {
    return (
      <div className="auth-container">
        <div className="auth-card success-card">
          <div className="icon-wrapper">
            <Download size={32} />
          </div>
          <h2>Your Success Card</h2>
          <p className="subtitle">Payment verified! Save these details! You need them to log in.</p>
          
          <div className="credentials-box">
            <div className="credential-item">
              <span className="label">MARKA ID</span>
              <span className="value text-primary">{successData.marka_id}</span>
            </div>
            <div className="credential-item">
              <span className="label">PIN</span>
              <span className="value text-dark pin-value">{successData.pin}</span>
            </div>
          </div>

          <div className="bg-green-50 p-3 rounded-lg mb-6 text-green-700 font-bold text-sm border border-green-200">
            {successData.credits} Credits have been added to your account!
          </div>
          
          <button 
            className="btn btn-primary w-full"
            onClick={() => {
              setSuccessData(null);
              setIsLogin(true);
              setMarkaId(successData.marka_id);
              setPin('');
            }}
          >
            I have saved them, take me to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-header">
        <h1>MARKA</h1>
        <p>Keep the Paper. Eliminate the Marking.</p>
      </div>

      <div className="auth-card">
        <div className="auth-tabs">
          <button 
            className={`tab ${isLogin ? 'active' : ''}`}
            onClick={() => { setIsLogin(true); setError(''); setShowForgotPin(false); }}
          >
            Login
          </button>
          <button 
            className={`tab ${!isLogin ? 'active' : ''}`}
            onClick={() => { setIsLogin(false); setError(''); setShowForgotPin(false); }}
          >
            Buy Credits to Start
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}

        {showForgotPin ? (
          <form onSubmit={handleForgotPin} className="auth-form">
            <h3 className="text-lg font-bold mb-2">Recover PIN</h3>
            <p className="text-sm text-gray-600 mb-4">Enter the email you used when purchasing your credits.</p>
            {forgotMsg && <div className="bg-green-50 text-green-700 p-3 rounded-lg mb-4 text-sm border border-green-200">{forgotMsg}</div>}
            <div className="form-group">
              <label>Email Address</label>
              <input 
                type="email" 
                value={forgotEmail}
                onChange={(e) => setForgotEmail(e.target.value)}
                placeholder="your@email.com"
                required
              />
            </div>
            <button type="submit" disabled={loading} className="btn btn-primary w-full bg-blue-600 text-white font-bold py-2 rounded-lg mb-3">
              {loading ? <Loader2 className="animate-spin mx-auto" size={20} /> : 'Send Recovery Link'}
            </button>
            <button type="button" className="w-full text-sm text-gray-500 hover:text-gray-800 py-2" onClick={() => setShowForgotPin(false)}>
              Back to Login
            </button>
          </form>
        ) : isLogin ? (
          <form onSubmit={handleLogin} className="auth-form">
            <div className="form-group">
              <label>MARKA ID</label>
              <input 
                type="text" 
                value={markaId}
                onChange={(e) => setMarkaId(e.target.value.toUpperCase())}
                placeholder="MK-XXXX"
                className="input-mono uppercase text-large"
                required
              />
            </div>
            <div className="form-group">
              <label>4-Digit PIN</label>
              <input 
                type="password" 
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
                placeholder="••••"
                className="input-mono letter-spacing text-xl text-center"
                required
              />
            </div>
            <button type="submit" disabled={loading} className="btn btn-primary w-full">
              {loading ? <Loader2 className="animate-spin" size={20} /> : 'Login'}
            </button>
          </form>
        ) : (
          <form onSubmit={handlePurchase} className="auth-form">
            <div className="bg-blue-50 text-blue-800 p-4 rounded-lg mb-4 border border-blue-100">
              <p className="font-bold text-center mb-2">Unlock Your MARKA ID</p>
              <p className="text-sm text-center">Select a package to generate your ID and instantly receive credits for grading exams.</p>
            </div>

            <div className="form-group">
              <label>Select Package</label>
              <select 
                className="w-full px-4 py-3 rounded-lg border border-gray-300 font-bold focus:ring-2 focus:ring-blue-500 bg-white"
                onChange={(e) => setAmount(Number(e.target.value))}
                value={amount}
              >
                <option value={5000}>Starter — ₦5,000 (100 credits)</option>
                <option value={11250}>Growth — ₦11,250 (250 credits)</option>
                <option value={20000}>School — ₦20,000 (500 credits)</option>
                <option value={35000}>Institution — ₦35,000 (1,000 credits)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Email Address</label>
              <input 
                type="email" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
              />
              <span className="help-text">Used to send your receipt and recover your PIN.</span>
            </div>

            <div className="bg-yellow-50 p-3 rounded text-xs text-yellow-800 font-medium border border-yellow-200 mt-2">
              <span className="font-bold uppercase block mb-1">Testing Note:</span>
              Since you are using a Test API Key, use card number <code className="bg-yellow-200 px-1 py-0.5 rounded">4084084084084081</code> with any CVV to simulate a successful payment.
            </div>

            <button type="submit" disabled={loading} className="btn btn-success w-full bg-green-600 hover:bg-green-700 text-white shadow-md hover:shadow-lg transition-all py-3 rounded-lg font-bold mt-4">
              {loading ? <Loader2 className="animate-spin mx-auto" size={20} /> : `Pay ₦${amount.toLocaleString()} to Generate ID`}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
