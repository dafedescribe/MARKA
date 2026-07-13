import React from 'react';
import { motion } from 'motion/react';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Play, AlertTriangle } from 'lucide-react';

export default function UploadQueue({
  examCode, setExamCode, exams, uploadQueue, setUploadQueue,
  fileInputRef, handleFilesAdded, runBatchProcessing, isUploadingBatch
}) {
  return (
    <motion.div
      key="upload-view"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="space-y-8"
    >
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

      {uploadQueue.length === 0 ? (
        <div className="bg-white border-2 border-dashed border-gray-200 hover:border-[#3B0042] rounded-3xl p-12 text-center space-y-6 transition-all shadow-sm cursor-pointer relative" onClick={() => fileInputRef.current?.click()}>
          <input type="file" ref={fileInputRef} multiple accept="image/*" onChange={handleFilesAdded} className="hidden" />
          <div className="w-16 h-16 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto"><Upload className="w-8 h-8" /></div>
          <div className="space-y-2">
            <h3 className="text-lg font-black text-gray-900">Drop sheets here or click to select</h3>
            <p className="text-xs text-gray-400 max-w-sm mx-auto">We support high-speed batching. Upload multiple sheets at once.</p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-gray-900">{uploadQueue.length} sheets in queue</h3>
            <div className="flex gap-2">
              <button onClick={() => setUploadQueue([])} className="px-4 py-2 border border-gray-200 rounded-xl text-xs font-bold text-gray-600">Clear</button>
              <button onClick={runBatchProcessing} disabled={isUploadingBatch} className="px-4 py-2 bg-[#3B0042] text-white rounded-xl text-xs font-bold disabled:bg-gray-400 flex items-center gap-2">
                {isUploadingBatch ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                {isUploadingBatch ? 'Processing...' : 'Start Grading'}
              </button>
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
        </div>
      )}
    </motion.div>
  );
}
