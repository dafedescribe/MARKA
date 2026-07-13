import React from 'react';
import { motion } from 'motion/react';
import { Search, RefreshCcw, FileText, Loader2, Clock, Trash2 } from 'lucide-react';

export default function Gallery({ scans, fetchScans, wipeImage, expiryInfo, searchQuery, setSearchQuery }) {
  const filteredScans = scans.filter((p) => {
    return (p.scan_id || '').toLowerCase().includes(searchQuery.toLowerCase());
  });

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
                  {scan.status === 'processing' || scan.status === 'uploading' || scan.status === 'grading' ? <Loader2 className="w-6 h-6 text-[#3B0042] animate-spin" /> : scan.thumbnailUrl ? <img src={scan.thumbnailUrl} alt="Graded OMR" className="w-full h-full object-cover" /> : <FileText className="w-6 h-6 text-gray-300" />}
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
                        <button onClick={() => wipeImage(scan.scan_id)} className="text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"><Trash2 className="w-4 h-4" /></button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </motion.div>
  );
}
