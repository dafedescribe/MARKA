import React from 'react';
import { motion } from 'motion/react';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Play, AlertTriangle, RefreshCw, Plus, Images, Sun, Maximize, PenLine, ScanLine } from 'lucide-react';

const CAPTURE_TIPS = [
  { icon: Sun, title: 'Even, bright light', desc: 'No shadows across the sheet' },
  { icon: Maximize, title: 'Flat & fully in frame', desc: 'All 4 corner squares visible' },
  { icon: PenLine, title: 'Fill bubbles darkly', desc: 'Dark pencil or pen, fully shaded' },
  { icon: ScanLine, title: 'Straight & in focus', desc: 'Shoot from directly above' },
];

export default function UploadQueue({
  examCode, setExamCode, exams, uploadQueue, setUploadQueue,
  fileInputRef, handleFilesAdded, runBatchProcessing, isUploadingBatch, retryFailed, goToLibrary
}) {
  const hasFailedItems = uploadQueue.some(item => item.status === 'failed');
  const queuedCount = uploadQueue.filter(item => item.status === 'queued').length;
  const completeCount = uploadQueue.filter(item => item.status === 'complete').length;
  const allSettled = uploadQueue.length > 0 && !isUploadingBatch &&
    uploadQueue.every(item => item.status === 'complete' || item.status === 'failed');

  return (
    <motion.div
      key="upload-view"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="space-y-8"
    >
      {/* Single always-present file input, shared by the dropzone and "Add More" */}
      <input type="file" ref={fileInputRef} multiple accept="image/*" onChange={handleFilesAdded} className="hidden" />

      <div className="flex flex-col md:flex-row justify-between items-start gap-4 border-b border-gray-200 pb-4">
        <div>
          <h2 className="text-xl font-black text-purple-950">Grade Scanning Session</h2>
          <p className="text-xs text-gray-400">Active Exam: <strong className="text-[#3B0042]">{examCode}</strong>. Select an exam to change.</p>
        </div>
        <select value={examCode} onChange={(e) => setExamCode(e.target.value)} className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-semibold text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#3B0042]/20 focus:border-[#3B0042]">
          <option value="MARKA">Demo — MARKA</option>
          {exams.filter((ex) => ex.exam_code !== 'MARKA').map((ex) => (
            <option key={ex.exam_code} value={ex.exam_code}>{ex.exam_code}</option>
          ))}
        </select>
      </div>

      {/* Capture guidance — the biggest driver of grading accuracy is photo quality */}
      <div className="bg-purple-50/60 border border-purple-100 rounded-2xl p-4">
        <p className="text-[11px] font-black uppercase tracking-wider text-[#3B0042] mb-3">For accurate grading, photograph each sheet like this</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {CAPTURE_TIPS.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex items-start gap-2.5">
              <div className="w-8 h-8 flex-shrink-0 bg-white text-[#3B0042] rounded-lg flex items-center justify-center shadow-sm"><Icon className="w-4 h-4" /></div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-gray-900 leading-tight">{title}</p>
                <p className="text-[11px] text-gray-500 leading-tight mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {uploadQueue.length === 0 ? (
        <div className="bg-white border-2 border-dashed border-gray-200 hover:border-[#3B0042] rounded-3xl p-12 text-center space-y-6 transition-all shadow-sm cursor-pointer relative" onClick={() => fileInputRef.current?.click()}>
          <div className="w-16 h-16 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto"><Upload className="w-8 h-8" /></div>
          <div className="space-y-2">
            <h3 className="text-lg font-black text-gray-900">Drop sheets here or click to select</h3>
            <p className="text-xs text-gray-400 max-w-sm mx-auto">We support high-speed batching. Upload multiple sheets at once.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap justify-between items-center gap-2">
            <h3 className="text-sm font-bold text-gray-900">{uploadQueue.length} sheets in queue{completeCount > 0 && ` · ${completeCount} graded`}</h3>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => setUploadQueue([])} className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50 transition-colors">Clear</button>

              <button onClick={() => fileInputRef.current?.click()} disabled={isUploadingBatch} className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-700 hover:bg-gray-50 disabled:opacity-50 flex items-center gap-2 transition-colors">
                <Plus className="w-4 h-4" /> Add More
              </button>

              {hasFailedItems && !isUploadingBatch && (
                <button onClick={retryFailed} className="px-4 py-2 bg-amber-500 text-white rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-amber-600 transition-colors">
                  <RefreshCw className="w-4 h-4" /> Retry Failed
                </button>
              )}

              {(queuedCount > 0 || isUploadingBatch) && (
                <button onClick={runBatchProcessing} disabled={isUploadingBatch} className="px-4 py-2 bg-[#3B0042] text-white rounded-xl text-xs font-bold disabled:bg-gray-400 flex items-center gap-2 hover:bg-[#2c0032] transition-colors">
                  {isUploadingBatch ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  {isUploadingBatch ? 'Processing...' : (completeCount > 0 ? `Grade ${queuedCount} New` : 'Start Grading')}
                </button>
              )}

              {allSettled && completeCount > 0 && (
                <button onClick={goToLibrary} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-emerald-700 transition-colors">
                  <Images className="w-4 h-4" /> View in OMR Library
                </button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {uploadQueue.map((item) => (
              <div key={item.id} className="bg-white border border-gray-100 rounded-xl p-4 flex items-center gap-4 shadow-sm">
                <div className="w-12 h-12 rounded-lg bg-gray-50 flex items-center justify-center">
                  {item.status === 'queued' && <FileText className="w-6 h-6 text-gray-400" />}
                  {item.status === 'uploading' && <Upload className="w-5 h-5 text-purple-400 animate-bounce" />}
                  {item.status === 'grading' && <Loader2 className="w-5 h-5 text-[#3B0042] animate-spin" />}
                  {item.status === 'complete' && <CheckCircle className="w-6 h-6 text-emerald-500" />}
                  {item.status === 'failed' && <XCircle className="w-6 h-6 text-red-500" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-gray-900 truncate">{item.filename}</p>
                  <p className="text-[10px] text-gray-500 font-medium uppercase tracking-wider mt-1">{item.status}</p>
                  {item.isBlurry && <p className="text-[10px] text-amber-500 mt-0.5 truncate flex items-center gap-1 font-semibold"><AlertTriangle className="w-3 h-3" /> Blur Detected</p>}
                  {item.error && <p className="text-[10px] text-red-500 mt-0.5 truncate">{item.error}</p>}
                </div>
              </div>
            ))}
          </div>

          {allSettled && completeCount > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
              <p className="text-sm font-bold text-emerald-800">Grading complete — {completeCount} sheet{completeCount > 1 ? 's' : ''} graded. Results are in your OMR Library.</p>
              <button onClick={goToLibrary} className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-emerald-700 transition-colors flex-shrink-0">
                <Images className="w-4 h-4" /> Go to Library
              </button>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
