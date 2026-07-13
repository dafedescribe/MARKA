import React from 'react';
import {
  FileSpreadsheet,
  UploadCloud,
  CheckCircle,
  ChevronRight,
  ShieldAlert,
  Loader2,
  KeyRound,
  Coins,
  Download,
  Sparkles,
  PhoneCall
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function Landing({ onGetStarted }) {
  const handleDownloadDemo = () => {
    const link = document.createElement('a');
    link.href = '/demo_omr_sheet.pdf';
    link.download = 'MARKA_Demo_OMR_Sheet.pdf';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans select-none">
      {/* Navigation Header */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-30 shadow-sm transition-all duration-200">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer">
            <div className="w-10 h-10 rounded-xl bg-[#3B0042] flex items-center justify-center text-white font-extrabold text-xl tracking-tighter shadow-md">
              M
            </div>
            <div>
              <span className="text-xl font-black text-[#3B0042] tracking-wider">MARKA</span>
              <span className="block text-[9px] font-bold text-gray-400 tracking-widest uppercase font-mono">
                OMR Grading Scanner
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm font-semibold text-gray-500 hover:text-[#3B0042] transition-colors">
              Features
            </a>
            <a href="#pricing-section" className="text-sm font-semibold text-gray-500 hover:text-[#3B0042] transition-colors">
              Pricing
            </a>
            <a href="#faq-section" className="text-sm font-semibold text-gray-500 hover:text-[#3B0042] transition-colors">
              FAQ
            </a>
          </nav>

          <div className="flex items-center gap-4">
            <button
              onClick={onGetStarted}
              className="px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-[#3B0042] hover:bg-[#2c0032] shadow-md hover:shadow-lg transition-all active:scale-95"
            >
              Login / Buy Credits
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-12 md:py-16">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
          className="space-y-24"
        >
          {/* Hero Section */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            <div className="lg:col-span-7 space-y-8 pr-4">
              <div className="inline-flex items-center gap-2 bg-purple-50 border border-purple-100 text-[#3B0042] px-4 py-1.5 rounded-full text-xs font-bold tracking-wide uppercase">
                <Sparkles className="w-3.5 h-3.5 text-amber-500 animate-spin" />
                First-of-its-kind Instant OMR Scanner
              </div>
              <h1 className="text-4xl md:text-6xl font-black text-gray-900 leading-tight tracking-tight">
                Stop Marking <br />
                <span className="text-[#3B0042] underline decoration-amber-400 decoration-wavy">
                  Objective Exams
                </span>{" "}
                Manually.
              </h1>
              <p className="text-lg md:text-xl text-gray-500 leading-relaxed max-w-2xl">
                Deploy MARKA in your school. Upload a batch of up to 100 scanned student sheets,
                and watch them grade in seconds. Credits are deducted only on success.
              </p>
              <div className="flex flex-wrap gap-4 pt-2">
                <button
                  onClick={onGetStarted}
                  className="px-8 py-4 bg-[#3B0042] text-white hover:bg-[#2c0032] font-extrabold rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2"
                >
                  Start Marking
                  <ChevronRight className="w-5 h-5" />
                </button>
                <button
                  onClick={handleDownloadDemo}
                  className="px-8 py-4 bg-white text-[#3B0042] hover:bg-gray-50 border border-gray-200 font-extrabold rounded-xl transition-all flex items-center gap-2"
                >
                  <Download size={20} />
                  Download Trial Sheet
                </button>
              </div>
            </div>

            <div className="lg:col-span-5 bg-white p-8 rounded-2xl border border-gray-100 shadow-xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-[#3B0042]/5 rounded-full -mr-16 -mt-16"></div>
              <div className="relative z-10 space-y-6">
                <div className="flex justify-between items-center pb-4 border-b border-gray-100">
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                    Visual Zero Engine
                  </span>
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    Ready to scan
                  </span>
                </div>

                <div className="space-y-4 p-4 bg-gray-50 rounded-xl border border-gray-100 font-mono text-xs">
                  <div className="flex justify-between font-bold border-b pb-2 text-purple-950">
                    <span>OMR CARD #01</span>
                    <span>CONFIDENCE 99%</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span>Q1. A B [C] D</span>
                      <span className="text-emerald-600">✓ Correct</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Q2. [A] B C D</span>
                      <span className="text-emerald-600">✓ Correct</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Q3. A [B] C D</span>
                      <span className="text-red-500">✗ Wrong (Key: C)</span>
                    </div>
                  </div>
                </div>

                <div className="text-center p-3 bg-purple-50/50 rounded-xl">
                  <span className="text-xs font-semibold text-[#3B0042]">
                    Takes a blurry photo → Isolates anchors → Grades bubbles → Outputs CSV
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Three-step illustration */}
          <div id="features" className="space-y-12">
            <div className="text-center space-y-4">
              <h2 className="text-3xl font-black text-gray-900">How It Works</h2>
              <p className="text-gray-500 max-w-lg mx-auto">
                Three incredibly obvious steps. No learning curve required.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all text-center space-y-4">
                <div className="w-14 h-14 rounded-full bg-purple-50 text-[#3B0042] flex items-center justify-center mx-auto text-2xl font-bold">
                  1
                </div>
                <h3 className="text-lg font-bold text-gray-900">Print Sheets</h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Download and print our standard OMR bubble templates for your students.
                </p>
              </div>

              <div className="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all text-center space-y-4">
                <div className="w-14 h-14 rounded-full bg-purple-50 text-[#3B0042] flex items-center justify-center mx-auto text-2xl font-bold">
                  2
                </div>
                <h3 className="text-lg font-bold text-gray-900">Upload Photos</h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Snap pictures of the sheets with your mobile phone or scan them in batches.
                </p>
              </div>

              <div className="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all text-center space-y-4">
                <div className="w-14 h-14 rounded-full bg-purple-50 text-[#3B0042] flex items-center justify-center mx-auto text-2xl font-bold">
                  3
                </div>
                <h3 className="text-lg font-bold text-gray-900">Get Results</h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  Instantly download individual scores, visual diagnostic analytics, or CSV exports.
                </p>
              </div>
            </div>
          </div>

          {/* Testimonials */}
          <div className="bg-purple-950 text-white rounded-3xl p-10 md:p-16 relative overflow-hidden">
            <div className="absolute inset-0 bg-[#3B0042] opacity-50"></div>
            <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
              <div className="space-y-6">
                <span className="text-xs font-bold text-amber-400 tracking-widest uppercase">
                  PILOT SCHOOLS FEEDBACK
                </span>
                <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight leading-tight">
                  Trusted by 45+ schools during our private beta
                </h2>
                <p className="text-purple-100 leading-relaxed">
                  Teachers reported saving over 6 hours per exam batch, eliminating fatigue, and
                  focusing more time on student interventions.
                </p>
              </div>
              <div className="space-y-6 bg-white/5 p-8 rounded-2xl border border-white/10 backdrop-blur-md">
                <p className="italic text-purple-50 text-sm leading-relaxed">
                  "We scanned 480 biology exam papers using MARKA. The results were finished within 10
                  minutes. The best part is there's no learning curve. Our teachers understood it instantly."
                </p>
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-amber-400 flex items-center justify-center text-purple-950 font-bold">
                    AO
                  </div>
                  <div>
                    <span className="block font-bold text-white text-sm">Mrs. Alabi Olakunle</span>
                    <span className="block text-xs text-purple-200">Exam Officer, Hillcrest College</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Pricing Cards */}
          <div id="pricing-section" className="space-y-12">
            <div className="text-center space-y-4">
              <h2 className="text-3xl font-black text-gray-900">Simple Pay-As-You-Go Credits</h2>
              <p className="text-gray-500 max-w-md mx-auto">
                No recurring plans. No monthly subscriptions. Buy credits when you need them.
                1 Credit = 1 Exam Sheet graded.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              {[
                { count: 100, price: "₦5,000", desc: "For small classroom tests" },
                { count: 250, price: "₦11,250", desc: "Best for midterm exams" },
                { count: 500, price: "₦20,000", desc: "Perfect for secondary schools" },
                { count: 1000, price: "₦35,000", desc: "For large end-of-term exams" }
              ].map((p, idx) => (
                <div
                  key={idx}
                  className={`bg-white border ${idx === 1 ? 'border-purple-500 shadow-md ring-4 ring-purple-50' : 'border-gray-100 shadow-sm hover:border-purple-300'} rounded-2xl p-6 flex flex-col justify-between transition-all text-center relative`}
                >
                  {idx === 1 && (
                    <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-purple-500 text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest">
                      Most Popular
                    </div>
                  )}
                  <div className="space-y-4 mt-2">
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-widest block">
                      PACKAGE
                    </span>
                    <h3 className="text-3xl font-black text-purple-950">{p.count} Credits</h3>
                    <p className="text-xs text-gray-400 leading-snug">{p.desc}</p>
                    <div className="text-2xl font-black text-gray-900 py-2">{p.price}</div>
                  </div>
                  <button
                    onClick={onGetStarted}
                    className={`mt-6 w-full py-3 rounded-xl font-bold text-sm transition-all ${idx === 1 ? 'bg-[#3B0042] text-white hover:bg-[#2c0032]' : 'bg-purple-50 text-[#3B0042] hover:bg-[#3B0042] hover:text-white'}`}
                  >
                    Choose Package
                  </button>
                </div>
              ))}
            </div>
            <p className="text-center text-sm font-semibold text-gray-500">
              Need 5,000+ credits? <a href="mailto:hello@marka.com.ng" className="text-[#3B0042] hover:underline">Contact us for Enterprise pricing.</a>
            </p>
          </div>

          {/* Footer / FAQ */}
          <footer id="faq-section" className="border-t border-gray-200 pt-16 pb-12 space-y-12">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
              <div className="space-y-6">
                <h3 className="text-xl font-bold text-gray-900">Frequently Asked Questions</h3>
                <div className="space-y-4">
                  <div>
                    <h4 className="font-bold text-gray-900">Do my credits expire?</h4>
                    <p className="text-sm text-gray-500 mt-1">
                      Never. Your purchased credits remain active in your account indefinitely.
                    </p>
                  </div>
                  <div>
                    <h4 className="font-bold text-gray-900">What happens if a scan fails?</h4>
                    <p className="text-sm text-gray-500 mt-1">
                      No credits are deducted for blurry or failed scans. You can retry as many times as you like.
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <h3 className="text-xl font-bold text-gray-900">Contact & Support</h3>
                <p className="text-sm text-gray-500">
                  Need help setting up OMR templates or custom bulk credits for your district?
                  Our support team is active.
                </p>
                <div className="flex flex-wrap gap-4">
                  <a
                    href="mailto:support@marka.com.ng"
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-200 text-sm font-semibold hover:bg-gray-50"
                  >
                    <PhoneCall className="w-4 h-4 text-purple-600" />
                    support@marka.com.ng
                  </a>
                </div>
              </div>
            </div>

            <div className="border-t border-gray-100 pt-8 flex flex-col md:flex-row justify-between items-center text-xs text-gray-400 gap-4">
              <span>© {new Date().getFullYear()} MARKA OMR. Built for premium teacher confidence.</span>
              <div className="flex gap-6">
                <a href="#" className="hover:underline">Privacy Policy</a>
                <a href="#" className="hover:underline">Terms of Service</a>
              </div>
            </div>
          </footer>
        </motion.div>
      </main>
    </div>
  );
}
