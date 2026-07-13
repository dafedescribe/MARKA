import React, { useState, useEffect } from "react";
import LandingPage from "./components/LandingPage";
import DashboardAndMarking from "./components/DashboardAndMarking";
import { UserAccount, BatchMarking, GradedPaper } from "./types";
import { motion, AnimatePresence } from "motion/react";
import { CheckCircle2, X } from "lucide-react";

export default function App() {
  const [user, setUser] = useState<UserAccount | null>(null);
  const [batches, setBatches] = useState<BatchMarking[]>([]);
  const [papers, setPapers] = useState<GradedPaper[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Status banner notification
  const [bannerMsg, setBannerMsg] = useState<string | null>(null);

  // Detect and verify saved browser credential cookies/localStorage on first mount
  const API_BASE = window.location.origin;

  useEffect(() => {
    const savedId = localStorage.getItem("marka_id");
    const savedPin = localStorage.getItem("marka_pin");

    if (savedId && savedPin) {
      // Auto login verification on session load
      fetch(`${API_BASE}/api/user-data?markaId=${savedId}&pin=${savedPin}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.user) {
            setUser(data.user);
            setBatches(data.batches || []);
            setPapers(data.papers || []);
          } else {
            localStorage.removeItem("marka_id");
            localStorage.removeItem("marka_pin");
          }
        })
        .catch(() => {
          // If offline, still allow offline preview with empty mock lists
          console.warn("Could not sync remote cloud OMR session, falling back.");
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, [API_BASE]);

  const handleLoginSuccess = async (loggedInUser: UserAccount) => {
    localStorage.setItem("marka_id", loggedInUser.markaId);
    localStorage.setItem("marka_pin", loggedInUser.pin);
    setUser(loggedInUser);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/user-data?markaId=${loggedInUser.markaId}&pin=${loggedInUser.pin}`);
      const data = await res.json();
      if (res.ok) {
        setBatches(data.batches || []);
        setPapers(data.papers || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("marka_id");
    localStorage.removeItem("marka_pin");
    setUser(null);
    setBatches([]);
    setPapers([]);
  };

  const triggerBanner = (msg: string | null) => {
    setBannerMsg(msg);
    if (msg) {
      setTimeout(() => {
        setBannerMsg(null);
      }, 4000);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center font-sans">
        <div className="w-10 h-10 rounded-xl bg-[#3B0042] animate-bounce flex items-center justify-center text-white font-extrabold text-lg">
          M
        </div>
        <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mt-4">
          Syncing OMR Cloud Database...
        </p>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-gray-50 select-none">
      {/* Toast Notification Banner */}
      <AnimatePresence>
        {bannerMsg && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed top-6 right-6 z-50 bg-purple-950 text-white p-4 rounded-xl shadow-xl flex items-center gap-3 border border-white/10"
          >
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            <span className="text-xs font-bold">{bannerMsg}</span>
            <button
              onClick={() => setBannerMsg(null)}
              className="p-1 rounded-full hover:bg-white/10 text-purple-300"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {!user ? (
          <LandingPage
            onLoginSuccess={handleLoginSuccess}
            onLaunchDemo={() => handleLoginSuccess({ markaId: "MARKA-DEMO", pin: "1234", credits: 382, createdAt: "" })}
            onSetBanner={triggerBanner}
            apiBase={API_BASE}
          />
        ) : (
          <DashboardAndMarking
            user={user}
            initialBatches={batches}
            initialPapers={papers}
            onLogout={handleLogout}
            apiBase={API_BASE}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
