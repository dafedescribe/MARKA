import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, RefreshCcw, FileText, Loader2, Clock, Trash2, Download, X, Maximize2 } from 'lucide-react';

export default function Gallery({ scans, fetchScans, loadMoreScans, hasMoreScans, wipeImage, expiryInfo, searchQuery, setSearchQuery }) {
  const [lightbox, setLightbox] = useState(null);
  const [overrideQ, setOverrideQ] = useState('');
  const [overrideOpt, setOverrideOpt] = useState('');
  const [isOverriding, setIsOverriding] = useState(false);

  const handleOverride = async (e) => {
    e.preventDefault();
    if (!overrideQ || !overrideOpt) return;
    setIsOverriding(true);
    try {
      const token = localStorage.getItem('marka_token');
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${API_URL}/scans/${lightbox.scan_id}/override`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ q_num: overrideQ, new_option: overrideOpt.toUpperCase() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Override failed");
      
      // Update local state for immediate feedback
      setLightbox(prev => ({
        ...prev,
        score: data.score,
        percentage: data.percentage,
        raw_marks: data.raw_marks
      }));
      setOverrideQ('');
      setOverrideOpt('');
      fetchScans(); // Refresh background gallery list silently
    } catch (err) {
      alert(err.message);
    } finally {
      setIsOverriding(false);
    }
  };

  const filteredScans = scans.filter((p) => {
    return (p.scan_id || '').toLowerCase().includes(searchQuery.toLowerCase());
  });

  const downloadImage = async (scan) => {
    if (!scan?.thumbnailUrl) return;
    try {
      const res = await fetch(scan.thumbnailUrl);
      if (!res.ok) throw new Error('fetch failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `MARKA_${scan.scan_id || scan.id}_graded.webp`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed', err);
      alert('Could not download the graded image. It may have been purged.');
    }
  };

  return (
    <motion.div
      key="gallery-view"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="space-y-6"
    >
      <div className="flex justify-between items-center bg-white p-4 rounded-2xl border border-gray-100 shadow-sm">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <div className="relative w-full">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input type="text" placeholder="Search Scan ID..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:border-[#3B0042] focus:outline-none" />
          </div>
        </div>
        <button onClick={fetchScans} className="p-2 text-gray-400 hover:text-[#3B0042] bg-white border border-gray-200 rounded-lg shadow-sm transition-colors ml-4" title="Refresh">
          <RefreshCcw className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredScans.length === 0 ? (
          <div className="col-span-full text-center py-12">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm font-medium">No scans found.</p>
          </div>
        ) : (
          filteredScans.map((scan) => {
            const exp = scan.status === 'success' ? expiryInfo(scan.created_at) : null;
            const hasImage = !!scan.graded_image_path;

            return (
              <div key={scan.id || scan.scan_id} className="bg-white border border-gray-100 rounded-xl p-4 flex gap-4 items-center shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group">
                <div className="w-20 h-20 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
                  {scan.status === 'processing' || scan.status === 'uploading' || scan.status === 'grading' ? (
                    <Loader2 className="w-6 h-6 text-[#3B0042] animate-spin" />
                  ) : scan.thumbnailUrl ? (
                    <button type="button" onClick={() => setLightbox(scan)} className="w-full h-full group/thumb relative cursor-zoom-in" title="View full graded sheet">
                      <img src={scan.thumbnailUrl} alt="Graded OMR" className="w-full h-full object-cover" />
                      <span className="absolute inset-0 bg-black/0 group-hover/thumb:bg-black/30 flex items-center justify-center transition-colors">
                        <Maximize2 className="w-5 h-5 text-white opacity-0 group-hover/thumb:opacity-100 transition-opacity" />
                      </span>
                    </button>
                  ) : (
                    <FileText className="w-6 h-6 text-gray-300" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono font-bold text-gray-900 truncate">{scan.scan_id || 'Generating ID...'}</span>
                    {scan.status === 'success' && <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 text-[9px] font-black uppercase tracking-wider">Graded</span>}
                    {scan.status === 'failed' && <span className="px-1.5 py-0.5 rounded bg-red-50 text-red-600 text-[9px] font-black uppercase tracking-wider">Failed</span>}
                  </div>
                  {scan.status === 'success' ? (
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-black text-[#3B0042] leading-none">{scan.score}<span className="text-sm text-gray-400">/{scan.total}</span></span>
                      <span className="text-sm font-bold text-gray-500">{scan.percentage}%</span>
                    </div>
                  ) : scan.status === 'failed' ? (
                    <p className="text-xs font-semibold text-red-500 truncate">{scan.error_message}</p>
                  ) : (
                    <div className="flex items-center gap-1.5 mt-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></div>
                      <span className="text-xs font-semibold text-purple-600">Running ML Engine...</span>
                    </div>
                  )}
                  {exp && (
                    <div className="mt-2 flex items-center justify-between">
                      <div className="flex items-center gap-1">
                        <Clock className={`w-3 h-3 ${exp.urgent ? 'text-red-500' : 'text-gray-400'}`} />
                        <span className={`text-[10px] ${exp.urgent ? 'text-red-600 font-bold' : 'text-gray-400 font-medium'}`}>{hasImage ? exp.text : 'Image purged'}</span>
                      </div>
                      {hasImage && (
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button onClick={() => downloadImage(scan)} className="text-gray-300 hover:text-[#3B0042] transition-colors" title="Download graded sheet"><Download className="w-4 h-4" /></button>
                          <button onClick={() => wipeImage(scan.scan_id)} className="text-gray-300 hover:text-red-500 transition-colors" title="Delete image immediately"><Trash2 className="w-4 h-4" /></button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {hasMoreScans && filteredScans.length > 0 && searchQuery === "" && (
        <div className="flex justify-center pt-6">
          <button
            onClick={loadMoreScans}
            className="px-6 py-2.5 bg-white border border-gray-200 hover:bg-gray-50 hover:border-gray-300 text-gray-600 font-bold text-sm rounded-xl transition-all shadow-sm flex items-center gap-2"
          >
            Load More Scans
          </button>
        </div>
      )}

      {/* Full-size graded sheet lightbox */}
      <AnimatePresence>
        {lightbox && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setLightbox(null)}
            className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden"
            >
              <div className="p-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-mono font-bold text-gray-900 truncate">{lightbox.scan_id}</p>
                  <p className="text-xs text-gray-500">
                    Score <span className="font-bold text-[#3B0042]">{lightbox.score}/{lightbox.total}</span> · {lightbox.percentage}%
                    {lightbox.raw_marks?.ambiguous?.length > 0 && (
                      <span className="ml-2 text-amber-600 font-bold bg-amber-50 px-2 py-0.5 rounded-full">
                        Ambiguous: {lightbox.raw_marks.ambiguous.join(", ")}
                      </span>
                    )}
                  </p>
                </div>
                
                <form onSubmit={handleOverride} className="flex items-center gap-2 flex-shrink-0 bg-gray-50 p-1.5 rounded-xl border border-gray-200">
                  <input type="number" placeholder="Q#" value={overrideQ} onChange={e=>setOverrideQ(e.target.value)} required min={1} className="w-12 px-2 py-1 text-xs border border-gray-200 rounded text-center focus:outline-none focus:border-purple-500" />
                  <input type="text" placeholder="A-E" value={overrideOpt} onChange={e=>setOverrideOpt(e.target.value.toUpperCase())} required maxLength={1} className="w-12 px-2 py-1 text-xs border border-gray-200 rounded text-center focus:outline-none focus:border-purple-500 uppercase" />
                  <button type="submit" disabled={isOverriding} className="px-3 py-1 bg-white border border-gray-200 text-xs font-bold text-[#3B0042] rounded hover:bg-gray-50 transition-colors disabled:opacity-50">
                    {isOverriding ? '...' : 'Override'}
                  </button>
                </form>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={() => downloadImage(lightbox)} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#3B0042] text-white text-xs font-bold rounded-lg hover:bg-[#4d0055] transition-colors">
                    <Download className="w-3.5 h-3.5" /> Download
                  </button>
                  <button onClick={() => setLightbox(null)} className="p-1.5 text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors" title="Close">
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-auto bg-gray-50 flex items-center justify-center p-4">
                {lightbox.thumbnailUrl ? (
                  <img src={lightbox.thumbnailUrl} alt="Graded OMR sheet" className="max-w-full max-h-[70vh] object-contain rounded-lg shadow" />
                ) : (
                  <p className="text-sm text-gray-500 py-12">Image no longer available.</p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
