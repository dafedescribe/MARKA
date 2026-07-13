import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Download, LogOut, RefreshCcw, Trash2, Clock } from 'lucide-react';
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

  // Days/hours until a scan's images auto-wipe (7 days after created_at).
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
      // Demotest has 999999 credits, so it's fine. Normal users shouldn't exceed limits.
      alert(`You only have ${credits} credits but tried to upload ${files.length} images! Please top up.`);
      return;
    }

    setUploading(true);
    
    // We can upload in parallel using Promise.all
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
                  <span className="upload-title">Tap or Drop to Scan OMR Sheets</span>
                  <span className="upload-subtitle">Upload multiple at once</span>
                </div>
              )}
              <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden-input" 
                accept="image/jpeg, image/png"
                multiple
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

            {scans.map((scan) => {
              const exp = scan.status === 'success' ? expiryInfo(scan.created_at) : null;
              const hasImage = !!scan.graded_image_path;
              return (
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

                  {exp && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem', marginTop: '4px', color: exp.urgent ? '#c0261a' : '#8a8a8a', fontWeight: exp.urgent ? 700 : 500 }}>
                      <Clock size={12} /> {hasImage ? exp.text : 'Images deleted · score kept'}
                    </span>
                  )}
                </div>

                <div className="scan-status-icon" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                  {scan.status === 'success' && <CheckCircle className="text-success" size={24} />}
                  {scan.status === 'failed' && <XCircle className="text-danger" size={24} />}
                  {scan.status === 'processing' && <Loader2 className="spinner" size={24} />}
                  {scan.status === 'success' && hasImage && (
                    <button
                      type="button"
                      title="Delete image to reclaim space (keeps the score)"
                      onClick={() => wipeImage(scan.scan_id)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#b0392b', padding: 0 }}
                    >
                      <Trash2 size={18} />
                    </button>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}
