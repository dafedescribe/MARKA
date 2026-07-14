import React, { useState, useEffect, useRef } from 'react';
import { supabase, setSupabaseToken } from '../lib/supabase';
import { LogOut } from 'lucide-react';
import { AnimatePresence } from 'motion/react';
import DashboardHome from './DashboardHome';
import ExamBuilder from './ExamBuilder';
import UploadQueue from './UploadQueue';
import Gallery from './Gallery';


export default function Dashboard({ token, onLogout }) {
  const [credits, setCredits] = useState(parseInt(localStorage.getItem('marka_credits') || '0'));
  const [scans, setScans] = useState([]);
  const [scanPage, setScanPage] = useState(0);
  const [hasMoreScans, setHasMoreScans] = useState(true);
  const [exams, setExams] = useState([]);
  const [isOffline, setIsOffline] = useState(false);
  const [scansError, setScansError] = useState(null);
  const [userEmail, setUserEmail] = useState('');
  const [markaId, setMarkaId] = useState('');
  
  // Navigation
  const [currentView, setCurrentView] = useState('dashboard'); // dashboard, builder, upload, gallery

  // Exam Builder
  const [examCode, setExamCode] = useState('MARKA');
  const [newExamCode, setNewExamCode] = useState('');
  const [questionsCount, setQuestionsCount] = useState(20);
  const [optionsCount, setOptionsCount] = useState(5);
  const [answerKey, setAnswerKey] = useState({});
  const [activeBuilderQ, setActiveBuilderQ] = useState(1);
  const [examSaving, setExamSaving] = useState(false);
  const [examMsg, setExamMsg] = useState('');
  
  // Upload Queue
  const [uploadQueue, setUploadQueue] = useState([]);
  const [isUploadingBatch, setIsUploadingBatch] = useState(false);
  const fileInputRef = useRef(null);

  // Gallery Filters
  const [searchQuery, setSearchQuery] = useState("");

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // Authenticate the Supabase client with our backend JWT before any read.
  // Without this every supabase query runs as anon and RLS returns nothing.
  useEffect(() => { setSupabaseToken(token); }, [token]);

  useEffect(() => {
    // Dynamically load Paystack JS
    const script = document.createElement('script');
    script.src = 'https://js.paystack.co/v1/inline.js';
    script.async = true;
    document.body.appendChild(script);

    setSupabaseToken(token);
    fetchScans(0, false);
    fetchExams();
    refreshCredits();
    const channel = supabase
      .channel('public:scans')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'scans' }, (payload) => {
        fetchScans(0, false);
        refreshCredits();
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, []);

  // Keyboard navigation for Answer Key Builder
  useEffect(() => {
    if (currentView !== "builder") return;

    const handleKeyDown = (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveBuilderQ((prev) => Math.min(questionsCount, prev + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveBuilderQ((prev) => Math.max(1, prev - 1));
      } else if (["a", "b", "c", "d", "e", "A", "B", "C", "D", "E"].includes(e.key)) {
        const option = e.key.toUpperCase();
        if (optionsCount >= (option.charCodeAt(0) - 64)) {
          setAnswerKey((prev) => ({ ...prev, [activeBuilderQ]: option }));
          if (activeBuilderQ < questionsCount) {
            setActiveBuilderQ((prev) => prev + 1);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentView, activeBuilderQ, questionsCount, optionsCount]);

  // Keep answers within the current question count; do NOT auto-fill untouched
  // questions (they must be answered explicitly — see the guard in handleCreateExam).
  useEffect(() => {
    setAnswerKey((prev) => {
      const key = {};
      for (let i = 1; i <= questionsCount; i++) {
        if (prev[i] !== undefined) key[i] = prev[i];
      }
      return key;
    });
  }, [questionsCount]);

  const refreshCredits = async () => {
    try {
      const { data } = await supabase.from('users').select('credits, email, marka_id').single();
      if (data) {
        setCredits(data.credits);
        setUserEmail(data.email);
        setMarkaId(data.marka_id);
        localStorage.setItem('marka_credits', data.credits);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchScans = async (page = 0, append = false) => {
    try {
      const { data, error } = await supabase
        .from('scans')
        .select('*')
        .order('created_at', { ascending: false })
        .range(page * 100, (page + 1) * 100 - 1);

      // A real query error (auth/RLS/permission) must NOT look like "no scans" —
      // surface it so the user knows the list failed to load rather than assuming
      // their grading was lost.
      if (error) throw error;

      if (data) {
        setHasMoreScans(data.length === 100);
        const scansWithUrls = await Promise.all(data.map(async (scan) => {
          if (scan.status === 'success' && scan.graded_image_path) {
            const { data: urlData } = await supabase.storage
              .from('graded_images')
              .createSignedUrl(scan.graded_image_path, 3600);
            return { ...scan, thumbnailUrl: urlData?.signedUrl };
          }
          return scan;
        }));
        if (append) {
          setScans(prev => [...prev, ...scansWithUrls]);
        } else {
          setScans(scansWithUrls);
          setScanPage(0);
        }
      }
      setScansError(null);
      setIsOffline(false);
    } catch (e) {
      console.error("Error fetching scans:", e);
      if (e.message === 'Failed to fetch' || e.name === 'TypeError') setIsOffline(true);
      setScansError(e.message || 'Could not load your scans. Please retry.');
    }
  };

  const loadMoreScans = () => {
    const nextPage = scanPage + 1;
    setScanPage(nextPage);
    fetchScans(nextPage, true);
  };

  const fetchExams = async () => {
    try {
      const res = await fetch(`${API_URL}/exams`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      setExams(data.exams || []);
      setIsOffline(false);
    } catch (e) {
      console.error("Error fetching exams:", e);
      if (e.message === 'Failed to fetch' || e.name === 'TypeError') setIsOffline(true);
    }
  };

  const handleTopUp = () => {
    if (!userEmail || !markaId) {
      alert("User details not fully loaded. Please wait a moment or refresh.");
      return;
    }
    if (typeof PaystackPop === 'undefined') {
      alert("Payment system is loading. Please try again in a second.");
      return;
    }
    const handler = PaystackPop.setup({
      key: import.meta.env.VITE_PAYSTACK_PUBLIC_KEY || 'pk_test_replace_with_your_key_here',
      email: userEmail,
      amount: 5000 * 100, // Top up starter pack (100 credits)
      currency: 'NGN',
      metadata: { 
        custom_fields: [
          { display_name: "MARKA ID", variable_name: "marka_id", value: markaId }
        ]
      },
      callback: (response) => {
        alert("Payment successful! Your credits will be updated momentarily.");
        setTimeout(refreshCredits, 2000);
      }
    });
    handler.openIframe();
  };

  const handleCreateExam = async () => {
    const code = newExamCode.trim().toUpperCase();
    if (!code) { setExamMsg('Enter an exam name/code.'); return; }

    // Guard: every question must be explicitly answered (a letter, several
    // letters, or ★ bonus). Untouched questions are no longer defaulted to "A".
    const missing = [];
    for (let i = 1; i <= questionsCount; i++) {
      const v = answerKey[i];
      const isSet = v === '*'
        || (Array.isArray(v) ? v.length > 0 : (typeof v === 'string' && v.length > 0));
      if (!isSet) missing.push(i);
    }
    if (missing.length) {
      const preview = missing.slice(0, 6).map((n) => `Q${n}`).join(', ');
      setExamMsg(`${missing.length} question${missing.length > 1 ? 's' : ''} unanswered (${preview}${missing.length > 6 ? '…' : ''}). Mark every question, or use ★ for bonus.`);
      return;
    }

    setExamSaving(true);
    setExamMsg('');
    try {
      const res = await fetch(`${API_URL}/exams`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ exam_code: code, answers: answerKey }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to save exam');
      setNewExamCode('');
      await fetchExams();
      setExamCode(code);
      setCurrentView('upload');
    } catch (e) {
      setExamMsg(e.message);
    } finally {
      setExamSaving(false);
    }
  };

  const wipeImage = async (scanId) => {
    if (!scanId) return;
    if (!window.confirm('Delete this scan’s image to reclaim space? The score is kept.')) return;
    try {
      const res = await fetch(`${API_URL}/scans/${scanId}/wipe-image`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || 'Failed to delete'); }
      setScans(prev => prev.map(s => s.scan_id === scanId
        ? { ...s, graded_image_path: null, image_path: null, thumbnailUrl: null } : s));
    } catch (e) {
      alert(e.message);
    }
  };

  const handleWipeAllRaw = async () => {
    if (!window.confirm('Delete ALL original high-res images to reclaim space? (Your graded images and scores will be kept). This cannot be undone.')) return;
    try {
      const res = await fetch(`${API_URL}/scans/wipe-all-raw`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to delete batch');
      alert(`Successfully deleted ${data.deleted} original images to reclaim space.`);
      fetchScans(0, false);
    } catch (e) {
      alert(e.message);
    }
  };

  const expiryInfo = (createdAt) => {
    if (!createdAt) return null;
    const ms = new Date(createdAt).getTime() + 7 * 24 * 3600 * 1000 - Date.now();
    if (ms <= 0) return { text: 'Images expired', urgent: true };
    const days = Math.floor(ms / (24 * 3600 * 1000));
    const hours = Math.floor((ms % (24 * 3600 * 1000)) / (3600 * 1000));
    return { text: `Expires in ${days}d ${hours}h`, urgent: days < 2 };
  };

  const checkBlur = async (file) => {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const scale = Math.min(500 / img.width, 500 / img.height);
        canvas.width = img.width * scale;
        canvas.height = img.height * scale;
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        let sum = 0, sumSq = 0, diffCount = 0;
        
        for (let y = 0; y < canvas.height; y++) {
          for (let x = 1; x < canvas.width; x++) {
            const idx = (y * canvas.width + x) * 4;
            const prevIdx = (y * canvas.width + (x - 1)) * 4;
            const lum = 0.299*data[idx] + 0.587*data[idx+1] + 0.114*data[idx+2];
            const prevLum = 0.299*data[prevIdx] + 0.587*data[prevIdx+1] + 0.114*data[prevIdx+2];
            const diff = Math.abs(lum - prevLum);
            sum += diff;
            sumSq += diff * diff;
            diffCount++;
          }
        }
        const mean = sum / diffCount;
        const variance = (sumSq / diffCount) - (mean * mean);
        URL.revokeObjectURL(url);
        resolve(variance < 30);
      };
      img.onerror = () => resolve(false);
      img.src = url;
    });
  };

  const handleFilesAdded = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    if (credits < files.length && credits !== -1 && token) {
      alert(`You only have ${credits} credits but tried to upload ${files.length} images! Please top up.`);
      return;
    }

    const newItems = await Promise.all(files.map(async (f, index) => {
      const isBlurry = await checkBlur(f);
      return {
        id: `temp_${Date.now()}_${index}`,
        file: f,
        filename: f.name,
        status: "queued",
        isBlurry,
        error: null
      };
    }));
    
    setUploadQueue(prev => [...prev, ...newItems]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
  const runBatchProcessing = async () => {
    setIsUploadingBatch(true);
    let wakeLock = null;
    try {
      if ('wakeLock' in navigator) {
        wakeLock = await navigator.wakeLock.request('screen');
      }
    } catch (err) {
      console.warn("WakeLock not supported or denied.");
    }
    
    const currentQueue = [...uploadQueue];
    for (let i = 0; i < currentQueue.length; i++) {
      const item = currentQueue[i];
      if (item.status === "complete" || item.status === "failed") continue;

      setUploadQueue((prev) =>
        prev.map((itm) => (itm.id === item.id ? { ...itm, status: "uploading" } : itm))
      );

      try {
        const scanId = `${Date.now()}_${Math.floor(Math.random() * 1000)}`;
        
        // Optimistic scan insertion for realtime feel in gallery
        const optimisticScan = {
          id: item.id,
          scan_id: scanId,
          status: 'processing',
          created_at: new Date().toISOString()
        };
        setScans(prev => [optimisticScan, ...prev]);

        let triggerRes;
        // Retry logic for cold starts (up to 2 retries)
        for (let attempt = 1; attempt <= 3; attempt++) {
          try {
            const res = await fetch(`${API_URL}/upload/presigned-url?scan_id=${scanId}`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) throw new Error("API not ready");
            const { upload_url } = await res.json();

            const uploadRes = await fetch(upload_url, {
              method: 'PUT',
              headers: { 'Content-Type': item.file.type },
              body: item.file
            });

            if (!uploadRes.ok) throw new Error('Failed to upload image directly to Supabase');
            
            setUploadQueue((prev) =>
              prev.map((itm) => (itm.id === item.id ? { ...itm, status: "grading" } : itm))
            );

            triggerRes = await fetch(`${API_URL}/process-scan`, {
              method: 'POST',
              headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
              },
              body: JSON.stringify({
                scan_id: scanId,
                exam_code: examCode
              })
            });
            break; // Success
          } catch (err) {
            if (attempt === 3) throw err;
            await new Promise(r => setTimeout(r, 2000)); // wait 2s before retry
          }
        }

        if (!triggerRes.ok) throw new Error('Failed to trigger processing');
        
        setUploadQueue((prev) =>
          prev.map((itm) =>
            itm.id === item.id ? { ...itm, status: "complete" } : itm
          )
        );
      } catch (error) {
        console.error(error);
        setUploadQueue((prev) =>
          prev.map((itm) =>
            itm.id === item.id ? { ...itm, status: "failed", error: error.message } : itm
          )
        );
        setScans(prev => prev.filter(s => s.id !== item.id)); // Remove optimistic on fail
      }
    }
    
    setIsUploadingBatch(false);
    if (wakeLock) {
      wakeLock.release().catch(() => {});
    }

    // Grading finishes asynchronously on the server. Don't rely solely on the
    // realtime subscription (it may be disabled/dropped) — poll a few times so
    // the optimistic "processing" cards reconcile to the real graded results.
    fetchScans(0, false);
    [3000, 7000, 12000, 20000].forEach((ms) => setTimeout(() => fetchScans(0, false), ms));
  };

  const goToLibrary = () => {
    fetchScans(0, false);
    setCurrentView('gallery');
  };

  const handleExport = async (exportExamCode) => {
    try {
      const res = await fetch(`${API_URL}/export/${exportExamCode}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error("Failed to export");
      const { export_url } = await res.json();
      window.location.href = export_url;
    } catch (e) {
      alert(e.message);
    }
  };

  const retryFailed = () => {
    // Reset all failed items back to 'queued' so runBatchProcessing picks them up
    setUploadQueue(prev => prev.map(item =>
      item.status === 'failed' ? { ...item, status: 'queued', error: null } : item
    ));
    // Immediately kick off batch processing again
    setTimeout(() => runBatchProcessing(), 100);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans select-none">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex flex-col md:flex-row justify-between items-center gap-4 sticky top-0 z-30 shadow-sm transition-all duration-200">
        <div className="flex items-center gap-4">
          <img src="/favicon.png" alt="MARKA Logo" className="h-14 w-auto object-contain drop-shadow-sm" />
        </div>
        
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => setCurrentView("dashboard")} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "dashboard" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>Dashboard</button>
          <button onClick={() => { setNewExamCode(""); setQuestionsCount(20); setCurrentView("builder"); }} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "builder" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>New Exam Sheet</button>
          <button onClick={() => setCurrentView("upload")} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "upload" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>Scan & Grade</button>
          <button onClick={goToLibrary} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "gallery" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>OMR Library</button>
          <div className="w-px h-6 bg-gray-200 mx-2"></div>
          <div className="flex items-center gap-2 bg-purple-50 px-3 py-1.5 rounded-lg border border-purple-100">
            <span className="text-xs font-bold text-purple-900 uppercase">Credits</span>
            <span className="text-sm font-black text-[#3B0042]">{credits.toLocaleString()}</span>
            <button onClick={handleTopUp} className="ml-2 px-2 py-1 bg-[#3B0042] text-white text-[10px] font-bold rounded hover:bg-[#2c0032] transition-colors uppercase">
              Top Up
            </button>
          </div>
          <button onClick={onLogout} className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Logout">
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">
        {isOffline && (
          <div className="mb-4 bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-xl text-sm font-bold flex items-center justify-between">
            <span>Network Error: Could not reach MARKA services. Retrying...</span>
            <button onClick={() => { fetchScans(); fetchExams(); }} className="underline hover:text-amber-900">Retry Now</button>
          </div>
        )}
        <AnimatePresence mode="wait">
          {currentView === "dashboard" && <DashboardHome credits={credits} scans={scans} exams={exams} setExamCode={setExamCode} setCurrentView={setCurrentView} handleExport={handleExport} setQuestionsCount={setQuestionsCount} setAnswerKey={setAnswerKey} setNewExamCode={setNewExamCode} handleWipeAllRaw={handleWipeAllRaw} />}
          {currentView === "builder" && <ExamBuilder newExamCode={newExamCode} setNewExamCode={setNewExamCode} questionsCount={questionsCount} setQuestionsCount={setQuestionsCount} optionsCount={optionsCount} setOptionsCount={setOptionsCount} answerKey={answerKey} setAnswerKey={setAnswerKey} activeBuilderQ={activeBuilderQ} setActiveBuilderQ={setActiveBuilderQ} examSaving={examSaving} examMsg={examMsg} handleCreateExam={handleCreateExam} setCurrentView={setCurrentView} />}
          {currentView === "upload" && <UploadQueue examCode={examCode} setExamCode={setExamCode} exams={exams} uploadQueue={uploadQueue} setUploadQueue={setUploadQueue} fileInputRef={fileInputRef} handleFilesAdded={handleFilesAdded} runBatchProcessing={runBatchProcessing} isUploadingBatch={isUploadingBatch} retryFailed={retryFailed} goToLibrary={goToLibrary} />}
          {currentView === "gallery" && <Gallery scans={scans} fetchScans={() => fetchScans(0, false)} loadMoreScans={loadMoreScans} hasMoreScans={hasMoreScans} wipeImage={wipeImage} expiryInfo={expiryInfo} searchQuery={searchQuery} setSearchQuery={setSearchQuery} scansError={scansError} />}
        </AnimatePresence>
      </main>
    </div>
  );
}
