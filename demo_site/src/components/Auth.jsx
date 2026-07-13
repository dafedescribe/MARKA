import React, { useState, useEffect } from 'react';
import { Download, Loader2, KeyRound, Coins, ShieldAlert, CheckCircle2, ArrowRight } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function Auth({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);
  const [markaId, setMarkaId] = useState('');
  const [pin, setPin] = useState('');
  const [email, setEmail] = useState('');
  const [amount, setAmount] = useState(5000); // Naira; matches the Starter pack
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [successData, setSuccessData] = useState(null);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const PAYSTACK_PUBLIC_KEY = import.meta.env.VITE_PAYSTACK_PUBLIC_KEY || 'pk_test_replace_with_your_key_here';

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

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center font-sans py-12 px-4 sm:px-6 lg:px-8 select-none">
      <div className="absolute top-8 left-8 flex items-center gap-3">
        <img src="/favicon.png" alt="MARKA Logo" className="h-9 w-auto object-contain drop-shadow-sm" />
        <div>
          <span className="text-xl font-black text-[#3B0042] tracking-wider">MARKA</span>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {successData ? (
          <motion.div
            key="success-screen"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="max-w-xl w-full mx-auto bg-white p-8 rounded-2xl border border-gray-100 shadow-xl space-y-6 text-center"
          >
            <div className="bg-emerald-50 text-emerald-700 p-4 rounded-xl border border-emerald-100 flex items-center gap-3 justify-center text-sm font-bold">
              <CheckCircle2 className="w-5 h-5" />
              Payment Verified Successfully!
            </div>

            <div className="bg-purple-50/50 p-6 rounded-2xl border border-purple-100 space-y-4">
              <p className="text-xs text-gray-500 font-semibold uppercase">
                YOUR SECURITY ACCESS KEYWORDS
              </p>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
                  <span className="block text-[10px] font-bold text-gray-400 uppercase mb-1">
                    MARKA ID
                  </span>
                  <span className="text-xl font-mono font-black text-[#3B0042] tracking-wider select-all">
                    {successData.marka_id}
                  </span>
                </div>
                <div className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
                  <span className="block text-[10px] font-bold text-gray-400 uppercase mb-1">
                    SECRET PIN
                  </span>
                  <span className="text-xl font-mono font-black text-amber-600 select-all">
                    {successData.pin}
                  </span>
                </div>
              </div>

              <div className="bg-white p-3 rounded-xl border border-gray-100 text-sm font-bold text-[#3B0042]">
                {successData.credits} Credits added to your account
              </div>

              <p className="text-[11px] text-gray-400 leading-normal px-4">
                Write these down immediately. You will use these
                anytime to log in and access your balance.
              </p>
            </div>

            <button
              onClick={() => {
                setSuccessData(null);
                setIsLogin(true);
                setMarkaId(successData.marka_id);
                setPin('');
              }}
              className="w-full py-4 bg-[#3B0042] text-white hover:bg-[#2c0032] font-bold rounded-xl transition-all shadow-md active:scale-95"
            >
              I have saved them, proceed to Login
            </button>
          </motion.div>
        ) : (
          <motion.div
            key={isLogin ? 'login' : 'buy'}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.15 }}
            className="max-w-md w-full bg-white p-8 rounded-2xl border border-gray-100 shadow-xl space-y-8"
          >
            {/* Tabs */}
            <div className="grid grid-cols-2 gap-4 bg-gray-50 p-1.5 rounded-xl border border-gray-100">
              <button
                type="button"
                onClick={() => { setIsLogin(true); setError(''); }}
                className={`py-2.5 rounded-lg text-xs font-bold transition-all ${
                  isLogin
                    ? "bg-white text-[#3B0042] shadow-sm"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                Login
              </button>
              <button
                type="button"
                onClick={() => { setIsLogin(false); setError(''); }}
                className={`py-2.5 rounded-lg text-xs font-bold transition-all ${
                  !isLogin
                    ? "bg-white text-[#3B0042] shadow-sm"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                Buy Credits
              </button>
            </div>

            {error && (
              <div className="bg-red-50 text-red-700 p-3.5 rounded-xl border border-red-100 text-xs font-bold flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 flex-shrink-0" />
                {error}
              </div>
            )}

            {isLogin ? (
              <form onSubmit={handleLogin} className="space-y-6">
                <div className="text-center space-y-2 pb-2">
                  <div className="w-12 h-12 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto mb-2">
                    <KeyRound className="w-6 h-6" />
                  </div>
                  <h2 className="text-2xl font-black text-gray-900">Access Your Credits</h2>
                  <p className="text-xs text-gray-500">
                    No email or password registration is required.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-gray-600 uppercase tracking-wide">
                      MARKA ID
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. M-123456"
                      value={markaId}
                      onChange={(e) => setMarkaId(e.target.value.toUpperCase())}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] font-mono text-sm uppercase transition-colors"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-gray-600 uppercase tracking-wide">
                      PIN
                    </label>
                    <input
                      type="password"
                      required
                      maxLength={4}
                      placeholder="••••"
                      value={pin}
                      onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] font-mono text-xl text-center tracking-[1em] transition-colors"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-4 bg-[#3B0042] hover:bg-[#2c0032] disabled:bg-purple-900/50 text-white font-extrabold rounded-xl transition-all flex items-center justify-center gap-2 shadow-md active:scale-95"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Verifying credits...
                    </>
                  ) : (
                    "Continue to Dashboard"
                  )}
                </button>
              </form>
            ) : (
              <form onSubmit={handlePurchase} className="space-y-6">
                <div className="text-center space-y-2 pb-2">
                  <div className="w-12 h-12 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto mb-2">
                    <Coins className="w-6 h-6" />
                  </div>
                  <h2 className="text-2xl font-black text-gray-900">Purchase Credits</h2>
                  <p className="text-xs text-gray-500">
                    Instant activation via Paystack. Your ID will be generated automatically.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-gray-600 uppercase tracking-wide">
                      Select Credits Volume
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: 'Starter', price: 5000, credits: 100 },
                        { label: 'Growth', price: 11250, credits: 250 },
                        { label: 'School', price: 20000, credits: 500 },
                        { label: 'Institution', price: 35000, credits: 1000 }
                      ].map((pkg) => (
                        <div
                          key={pkg.price}
                          onClick={() => setAmount(pkg.price)}
                          className={`cursor-pointer border p-3 rounded-xl text-center transition-all ${
                            amount === pkg.price
                              ? "border-[#3B0042] bg-purple-50/40 text-[#3B0042] ring-2 ring-[#3B0042]/10"
                              : "border-gray-200 hover:border-gray-300"
                          }`}
                        >
                          <span className="block text-base font-black">{pkg.credits}</span>
                          <span className="block text-[10px] text-gray-400 font-bold uppercase mt-0.5">
                            ₦{pkg.price.toLocaleString()}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2 pt-2">
                    <label className="block text-xs font-bold text-gray-600 uppercase tracking-wide">
                      Email Address
                    </label>
                    <input
                      type="email"
                      required
                      placeholder="your@email.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] text-sm transition-colors"
                    />
                    <p className="text-[10px] text-gray-400">Used strictly for payment receipt and PIN recovery.</p>
                  </div>
                </div>
                
                <div className="bg-amber-50 p-3 rounded-xl border border-amber-200 flex flex-col gap-1">
                  <span className="text-[10px] font-bold text-amber-800 uppercase tracking-wider">Test Mode Warning</span>
                  <span className="text-[11px] text-amber-700">Use card number <span className="font-mono bg-amber-100 px-1 rounded">4084084084084081</span> with any CVV.</span>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-4 bg-[#3B0042] hover:bg-[#2c0032] disabled:bg-gray-300 text-white font-extrabold rounded-xl transition-all flex items-center justify-center gap-2 shadow-md active:scale-95"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Initiating Paystack Checkout...
                    </>
                  ) : (
                    <>
                      Pay ₦{amount.toLocaleString()} via Paystack
                      <ArrowRight className="w-5 h-5" />
                    </>
                  )}
                </button>
              </form>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
