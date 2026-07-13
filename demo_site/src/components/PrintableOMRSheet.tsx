import React from "react";
import { Printer, Check, Circle } from "lucide-react";

interface PrintableOMRSheetProps {
  questionsCount?: number;
  optionsCount?: number;
  studentName?: string;
  markedAnswers?: Record<number, string>;
  correctAnswers?: Record<number, string>;
}

export default function PrintableOMRSheet({
  questionsCount = 20,
  optionsCount = 4,
  studentName = "",
  markedAnswers = {},
  correctAnswers = {}
}: PrintableOMRSheetProps) {
  const options = ["A", "B", "C", "D", "E"].slice(0, optionsCount);

  // Group questions into columns of 10 to resemble real exam papers
  const columns: number[][] = [];
  const itemsPerColumn = 10;
  for (let i = 0; i < questionsCount; i += itemsPerColumn) {
    const col: number[] = [];
    for (let j = i; j < Math.min(i + itemsPerColumn, questionsCount); j++) {
      col.push(j + 1);
    }
    columns.push(col);
  }

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="bg-white text-gray-900 border border-gray-200 shadow-lg p-8 md:p-12 rounded-xl max-w-3xl mx-auto font-sans print:shadow-none print:border-none print:p-0">
      {/* Exam Sheet Header */}
      <div className="flex justify-between items-start border-b-4 border-double border-[#3B0042] pb-6 mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#3B0042] uppercase font-mono">
            MARKA STANDARD ANSWER SHEET
          </h1>
          <p className="text-xs text-gray-500 font-mono mt-1">
            OBJECTIVE EXAM SCANNING SHEET • VITE-SCAN COMPATIBLE
          </p>
        </div>
        <button
          onClick={handlePrint}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-[#3B0042] bg-purple-50 hover:bg-purple-100 rounded-lg transition-all border border-[#3B0042]/10 print:hidden"
        >
          <Printer className="w-3.5 h-3.5" />
          Print Sheet
        </button>
      </div>

      {/* Student Details Fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 bg-gray-50 p-4 rounded-lg border border-gray-100 print:bg-white print:border-gray-200">
        <div>
          <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
            Candidate Full Name (Block Letters)
          </label>
          <div className="h-10 border-b-2 border-gray-300 flex items-end pb-1 font-mono text-sm tracking-widest font-bold text-purple-900 uppercase">
            {studentName || "_________________________________"}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
              Exam Date
            </label>
            <div className="h-10 border-b-2 border-gray-300 flex items-end pb-1 font-mono text-sm">
              {new Date().toLocaleDateString()}
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1">
              Sheet Version
            </label>
            <div className="h-10 border-b-2 border-gray-300 flex items-end pb-1 font-mono text-sm font-bold text-[#3B0042]">
              MK-V01
            </div>
          </div>
        </div>
      </div>

      {/* Instructions */}
      <div className="text-[11px] text-gray-600 mb-8 border border-gray-200 rounded-lg p-3 bg-purple-50/30 print:bg-white">
        <span className="font-bold text-[#3B0042] uppercase mr-2">Instructions:</span>
        Use a dark blue or black pen or pencil to completely shade the circle of your chosen option.
        Ensure your marks are dark and completely fill the bubble. Do not cross, tick, or partially fill.
      </div>

      {/* Bubbles Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-8 md:gap-12">
        {columns.map((column, colIdx) => (
          <div key={colIdx} className="space-y-3">
            {column.map((qNum) => {
              const selectedOpt = markedAnswers[qNum];
              const correctOpt = correctAnswers[qNum];

              return (
                <div
                  key={qNum}
                  className="flex items-center justify-between py-1 border-b border-gray-50 print:border-gray-100"
                >
                  <span className="font-mono text-sm font-bold text-gray-400 w-8">
                    {String(qNum).padStart(2, "0")}.
                  </span>

                  <div className="flex items-center gap-6 flex-1 justify-around">
                    {options.map((opt) => {
                      const isSelected = selectedOpt?.toUpperCase() === opt.toUpperCase();
                      const isCorrect = correctOpt?.toUpperCase() === opt.toUpperCase();

                      let bubbleClass = "border-2 border-gray-400 text-gray-500 bg-white";
                      if (isSelected) {
                        if (correctOpt) {
                          // Results overlay mode
                          if (isCorrect) {
                            bubbleClass = "bg-green-600 border-green-600 text-white font-bold";
                          } else {
                            bubbleClass = "bg-red-600 border-red-600 text-white font-bold";
                          }
                        } else {
                          // Simple marked mode
                          bubbleClass = "bg-purple-950 border-purple-950 text-white font-bold shadow-sm";
                        }
                      } else if (isCorrect && correctOpt) {
                        // Highlight correct answer if student missed it
                        bubbleClass = "border-2 border-green-600 text-green-700 bg-green-50 animate-pulse font-bold";
                      }

                      return (
                        <div key={opt} className="flex flex-col items-center">
                          <div
                            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs transition-all ${bubbleClass}`}
                          >
                            {isSelected ? (
                              correctOpt && isCorrect ? (
                                <Check className="w-3.5 h-3.5 stroke-[3]" />
                              ) : (
                                opt
                              )
                            ) : (
                              opt
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Icon Check Indicator if viewing results */}
                  {correctOpt && (
                    <div className="w-12 text-right">
                      {selectedOpt === correctOpt ? (
                        <span className="text-xs font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded">
                          ✓ Pass
                        </span>
                      ) : selectedOpt === "" || !selectedOpt ? (
                        <span className="text-xs font-semibold text-amber-500 bg-amber-50 px-2 py-0.5 rounded">
                          Blank
                        </span>
                      ) : (
                        <span className="text-xs font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded">
                          ✗ Fail
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Technical Tracking Anchors */}
      <div className="mt-12 flex justify-between items-center text-[9px] font-mono text-gray-400 border-t border-gray-100 pt-4">
        <span>ID: OMR-TRACK-TOP-L</span>
        <span>[▮ ▮ ▮ ▮ ▮ ▮ ▮ ▮ ▮]</span>
        <span>ID: OMR-TRACK-BOTTOM-R</span>
      </div>
    </div>
  );
}
