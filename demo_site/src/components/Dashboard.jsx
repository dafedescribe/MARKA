import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Download, LogOut, RefreshCcw } from 'lucide-react';
import { supabase } from '../lib/supabase';
import './Dashboard.css';

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
      const res = await fetch(`${API_URL}/exams?token=${token}`);
      if (!res.ok) return;
      const data = await res.json();
      setExams(data.exams || []);
    } catch (e) {
      console.error("Error fetching exams:", e);
    }
  };

  // Parse a letter-string answer key into { "1": "A", "3": "*", "4": ["A","C"] }.
  // Questions are separated by spaces/commas/newlines; position = question number.
  //   A     -> single answer
  //   AC    -> multiple accepted (any of them); run letters together
  //   *     -> bonus (any answer is correct)
  const parseAnswerKey = (text) => {
    const tokens = (text || '').trim().split(/[\s,]+/).filter(Boolean);
    const answers = {};
    tokens.forEach((tok, i) => {
      const q = String(i + 1);
      const t = tok.toUpperCase();
      if (t === '*' || t === 'ANY' || t === 'BONUS') { answers[q] = '*'; return; }
      const letters = [...new Set(t.replace(/[^A-E]/g, '').split(''))];
      if (letters.length === 0) return;               // skip junk token
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exam_code: code, answers, token }),
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

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (credits <= 0) {
      alert("You are out of credits! Please top up.");
      return;
    }

    setUploading(true);
    const tempId = `temp_${Date.now()}`;
    const optimisticScan = {
      id: tempId,
      status: 'processing',
      created_at: new Date().toISOString()
    };
    setScans(prev => [optimisticScan, ...prev]);

    try {
      const scanId = Date.now().toString();
      const res = await fetch(`${API_URL}/upload/presigned-url?scan_id=${scanId}&token=${token}`);
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scan_id: scanId,
          exam_code: examCode,
          token: token
        })
      });

      if (!triggerRes.ok) throw new Error('Failed to trigger processing');
      
    } catch (error) {
      console.error(error);
      alert(error.message);
      setScans(prev => prev.filter(s => s.id !== tempId));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleExport = async () => {
    try {
      const res = await fetch(`${API_URL}/export/${examCode}?token=${token}`);
      if (!res.ok) throw new Error("Failed to export");
      const { export_url } = await res.json();
      window.location.href = export_url;
    } catch (e) {
      alert(e.message);
    }
  };

  return (
    <div className="dashboard-container">
      <header className="navbar">
        <div className="nav-content">
          <div className="brand">
            <h1>MARKA</h1>
            <span className="badge">Production</span>
          </div>
          
          <div className="user-controls">
            <div className="credits-display">
              <span className="credits-label">Credits</span>
              <span className="credits-value">{credits.toLocaleString()}</span>
            </div>
            <button className="logout-btn" onClick={onLogout}>
              <LogOut size={20} />
            </button>
          </div>
        </div>
      </header>

      <main className="dashboard-main">
        <aside className="sidebar">
          <div className="card scan-card">
            <h2>Grade Exam</h2>
            
            <div className="form-group">
              <label>Select Exam</label>
              <select
                value={examCode}
                onChange={(e) => setExamCode(e.target.value)}
                className="select-input"
              >
                <option value="MARKA">Demo — MARKA Standard Sheet (100Q)</option>
                {exams.filter((ex) => ex.exam_code !== 'MARKA').map((ex) => (
                  <option key={ex.exam_code} value={ex.exam_code}>
                    {ex.exam_code} ({ex.num_questions}Q)
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => { setShowExamForm((v) => !v); setExamMsg(''); }}
                style={{ background: 'none', border: 'none', color: 'var(--primary, #3B0042)', cursor: 'pointer', padding: '6px 0', fontWeight: 600, fontSize: '0.85rem' }}
              >
                {showExamForm ? '× Cancel' : '+ New exam / answer key'}
              </button>
            </div>

            {showExamForm && (
              <div style={{ background: 'rgba(0,0,0,0.03)', padding: '12px', borderRadius: '8px', marginBottom: '1rem' }}>
                <label>Exam name</label>
                <input
                  type="text"
                  value={newExamCode}
                  onChange={(e) => setNewExamCode(e.target.value)}
                  placeholder="e.g. BIO-SS2-T1"
                  className="select-input"
                />
                <label style={{ marginTop: '0.6rem', display: 'block' }}>Answer key</label>
                <textarea
                  value={newExamKey}
                  onChange={(e) => setNewExamKey(e.target.value)}
                  placeholder="A B C D E A C ...  (one answer per question)"
                  rows={4}
                  className="select-input"
                  style={{ resize: 'vertical', fontFamily: 'monospace' }}
                />
                <p style={{ fontSize: '0.75rem', color: '#666', margin: '6px 0' }}>
                  One answer per question, separated by spaces. Use <b>*</b> for a
                  bonus (any answer correct), and run letters together for multiple
                  accepted answers (e.g. <b>AC</b>).
                </p>
                {examMsg && <p style={{ fontSize: '0.8rem', color: '#b00', margin: '6px 0' }}>{examMsg}</p>}
                <button
                  type="button"
                  className="btn btn-block"
                  disabled={examSaving}
                  onClick={handleCreateExam}
                >
                  {examSaving ? 'Saving…' : 'Save Exam'}
                </button>
              </div>
            )}

            <div 
              className={`upload-zone ${uploading ? 'uploading' : ''}`}
              onClick={() => !uploading && fileInputRef.current?.click()}
            >
              {uploading ? (
                <div className="upload-state">
                  <Loader2 size={32} className="spinner" />
                  <span>Uploading...</span>
                </div>
              ) : (
                <div className="upload-state">
                  <div className="icon-circle">
                    <Upload size={24} />
                  </div>
                  <span className="upload-title">Tap to Scan OMR</span>
                  <span className="upload-subtitle">Takes ~1 second</span>
                </div>
              )}
              <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden-input" 
                accept="image/jpeg, image/png"
                onChange={handleFileUpload} 
              />
            </div>
          </div>

          <div className="card export-card">
            <h2>Export Results</h2>
            <p>Download the CSV gradebook and all visual proof images for your records.</p>
            <p className="warning-text">Files auto-wipe after 7 days.</p>
            <button className="btn btn-block btn-white" onClick={handleExport}>
              <Download size={18} />
              <span>Download ZIP</span>
            </button>
          </div>
        </aside>

        <section className="feed">
          <div className="feed-header">
            <h2>Recent Scans</h2>
            <button onClick={fetchScans} className="refresh-btn">
              <RefreshCcw size={18} />
            </button>
          </div>

          <div className="scans-list">
            {scans.length === 0 && !uploading && (
              <div className="empty-state">
                <FileText size={48} />
                <p className="empty-title">No scans yet.</p>
                <p>Upload an OMR sheet to see the magic happen.</p>
              </div>
            )}

            {scans.map((scan) => (
              <div key={scan.id} className="scan-item">
                <div className="scan-thumbnail">
                  {scan.status === 'processing' ? (
                    <Loader2 size={24} className="spinner" />
                  ) : scan.thumbnailUrl ? (
                    <img src={scan.thumbnailUrl} alt="Graded OMR" />
                  ) : (
                    <FileText size={24} className="icon-muted" />
                  )}
                </div>

                <div className="scan-info">
                  <div className="scan-meta">
                    <span className="scan-id">{scan.scan_id || 'Generating...'}</span>
                    {scan.status === 'success' && <span className="status-badge success">Graded</span>}
                    {scan.status === 'failed' && <span className="status-badge failed">Failed</span>}
                  </div>
                  
                  {scan.status === 'success' ? (
                    <div className="scan-score-box">
                      <span className="scan-score">{scan.score}/{scan.total}</span>
                      <span className="scan-percentage">{scan.percentage}%</span>
                    </div>
                  ) : scan.status === 'failed' ? (
                    <p className="scan-error">{scan.error_message || 'Image unreadable'}</p>
                  ) : (
                    <p className="scan-processing-text">Running ML Extraction...</p>
                  )}
                </div>

                <div className="scan-status-icon">
                  {scan.status === 'success' && <CheckCircle className="text-success" size={24} />}
                  {scan.status === 'failed' && <XCircle className="text-danger" size={24} />}
                  {scan.status === 'processing' && <Loader2 className="spinner" size={24} />}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
