import React, { useState, useEffect, useRef } from 'react';
import { supabase } from '../lib/supabase';
import { LogOut } from 'lucide-react';
import { AnimatePresence } from 'motion/react';
import DashboardHome from './DashboardHome';
import ExamBuilder from './ExamBuilder';
import UploadQueue from './UploadQueue';
import Gallery from './Gallery';
import PrintableOMRSheet from './PrintableOMRSheet';

export default function Dashboard({ token, onLogout }) {
  const [credits, setCredits] = useState(parseInt(localStorage.getItem('marka_credits') || '0'));
  const [scans, setScans] = useState([]);
  const [exams, setExams] = useState([]);
  
  // Navigation
  const [currentView, setCurrentView] = useState('dashboard'); // dashboard, builder, upload, gallery

  // Exam Builder
  const [examCode, setExamCode] = useState('MARKA');
  const [newExamCode, setNewExamCode] = useState('');
  const [questionsCount, setQuestionsCount] = useState(20);
  const [optionsCount, setOptionsCount] = useState(4);
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

  useEffect(() => {
    fetchScans();
    fetchExams();
    const channel = supabase
      .channel('public:scans')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'scans' }, (payload) => {
        fetchScans();
        refreshCredits();
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
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

  useEffect(() => {
    const key = {};
    for (let i = 1; i <= questionsCount; i++) {
      key[i] = answerKey[i] || "A";
    }
    setAnswerKey(key);
  }, [questionsCount]);

  const refreshCredits = async () => {
    try {
      await supabase.auth.setSession({ access_token: token, refresh_token: '' });
      const { data } = await supabase.from('users').select('credits').single();
      if (data) {
        setCredits(data.credits);
        localStorage.setItem('marka_credits', data.credits);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchScans = async () => {
    try {
      await supabase.auth.setSession({ access_token: token, refresh_token: '' });
      const { data } = await supabase
        .from('scans')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(100);
        
      if (data) {
        const scansWithUrls = await Promise.all(data.map(async (scan) => {
          if (scan.status === 'success' && scan.graded_image_path) {
            const { data: urlData } = await supabase.storage
              .from('graded_images')
              .createSignedUrl(scan.graded_image_path, 3600);
            return { ...scan, thumbnailUrl: urlData?.signedUrl };
          }
          return scan;
        }));
        setScans(scansWithUrls);
      }
    } catch (e) {
      console.error("Error fetching scans:", e);
    }
  };

  const fetchExams = async () => {
    try {
      const res = await fetch(`${API_URL}/exams`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      setExams(data.exams || []);
    } catch (e) {
      console.error("Error fetching exams:", e);
    }
  };

  const handleCreateExam = async () => {
    const code = newExamCode.trim().toUpperCase();
    if (!code) { setExamMsg('Enter an exam name/code.'); return; }
    
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

        const res = await fetch(`${API_URL}/upload/presigned-url?scan_id=${scanId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
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

        const triggerRes = await fetch(`${API_URL}/process-scan`, {
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

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans select-none">
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex flex-col md:flex-row justify-between items-center gap-4 sticky top-0 z-30 shadow-sm transition-all duration-200">
        <div className="flex items-center gap-4">
          <img src="/favicon.png" alt="MARKA Logo" className="h-14 w-auto object-contain drop-shadow-sm" />
          <div className="flex flex-col justify-center">
            <span className="text-[10px] font-bold text-gray-400 tracking-widest uppercase mt-0.5">Production</span>
          </div>
        </div>
        
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => setCurrentView("dashboard")} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "dashboard" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>Dashboard</button>
          <button onClick={() => { setNewExamCode(""); setQuestionsCount(20); setCurrentView("builder"); }} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "builder" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>New Exam Sheet</button>
          <button onClick={() => setCurrentView("upload")} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "upload" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>Scan & Grade</button>
          <button onClick={() => setCurrentView("gallery")} className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${currentView === "gallery" ? "bg-[#3B0042] text-white shadow" : "text-gray-500 hover:bg-gray-100"}`}>OMR Library</button>
          <div className="w-px h-6 bg-gray-200 mx-2"></div>
          <div className="flex items-center gap-2 bg-purple-50 px-3 py-1.5 rounded-lg border border-purple-100">
            <span className="text-xs font-bold text-purple-900 uppercase">Credits</span>
            <span className="text-sm font-black text-[#3B0042]">{credits.toLocaleString()}</span>
          </div>
          <button onClick={onLogout} className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Logout">
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">
        <AnimatePresence mode="wait">
          {currentView === "dashboard" && <DashboardHome credits={credits} scans={scans} exams={exams} setExamCode={setExamCode} setCurrentView={setCurrentView} handleExport={handleExport} setQuestionsCount={setQuestionsCount} />}
          {currentView === "builder" && <ExamBuilder newExamCode={newExamCode} setNewExamCode={setNewExamCode} questionsCount={questionsCount} setQuestionsCount={setQuestionsCount} optionsCount={optionsCount} setOptionsCount={setOptionsCount} answerKey={answerKey} setAnswerKey={setAnswerKey} activeBuilderQ={activeBuilderQ} setActiveBuilderQ={setActiveBuilderQ} examSaving={examSaving} examMsg={examMsg} handleCreateExam={handleCreateExam} setCurrentView={setCurrentView} />}
          {currentView === "upload" && <UploadQueue examCode={examCode} setExamCode={setExamCode} exams={exams} uploadQueue={uploadQueue} setUploadQueue={setUploadQueue} fileInputRef={fileInputRef} handleFilesAdded={handleFilesAdded} runBatchProcessing={runBatchProcessing} isUploadingBatch={isUploadingBatch} />}
          {currentView === "gallery" && <Gallery scans={scans} fetchScans={fetchScans} wipeImage={wipeImage} expiryInfo={expiryInfo} searchQuery={searchQuery} setSearchQuery={setSearchQuery} />}
          {currentView === "print" && <PrintableOMRSheet questionsCount={questionsCount} optionsCount={optionsCount} />}
        </AnimatePresence>
      </main>
    </div>
  );
}
