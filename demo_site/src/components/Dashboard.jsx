import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Download, LogOut, RefreshCcw, Trash2, Clock, Plus, X, Settings2, Image as ImageIcon } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { motion, AnimatePresence } from 'motion/react';

export default function Dashboard({ token, onLogout }) {
  const [credits, setCredits] = useState(parseInt(localStorage.getItem('marka_credits') || '0'));
  const [scans, setScans] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [examCode, setExamCode] = useState('MARKA');
  const [exams, setExams] = useState([]);
  const [showExamForm, setShowExamForm] = useState(false);
  const [newExamCode, setNewExamCode] = useState('');
  const [newExamKey, setNewExamKey] = useState('');
  const [examSaving, setExamSaving] = useState(false);
  const [examMsg, setExamMsg] = useState('');
  const fileInputRef = useRef(null);
  
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
        .limit(20);
        
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

  const parseAnswerKey = (text) => {
    const tokens = (text || '').trim().split(/[\s,]+/).filter(Boolean);
    const answers = {};
    tokens.forEach((tok, i) => {
      const q = String(i + 1);
      const t = tok.toUpperCase();
      if (t === '*' || t === 'ANY' || t === 'BONUS') { answers[q] = '*'; return; }
      const letters = [...new Set(t.replace(/[^A-E]/g, '').split(''))];
      if (letters.length === 0) return;
      answers[q] = letters.length === 1 ? letters[0] : letters;
    });
    return answers;
  };

  const handleCreateExam = async () => {
    const code = newExamCode.trim().toUpperCase();
    if (!code) { setExamMsg('Enter an exam name/code.'); return; }
    const answers = parseAnswerKey(newExamKey);
    if (Object.keys(answers).length === 0) { setExamMsg('Enter the answer key.'); return; }
    setExamSaving(true);
    setExamMsg('');
    try {
      const res = await fetch(`${API_URL}/exams`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ exam_code: code, answers }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to save exam');
      setNewExamCode('');
      setNewExamKey('');
      setShowExamForm(false);
      await fetchExams();
      setExamCode(code);
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

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    if (credits < files.length && credits !== -1 && token) {
      alert(`You only have ${credits} credits but tried to upload ${files.length} images! Please top up.`);
      return;
    }

    setUploading(true);
    
    const uploadPromises = files.map(async (file, index) => {
      const tempId = `temp_${Date.now()}_${index}`;
      const optimisticScan = {
        id: tempId,
        status: 'processing',
        created_at: new Date().toISOString()
      };
      setScans(prev => [optimisticScan, ...prev]);

      try {
        const scanId = `${Date.now()}_${index}`;
        const res = await fetch(`${API_URL}/upload/presigned-url?scan_id=${scanId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const { upload_url, path } = await res.json();

        const uploadRes = await fetch(upload_url, {
          method: 'PUT',
          headers: {
            'Content-Type': file.type,
          },
          body: file
        });

        if (!uploadRes.ok) throw new Error('Failed to upload image directly to Supabase');

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
        
      } catch (error) {
        console.error(error);
        setScans(prev => prev.filter(s => s.id !== tempId));
      }
    });

    await Promise.all(uploadPromises);
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleExport = async () => {
    try {
      const res = await fetch(`${API_URL}/export/${examCode}`, {
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
      {/* Navigation Header */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-30 shadow-sm transition-all duration-200">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#3B0042] flex items-center justify-center text-white font-extrabold text-sm tracking-tighter shadow-sm">
              M
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-black text-[#3B0042] tracking-wider leading-none">MARKA</span>
              <span className="text-[8px] font-bold text-gray-400 tracking-widest uppercase mt-0.5">Production</span>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-purple-50 px-3 py-1.5 rounded-lg border border-purple-100">
              <span className="text-xs font-bold text-purple-900 uppercase">Credits</span>
              <span className="text-sm font-black text-[#3B0042]">{credits.toLocaleString()}</span>
            </div>
            <button 
              onClick={onLogout}
              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Logout"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        <div className="flex flex-col lg:flex-row gap-8 items-start">
          
          {/* Left Sidebar / Actions */}
          <div className="w-full lg:w-[340px] flex-shrink-0 space-y-6">
            
            {/* Exam Configuration Card */}
            <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                  <Settings2 className="w-4 h-4 text-[#3B0042]" />
                  Active Exam Set
                </h2>
              </div>
              
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <select
                    value={examCode}
                    onChange={(e) => setExamCode(e.target.value)}
                    className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm font-semibold text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#3B0042]/20 focus:border-[#3B0042] transition-all"
                  >
                    <option value="MARKA">Demo — MARKA Standard Sheet (100Q)</option>
                    {exams.filter((ex) => ex.exam_code !== 'MARKA').map((ex) => (
                      <option key={ex.exam_code} value={ex.exam_code}>
                        {ex.exam_code} ({ex.num_questions}Q)
                      </option>
                    ))}
                  </select>
                </div>

                <AnimatePresence>
                  {!showExamForm ? (
                    <motion.button
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      onClick={() => { setShowExamForm(true); setExamMsg(''); }}
                      className="w-full py-2 flex items-center justify-center gap-1.5 text-xs font-bold text-[#3B0042] bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Create New Answer Key
                    </motion.button>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="bg-gray-50 p-4 rounded-xl border border-gray-200 space-y-3 overflow-hidden"
                    >
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-bold text-gray-600 uppercase">New Key Setup</span>
                        <button onClick={() => setShowExamForm(false)} className="text-gray-400 hover:text-gray-700">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      
                      <input
                        type="text"
                        value={newExamCode}
                        onChange={(e) => setNewExamCode(e.target.value)}
                        placeholder="Exam Code (e.g. BIO-T1)"
                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm focus:border-[#3B0042] focus:outline-none uppercase"
                      />
                      
                      <textarea
                        value={newExamKey}
                        onChange={(e) => setNewExamKey(e.target.value)}
                        placeholder="A B C D E A C ... (one answer per question, space separated)"
                        rows={4}
                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm font-mono focus:border-[#3B0042] focus:outline-none resize-none"
                      />
                      
                      <p className="text-[10px] text-gray-500 leading-relaxed">
                        Use <b>*</b> for a bonus (any correct). Run letters together for multiple correct options (e.g. <b>AC</b>).
                      </p>
                      
                      {examMsg && <p className="text-xs text-red-600 font-semibold">{examMsg}</p>}
                      
                      <button
                        onClick={handleCreateExam}
                        disabled={examSaving}
                        className="w-full py-2 bg-[#3B0042] text-white font-bold text-xs rounded-lg hover:bg-[#2c0032] disabled:bg-gray-400 transition-colors"
                      >
                        {examSaving ? 'Saving...' : 'Save Exam Key'}
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Upload Zone */}
              <div className="mt-6">
                <div
                  onClick={() => !uploading && fileInputRef.current?.click()}
                  className={`w-full border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${
                    uploading 
                      ? 'border-purple-300 bg-purple-50' 
                      : 'border-gray-200 hover:border-[#3B0042] hover:bg-purple-50/50 bg-gray-50'
                  }`}
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-8 h-8 text-[#3B0042] animate-spin mb-3" />
                      <span className="text-sm font-bold text-[#3B0042]">Uploading securely...</span>
                    </>
                  ) : (
                    <>
                      <div className="w-12 h-12 bg-white rounded-full shadow-sm flex items-center justify-center mb-3 text-[#3B0042]">
                        <Upload className="w-6 h-6" />
                      </div>
                      <span className="text-sm font-bold text-gray-900 block mb-1">Scan OMR Sheets</span>
                      <span className="text-xs text-gray-500 font-medium">Tap to select or take photos</span>
                    </>
                  )}
                </div>
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  className="hidden" 
                  accept="image/jpeg, image/png, image/*"
                  capture="environment"
                  multiple
                  onChange={handleFileUpload} 
                />
              </div>
            </div>

            {/* Export Card */}
            <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-4">
              <h2 className="text-base font-bold text-gray-900">Export Results</h2>
              <p className="text-xs text-gray-500 leading-relaxed">
                Download a ZIP containing the CSV gradebook and visual diagnostic proof images for the active exam set.
              </p>
              <div className="bg-amber-50 p-2.5 rounded-lg border border-amber-100 text-[10px] text-amber-800 font-bold uppercase tracking-wide flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" /> Images auto-wipe after 7 days
              </div>
              <button 
                onClick={handleExport}
                className="w-full py-2.5 bg-gray-900 hover:bg-black text-white text-sm font-bold rounded-xl flex items-center justify-center gap-2 transition-colors shadow-sm"
              >
                <Download className="w-4 h-4" />
                Download Gradebook ZIP
              </button>
            </div>
          </div>

          {/* Right Feed / Results */}
          <div className="flex-1 bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden flex flex-col h-[calc(100vh-8rem)]">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-[#3B0042]" />
                Grading Stream
              </h2>
              <button 
                onClick={fetchScans}
                className="p-1.5 text-gray-400 hover:text-[#3B0042] bg-white border border-gray-200 rounded-lg shadow-sm transition-colors"
                title="Refresh stream"
              >
                <RefreshCcw className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50/30">
              {scans.length === 0 && !uploading && (
                <div className="h-full flex flex-col items-center justify-center text-center p-8">
                  <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center text-gray-300 mb-4 border border-gray-100">
                    <FileText className="w-8 h-8" />
                  </div>
                  <p className="text-lg font-bold text-gray-900 mb-1">No papers scanned yet</p>
                  <p className="text-sm text-gray-500 max-w-sm">
                    Upload an OMR sheet using the panel on the left to see the ML extraction magic happen instantly.
                  </p>
                </div>
              )}

              <AnimatePresence>
                {scans.map((scan) => {
                  const exp = scan.status === 'success' ? expiryInfo(scan.created_at) : null;
                  const hasImage = !!scan.graded_image_path;
                  
                  return (
                    <motion.div 
                      key={scan.id}
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-white border border-gray-100 rounded-xl p-3 flex gap-4 items-center shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group"
                    >
                      {/* Left Thumbnail */}
                      <div className="w-16 h-16 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
                        {scan.status === 'processing' ? (
                          <Loader2 className="w-6 h-6 text-[#3B0042] animate-spin" />
                        ) : scan.thumbnailUrl ? (
                          <img src={scan.thumbnailUrl} alt="Graded OMR" className="w-full h-full object-cover" />
                        ) : (
                          <FileText className="w-6 h-6 text-gray-300" />
                        )}
                      </div>

                      {/* Middle Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono font-bold text-gray-900 truncate">
                            {scan.scan_id || 'Generating ID...'}
                          </span>
                          {scan.status === 'success' && (
                            <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 text-[9px] font-black uppercase tracking-wider">
                              Graded
                            </span>
                          )}
                          {scan.status === 'failed' && (
                            <span className="px-1.5 py-0.5 rounded bg-red-50 text-red-600 text-[9px] font-black uppercase tracking-wider">
                              Failed
                            </span>
                          )}
                        </div>

                        {scan.status === 'success' ? (
                          <div className="flex items-baseline gap-2">
                            <span className="text-xl font-black text-[#3B0042] leading-none">
                              {scan.score}<span className="text-sm text-gray-400">/{scan.total}</span>
                            </span>
                            <span className="text-sm font-bold text-gray-500">
                              {scan.percentage}%
                            </span>
                          </div>
                        ) : scan.status === 'failed' ? (
                          <p className="text-xs font-semibold text-red-500 truncate max-w-xs">
                            {scan.error_message || 'Image unrecognizable'}
                          </p>
                        ) : (
                          <div className="flex items-center gap-1.5 mt-1">
                            <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></div>
                            <span className="text-xs font-semibold text-purple-600">Running ML Engine...</span>
                          </div>
                        )}

                        {exp && (
                          <div className="mt-1.5 flex items-center gap-1">
                            <Clock className={`w-3 h-3 ${exp.urgent ? 'text-red-500' : 'text-gray-400'}`} />
                            <span className={`text-[10px] ${exp.urgent ? 'text-red-600 font-bold' : 'text-gray-400 font-medium'}`}>
                              {hasImage ? exp.text : 'Image purged • Score kept'}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Right Actions */}
                      <div className="flex flex-col items-center gap-2 pr-2">
                        {scan.status === 'success' && <CheckCircle className="w-6 h-6 text-emerald-500" />}
                        {scan.status === 'failed' && <XCircle className="w-6 h-6 text-red-500" />}
                        
                        {scan.status === 'success' && hasImage && (
                          <button
                            onClick={() => wipeImage(scan.scan_id)}
                            className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors opacity-0 group-hover:opacity-100"
                            title="Delete image immediately"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </div>
          
        </div>
      </main>
    </div>
  );
}
