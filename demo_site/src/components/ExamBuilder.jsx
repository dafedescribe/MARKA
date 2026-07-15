import React from 'react';
import { motion } from 'motion/react';
import { ArrowRight, Star } from 'lucide-react';

// Answer-key values can be:
//   "A"            single correct option
//   ["A","C"]      multiple accepted options (any of them is correct)
//   "*"            bonus question (any/no answer is correct)
const getSel = (val) => {
  if (val === '*') return { bonus: true, set: new Set() };
  if (Array.isArray(val)) return { bonus: false, set: new Set(val) };
  if (typeof val === 'string' && val) return { bonus: false, set: new Set([val]) };
  return { bonus: false, set: new Set() }; // unset — no default answer
};
const isAnswered = (v) => v === '*' || (Array.isArray(v) ? v.length > 0 : (typeof v === 'string' && v.length > 0));
const normalize = (set) => {
  const arr = [...set].sort();
  if (arr.length <= 1) return arr[0] || 'A';
  return arr;
};

export default function ExamBuilder({
  newExamCode, setNewExamCode, questionsCount, setQuestionsCount, optionsCount,
  answerKey, setAnswerKey, activeBuilderQ, setActiveBuilderQ,
  examSaving, examMsg, handleCreateExam, setCurrentView
}) {
  const toggleOption = (qNum, opt) => {
    setAnswerKey((prev) => {
      const { set } = getSel(prev[qNum]); // selecting a letter also clears bonus
      if (set.has(opt)) {
        if (set.size > 1) set.delete(opt); // keep at least one accepted answer
      } else {
        set.add(opt);
      }
      return { ...prev, [qNum]: normalize(set) };
    });
  };

  const toggleBonus = (qNum) => {
    setAnswerKey((prev) => ({ ...prev, [qNum]: prev[qNum] === '*' ? 'A' : '*' }));
  };

  const answeredCount = Array.from({ length: questionsCount }, (_, i) => answerKey[i + 1]).filter(isAnswered).length;
  const allAnswered = answeredCount === questionsCount;

  return (
    <motion.div
      key="builder-view"
      initial={{ opacity: 0, scale: 0.99 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.99 }}
      className="max-w-4xl mx-auto space-y-8"
    >
      <div className="flex justify-between items-center border-b border-gray-200 pb-4">
        <div>
          <h2 className="text-xl font-black text-[#3B0042]">Create Objective Answer Key</h2>
          <p className="text-xs text-gray-400">Arrow keys change question; press A/B/C/D to mark. Click multiple letters to accept any of them, or ★ for a bonus (always correct).</p>
        </div>
        <button onClick={() => setCurrentView("dashboard")} className="px-4 py-2 border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-bold rounded-xl">Cancel</button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
        <div className="md:col-span-5 space-y-6">
          <div className="bg-white p-6 rounded-2xl border border-gray-100 space-y-4 shadow-sm">
            <h3 className="text-xs font-extrabold text-[#3B0042] uppercase tracking-wider">Exam Information</h3>
            <div className="space-y-2">
              <label className="block text-xs font-bold text-gray-600 uppercase">Exam Title / Code</label>
              <input type="text" placeholder="e.g. BIO-T1" value={newExamCode} onChange={(e) => setNewExamCode(e.target.value)} className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] text-sm font-bold uppercase" />
            </div>
            <div className="space-y-2">
              <label className="block text-xs font-bold text-gray-600 uppercase">Total Questions</label>
              <select value={questionsCount} onChange={(e) => setQuestionsCount(parseInt(e.target.value, 10))} className="w-full px-3 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] text-sm bg-white font-bold">
                <option value={10}>10 Questions</option>
                <option value={20}>20 Questions</option>
                <option value={30}>30 Questions</option>
                <option value={40}>40 Questions</option>
                <option value={50}>50 Questions</option>
                <option value={60}>60 Questions</option>
                <option value={80}>80 Questions</option>
                <option value={100}>100 Questions</option>
              </select>
            </div>
            <div className="rounded-xl bg-purple-50/50 border border-purple-100 p-3 space-y-1">
              <p className="text-[11px] font-bold text-[#3B0042] uppercase tracking-wide">Answer key legend</p>
              <p className="text-[11px] text-gray-500 leading-relaxed">
                <span className="font-bold text-gray-700">One letter</span> = single answer ·
                <span className="font-bold text-gray-700"> Several letters</span> = any accepted ·
                <span className="font-bold text-gray-700"> ★</span> = bonus (marked correct regardless).
              </p>
            </div>
          </div>

          {examMsg && <p className="text-xs text-red-600 font-semibold">{examMsg}</p>}

          <button onClick={handleCreateExam} disabled={examSaving} className="w-full py-4 bg-[#3B0042] hover:bg-[#2c0032] disabled:bg-gray-400 text-white font-extrabold text-sm rounded-xl transition-all shadow-md active:scale-95 flex items-center justify-center gap-2">
            {examSaving ? "Saving..." : "Generate Sheet Layout Key"} <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        <div className="md:col-span-7 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-extrabold text-gray-400 uppercase tracking-widest">Options Key Builder</h3>
            <span className={`text-[11px] font-bold ${allAnswered ? 'text-emerald-600' : 'text-amber-600'}`}>
              {answeredCount}/{questionsCount} answered
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[500px] overflow-y-auto pr-2">
            {Array.from({ length: questionsCount }).map((_, idx) => {
              const qNum = idx + 1;
              const { bonus, set } = getSel(answerKey[qNum]);
              const unset = !bonus && set.size === 0;
              return (
                <div key={qNum} onClick={() => setActiveBuilderQ(qNum)} className={`flex flex-wrap items-center justify-between gap-y-2 p-3 rounded-xl border cursor-pointer transition-all ${activeBuilderQ === qNum ? "border-[#3B0042] bg-purple-50/20 ring-2 ring-[#3B0042]/10" : unset ? "border-amber-200 bg-amber-50/30" : "border-gray-100"}`}>
                  <span className="font-mono text-xs font-bold text-gray-400 flex items-center gap-1.5">
                    {unset && <span className="w-1.5 h-1.5 rounded-full bg-amber-400" title="Unanswered"></span>}
                    Q{String(qNum).padStart(2, "0")}
                  </span>
                  {/* Wrap the option cluster so the ★ bonus button is never pushed past
                      the card edge (and hidden behind the next column) on narrow widths. */}
                  <div className="flex flex-wrap items-center justify-end gap-1.5">
                    {["A", "B", "C", "D", "E"].slice(0, optionsCount).map((opt) => {
                      const active = !bonus && set.has(opt);
                      return (
                        <button
                          key={opt}
                          type="button"
                          onClick={(e) => { e.stopPropagation(); toggleOption(qNum, opt); }}
                          className={`w-7 h-7 rounded-full text-xs font-bold transition-all ${active ? "bg-[#3B0042] text-white" : bonus ? "bg-gray-50 text-gray-300" : "bg-gray-50 text-gray-500 hover:bg-gray-100"}`}
                        >
                          {opt}
                        </button>
                      );
                    })}
                    <span className="w-px h-5 bg-gray-200 mx-0.5"></span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); toggleBonus(qNum); }}
                      title="Bonus — any answer counts as correct"
                      className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${bonus ? "bg-amber-400 text-white" : "bg-gray-50 text-gray-400 hover:bg-amber-50 hover:text-amber-500"}`}
                    >
                      <Star className="w-3.5 h-3.5" fill={bonus ? "currentColor" : "none"} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
