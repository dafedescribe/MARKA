import React from 'react';
import { motion } from 'motion/react';
import { Coins, HardDrive, PlusCircle, History, ClipboardList, Download, Eye, FileText } from 'lucide-react';

export default function DashboardHome({ credits, storedImages, exams, setExamCode, setCurrentView, handleExport, setQuestionsCount, setAnswerKey, setNewExamCode, handleClearLibrary, sheetProfile, setSheetProfile, saveSheetProfile, profileMessage, downloadTemplate, uploadLogo, removeLogo }) {
  return (
    <motion.div
      key="dashboard-view"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="space-y-8"
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex flex-col justify-between space-y-4">
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block">REMAINING CREDITS</span>
            <div className="p-2 bg-purple-50 text-[#3B0042] rounded-xl"><Coins className="w-5 h-5" /></div>
          </div>
          <div>
            <span className="text-3xl font-black text-purple-950 block">{credits} Credits</span>
            <span className="text-[10px] text-gray-400 font-semibold block mt-1">1 Credit used per successfully graded exam paper</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex flex-col justify-between space-y-4">
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block">STORAGE ALLOCATION</span>
            <div className="p-2 bg-purple-50 text-[#3B0042] rounded-xl"><HardDrive className="w-5 h-5" /></div>
          </div>
          <div>
            <span className="text-2xl font-black text-gray-800 block">{storedImages} Images</span>
            <div className="w-full bg-gray-100 rounded-full h-2 mt-2">
              <div className="bg-[#3B0042] h-2 rounded-full" style={{ width: `${Math.min((storedImages / 500) * 100, 100)}%` }}></div>
            </div>
          </div>
          <button onClick={handleClearLibrary} className="w-full text-center py-2.5 rounded-xl border border-gray-200 hover:bg-gray-50 text-gray-600 font-bold text-xs transition-all">Clear image library</button>
        </div>

        <div className="bg-[#3B0042] text-white p-6 rounded-2xl flex flex-col justify-between shadow-lg relative overflow-hidden">
          <div className="absolute -right-12 -bottom-12 w-32 h-32 bg-white/5 rounded-full"></div>
          <div className="space-y-2">
            <h2 className="text-lg font-bold">Start Grading Sheet</h2>
            <p className="text-xs text-purple-200 leading-normal">Establish an Answer Key, upload photo sheets, and see instant grades.</p>
          </div>
          <button onClick={() => setCurrentView("builder")} className="w-full py-3 bg-white text-[#3B0042] hover:bg-amber-400 font-extrabold text-xs rounded-xl transition-all shadow mt-4 flex items-center justify-center gap-2">
            <PlusCircle className="w-4 h-4" /> Start Marking Now
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm space-y-4">
        <div><h3 className="font-extrabold text-gray-900 text-sm">Sheet and receipt details</h3><p className="text-xs text-gray-500 mt-1">Save once; MARKA reuses these details.</p></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {['school_name', 'address', 'phone', 'email'].map((key) => <input key={key} value={sheetProfile[key] || ''} maxLength={key === 'address' ? 240 : 120} onChange={(e) => setSheetProfile({ ...sheetProfile, [key]: e.target.value })} placeholder={{ school_name: 'School or organisation name', address: 'Full address', phone: 'Phone', email: 'Email' }[key]} className="px-3 py-2.5 rounded-xl border border-gray-200 text-sm outline-none focus:border-purple-500" />)}
        </div>
        <div className="flex items-center gap-3">
          <div className="w-16 h-16 rounded-xl border border-dashed border-gray-300 bg-gray-50 flex items-center justify-center overflow-hidden">
            {sheetProfile.logo_b64 ? <img src={sheetProfile.logo_b64} alt="School logo preview" className="max-w-full max-h-full object-contain" /> : <span className="text-[10px] font-bold text-gray-400">LOGO</span>}
          </div>
          <label className="px-4 py-2.5 border border-gray-200 rounded-xl text-xs font-bold cursor-pointer hover:bg-gray-50">
            {sheetProfile.logo_b64 ? 'Replace logo' : 'Upload logo'}
            <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { uploadLogo(e.target.files?.[0]); e.target.value = ''; }} />
          </label>
          {sheetProfile.logo_b64 && <button onClick={removeLogo} className="px-3 py-2.5 text-red-600 text-xs font-bold">Remove</button>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={saveSheetProfile} className="px-4 py-2.5 bg-[#3B0042] text-white rounded-xl text-xs font-bold">Save details</button>
          <button onClick={() => downloadTemplate('printed')} className="px-4 py-2.5 border border-gray-200 rounded-xl text-xs font-bold">Download printed sheet</button>
          <button onClick={() => downloadTemplate('handdrawn')} className="px-4 py-2.5 border border-gray-200 rounded-xl text-xs font-bold">Download drawing guide</button>
          <span className="text-xs text-gray-500">{profileMessage}</span>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-6 space-y-6 shadow-sm">
        <h3 className="font-extrabold text-gray-900 text-sm flex items-center gap-2">
          <History className="w-4 h-4 text-purple-600" />
          Recent Exam Keys
        </h3>

        {exams.length === 0 ? (
          <div className="text-center py-16 space-y-4">
            <div className="w-16 h-16 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto"><ClipboardList className="w-8 h-8" /></div>
            <h4 className="text-sm font-bold text-gray-800">No exams created yet</h4>
            <button onClick={() => setCurrentView("builder")} className="px-5 py-2.5 bg-[#3B0042] hover:bg-[#2c0032] text-white text-xs font-bold rounded-xl transition-all">Create Exam Key</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 font-bold uppercase tracking-wider">
                  <th className="pb-3 font-semibold">Exam Title</th>
                  <th className="pb-3 font-semibold">Questions</th>
                  <th className="pb-3 font-semibold">Date Created</th>
                  <th className="pb-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {exams.map((ex) => (
                  <tr key={ex.exam_code} className="hover:bg-gray-50/50 transition-colors">
                    <td className="py-4 font-bold text-purple-950">{ex.exam_code}</td>
                    <td className="py-4 font-bold text-gray-800">{ex.num_questions}Q</td>
                    <td className="py-4 text-gray-400 font-mono">{new Date(ex.created_at).toLocaleDateString()}</td>
                    <td className="py-4 text-right space-x-2">
                      <button onClick={() => { setExamCode(ex.exam_code); setCurrentView("upload"); }} className="px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-[#3B0042] font-bold rounded-lg transition-all">Scan Papers</button>
                      <button onClick={() => { setQuestionsCount(ex.num_questions); setAnswerKey(ex.answer_key || {}); setNewExamCode(ex.exam_code); setCurrentView("builder"); }} className="px-2.5 py-1.5 border border-gray-200 hover:bg-purple-50 hover:border-purple-200 hover:text-purple-700 text-gray-500 rounded-lg transition-all" title="View / Edit Key"><Eye className="w-3.5 h-3.5" /></button>
                      <button onClick={() => handleExport(ex.exam_code, "csv")} className="px-2.5 py-1.5 border border-gray-200 hover:bg-gray-50 text-gray-500 rounded-lg transition-all inline-flex items-center gap-1 text-xs font-bold" title="Export results as CSV"><Download className="w-3.5 h-3.5" /> CSV</button>
                      <button onClick={() => handleExport(ex.exam_code, "pdf")} className="px-2.5 py-1.5 border border-gray-200 hover:bg-purple-50 hover:border-purple-200 hover:text-purple-700 text-gray-500 rounded-lg transition-all inline-flex items-center gap-1 text-xs font-bold" title="Export assessment receipts as PDF"><FileText className="w-3.5 h-3.5" /> PDF</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </motion.div>
  );
}
