import React, { useState } from "react";
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
  Flame,
  ArrowRight,
  PhoneCall,
  Sparkles,
  RefreshCw
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { UserAccount, DemoConfig } from "../types";

interface LandingPageProps {
  onLoginSuccess: (user: UserAccount) => void;
  onLaunchDemo: () => void;
  onSetBanner: (msg: string | null) => void;
  apiBase: string;
}

export default function LandingPage({
  onLoginSuccess,
  onLaunchDemo,
  onSetBanner,
  apiBase
}: LandingPageProps) {
  const [activeTab, setActiveTab] = useState<"home" | "buy" | "login" | "demo">("home");

  // Buy credits states
  const [markaIdInput, setMarkaIdInput] = useState("");
  const [isNewCustomer, setIsNewCustomer] = useState(true);
  const [selectedPackage, setSelectedPackage] = useState<100 | 250 | 500 | 1000>(250);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [generatedCreds, setGeneratedCreds] = useState<{
    markaId: string;
    pin: string;
    credits: number;
    isNew: boolean;
  } | null>(null);

  // Login states
  const [loginId, setLoginId] = useState("");
  const [loginPin, setLoginPin] = useState("");
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Demo states
  const [demoCount, setDemoCount] = useState(0);
  const [maxDemo, setMaxDemo] = useState(5);
  const [demoDownloading, setDemoDownloading] = useState(false);
  const [demoDownloadErr, setDemoDownloadErr] = useState("");

  // Server health alert
  const [serverStatus, setServerStatus] = useState<"checking" | "online" | "sleeping">("checking");

  React.useEffect(() => {
    // Backend wake-up and health check
    fetch(`${apiBase}/api/health`)
      .then((res) => {
        if (res.ok) setServerStatus("online");
        else setServerStatus("sleeping");
      })
      .catch(() => setServerStatus("sleeping"));
  }, [apiBase]);

  const handleCheckout = async () => {
    setIsProcessingPayment(true);
    // Simulate Paystack checkout window overlay beautifully
    setTimeout(async () => {
      try {
        const response = await fetch(`${apiBase}/api/register-credits`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            markaId: isNewCustomer ? null : markaIdInput,
            creditsPackage: selectedPackage,
          }),
        });
        const data = await response.json();
        if (response.ok) {
          setGeneratedCreds({
            markaId: data.user.markaId,
            pin: data.user.pin,
            credits: data.user.credits,
            isNew: data.isNew,
          });
          onSetBanner(`Successfully purchased ${selectedPackage} credits!`);
        } else {
          alert(data.error || "Purchase failed.");
        }
      } catch (err) {
        console.error(err);
        alert("Server error completing purchase simulation.");
      } finally {
        setIsProcessingPayment(false);
      }
    }, 1500);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    setIsLoggingIn(true);

    try {
      const response = await fetch(`${apiBase}/api/auth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markaId: loginId, pin: loginPin }),
      });
      const data = await response.json();
      if (response.ok) {
        onLoginSuccess(data.user);
      } else {
        setLoginError(data.error || "Wrong MARKA ID or PIN.");
      }
    } catch (err) {
      setLoginError("Could not connect to server. Please try again.");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const downloadSamplePaper = async () => {
    setDemoDownloading(true);
    setDemoDownloadErr("");
    try {
      const response = await fetch(`${apiBase}/api/demo/download-sheet`, {
        method: "POST",
      });
      const data = await response.json();
      if (response.ok) {
        setDemoCount(data.downloadCount);
        setMaxDemo(data.maxDownloads);

        // Download simulation file
        const element = document.createElement("a");
        const file = new Blob(
          [
            `MARKA SAMPLE OMR ANSWER SHEET TEMPLATE\n=======================================\nQuestions: 20 | Options: 4\nUse this mock sheet to test camera and upload flows.\n\n[PRINT THIS PAPER TO BEGIN GRADE SCANNING]`
          ],
          { type: "text/plain" }
        );
        element.href = URL.createObjectURL(file);
        element.download = "marka_sample_sheet.txt";
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
      } else {
        setDemoDownloadErr(data.error || "Download restriction hit.");
      }
    } catch (err) {
      setDemoDownloadErr("Failed to verify download limits.");
    } finally {
      setDemoDownloading(false);
    }
  };

  const downloadReceiptAsPDF = () => {
    const element = document.createElement("a");
    const file = new Blob(
      [
        `==================================================\n`,
        `                 MARKA RECEIPT                    \n`,
        `==================================================\n`,
        `MARKA ID: ${generatedCreds?.markaId}\n`,
        `PIN:      ${generatedCreds?.pin}\n`,
        `CREDITS:  ${generatedCreds?.credits}\n`,
        `DATE:     ${new Date().toLocaleString()}\n`,
        `STATUS:   PAID VIA PAYSTACK (SIMULATION)\n`,
        `==================================================\n`,
        `Keep these credentials safe. Use them to access your credits.\n`
      ],
      { type: "text/plain" }
    );
    element.href = URL.createObjectURL(file);
    element.download = `marka_receipt_${generatedCreds?.markaId}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      {/* Wake-up alert overlay for Render server spin downs */}
      {serverStatus === "checking" && (
        <div className="fixed inset-0 bg-[#3B0042]/95 flex flex-col items-center justify-center z-50 p-6 text-white">
          <Loader2 className="w-12 h-12 animate-spin text-purple-200 mb-4" />
          <h2 className="text-xl font-bold tracking-tight">Starting MARKA Server...</h2>
          <p className="text-sm text-purple-200/80 mt-2 max-w-sm text-center">
            Establishing server environment. This usually takes less than a minute. Please stand by.
          </p>
        </div>
      )}

      {/* Navigation Header */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-30 shadow-sm transition-all duration-200">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div
            onClick={() => setActiveTab("home")}
            className="flex items-center gap-3 cursor-pointer select-none"
          >
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
            <button
              onClick={() => setActiveTab("home")}
              className={`text-sm font-semibold transition-colors ${
                activeTab === "home" ? "text-[#3B0042]" : "text-gray-500 hover:text-[#3B0042]"
              }`}
            >
              Features
            </button>
            <a
              href="#pricing-section"
              onClick={() => setActiveTab("home")}
              className="text-sm font-semibold text-gray-500 hover:text-[#3B0042] transition-colors"
            >
              Pricing
            </a>
            <button
              onClick={() => setActiveTab("demo")}
              className={`text-sm font-semibold transition-colors ${
                activeTab === "demo" ? "text-[#3B0042]" : "text-gray-500 hover:text-[#3B0042]"
              }`}
            >
              Demo Credentials
            </button>
            <a
              href="#faq-section"
              onClick={() => setActiveTab("home")}
              className="text-sm font-semibold text-gray-500 hover:text-[#3B0042] transition-colors"
            >
              FAQ
            </a>
          </nav>

          <div className="flex items-center gap-4">
            <button
              onClick={() => setActiveTab("login")}
              className="px-5 py-2.5 rounded-xl text-sm font-bold text-[#3B0042] bg-purple-50 hover:bg-purple-100 transition-all active:scale-95"
            >
              Login
            </button>
            <button
              onClick={() => setActiveTab("buy")}
              className="px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-[#3B0042] hover:bg-[#2c0032] shadow-md hover:shadow-lg transition-all active:scale-95"
            >
              Buy Credits
            </button>
          </div>
        </div>
      </header>

      {/* Main Container with Screen transitions */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-12 md:py-16">
        <AnimatePresence mode="wait">
          {activeTab === "home" && (
            <motion.div
              key="home-screen"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.18 }}
              className="space-y-24"
            >
              {/* Screen 1 Hero Section */}
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
                    Deploy MARKA in your school. Upload a batch of up to 50 scanned student sheets,
                    and watch them grade in seconds. Credits are deducted only on success.
                  </p>
                  <div className="flex flex-wrap gap-4 pt-2">
                    <button
                      onClick={() => setActiveTab("demo")}
                      className="px-8 py-4 bg-[#3B0042] text-white hover:bg-[#2c0032] font-extrabold rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2"
                    >
                      Start Marking
                      <ChevronRight className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => setActiveTab("demo")}
                      className="px-8 py-4 bg-white text-[#3B0042] hover:bg-gray-50 border border-gray-200 font-extrabold rounded-xl transition-all"
                    >
                      Watch Demo
                    </button>
                  </div>
                </div>

                <div className="lg:col-span-5 bg-white p-8 rounded-2xl border border-gray-100 shadow-xl relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-[#3B0042]/5 rounded-full -mr-16 -mt-16"></div>
                  <div className="relative z-10 space-y-6">
                    <div className="flex justify-between items-center pb-4 border-b border-gray-100">
                      <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">
                        Live Preview Engine
                      </span>
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-bold">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        Ready to scan
                      </span>
                    </div>

                    {/* Simple Vector OMR Mockup inside card */}
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
                        Try the instant live grading with our Demo credentials
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Three-step illustration */}
              <div className="space-y-12">
                <div className="text-center space-y-4">
                  <h2 className="text-3xl font-black text-gray-900">How It Works</h2>
                  <p className="text-gray-500 max-w-lg mx-auto">
                    Three incredibly obvious steps. No manual or registration required.
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
                    { count: 100, price: "₦15,000", desc: "For small classroom tests" },
                    { count: 250, price: "₦32,500", desc: "Best for midterm exams" },
                    { count: 500, price: "₦60,000", desc: "Perfect for secondary schools" },
                    { count: 1000, price: "₦110,000", desc: "For large end-of-term exams" }
                  ].map((p, idx) => (
                    <div
                      key={idx}
                      className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm flex flex-col justify-between hover:border-purple-300 transition-all text-center"
                    >
                      <div className="space-y-4">
                        <span className="text-xs font-bold text-gray-400 uppercase tracking-widest block">
                          PACKAGE
                        </span>
                        <h3 className="text-3xl font-black text-purple-950">{p.count} Credits</h3>
                        <p className="text-xs text-gray-400 leading-snug">{p.desc}</p>
                        <div className="text-2xl font-black text-gray-900 py-2">{p.price}</div>
                      </div>
                      <button
                        onClick={() => {
                          setSelectedPackage(p.count as any);
                          setActiveTab("buy");
                        }}
                        className="mt-6 w-full py-3 rounded-xl bg-purple-50 text-[#3B0042] hover:bg-[#3B0042] hover:text-white font-bold text-sm transition-all"
                      >
                        Choose Package
                      </button>
                    </div>
                  ))}
                </div>
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
                        href="mailto:support@marka.ng"
                        className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-200 text-sm font-semibold hover:bg-gray-50"
                      >
                        <PhoneCall className="w-4 h-4 text-purple-600" />
                        support@marka.ng
                      </a>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-100 pt-8 flex flex-col md:flex-row justify-between items-center text-xs text-gray-400 gap-4">
                  <span>© 2026 MARKA OMR. Built for premium teacher confidence.</span>
                  <div className="flex gap-6">
                    <a href="#" className="hover:underline">Privacy Policy</a>
                    <a href="#" className="hover:underline">Terms of Service</a>
                  </div>
                </div>
              </footer>
            </motion.div>
          )}

          {activeTab === "buy" && (
            <motion.div
              key="buy-screen"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              className="max-w-xl mx-auto bg-white p-8 rounded-2xl border border-gray-100 shadow-xl space-y-8"
            >
              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto mb-2">
                  <Coins className="w-6 h-6" />
                </div>
                <h2 className="text-2xl font-black text-gray-900">Purchase Credits</h2>
                <p className="text-xs text-gray-500">
                  Instant activation via Paystack simulation. No account registration required.
                </p>
              </div>

              {!generatedCreds ? (
                <div className="space-y-6">
                  {/* Customer Status Select */}
                  <div className="grid grid-cols-2 gap-4 bg-gray-50 p-1.5 rounded-xl border border-gray-100">
                    <button
                      type="button"
                      onClick={() => setIsNewCustomer(true)}
                      className={`py-2.5 rounded-lg text-xs font-bold transition-all ${
                        isNewCustomer
                          ? "bg-white text-[#3B0042] shadow-sm"
                          : "text-gray-500 hover:text-gray-900"
                      }`}
                    >
                      I'm a New Customer
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsNewCustomer(false)}
                      className={`py-2.5 rounded-lg text-xs font-bold transition-all ${
                        !isNewCustomer
                          ? "bg-white text-[#3B0042] shadow-sm"
                          : "text-gray-500 hover:text-gray-900"
                      }`}
                    >
                      Top-up Existing Account
                    </button>
                  </div>

                  {/* Existing MARKA ID Input */}
                  {!isNewCustomer && (
                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-gray-600 uppercase">
                        Your MARKA ID
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. M-123456"
                        value={markaIdInput}
                        onChange={(e) => setMarkaIdInput(e.target.value)}
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] font-mono uppercase text-sm"
                      />
                    </div>
                  )}

                  {/* Package Selector */}
                  <div className="space-y-3">
                    <label className="block text-xs font-bold text-gray-600 uppercase">
                      Select Credits Volume
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                      {[100, 250, 500, 1000].map((vol) => (
                        <div
                          key={vol}
                          onClick={() => setSelectedPackage(vol as any)}
                          className={`cursor-pointer border p-4 rounded-xl text-center transition-all ${
                            selectedPackage === vol
                              ? "border-[#3B0042] bg-purple-50/40 text-[#3B0042] ring-2 ring-[#3B0042]/10"
                              : "border-gray-150 hover:border-gray-300"
                          }`}
                        >
                          <span className="block text-lg font-black">{vol}</span>
                          <span className="block text-[10px] text-gray-400 font-bold uppercase mt-1">
                            {vol === 100
                              ? "₦15,000"
                              : vol === 250
                              ? "₦32,500"
                              : vol === 500
                              ? "₦60,000"
                              : "₦110,000"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Paystack simulated checkout CTA */}
                  <button
                    onClick={handleCheckout}
                    disabled={isProcessingPayment || (!isNewCustomer && !markaIdInput)}
                    className="w-full py-4 rounded-xl bg-[#3B0042] hover:bg-[#2c0032] disabled:bg-gray-300 text-white font-extrabold flex items-center justify-center gap-2 transition-all shadow-md active:scale-95"
                  >
                    {isProcessingPayment ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Initiating Paystack Checkout...
                      </>
                    ) : (
                      <>
                        Secure checkout via Paystack
                        <ArrowRight className="w-5 h-5" />
                      </>
                    )}
                  </button>
                </div>
              ) : (
                /* Successful Buy View: Shows MARKA ID and PIN */
                <div className="space-y-6 text-center">
                  <div className="bg-emerald-50 text-emerald-700 p-4 rounded-xl border border-emerald-100 flex items-center gap-3 justify-center text-sm font-bold">
                    <CheckCircle className="w-5 h-5" />
                    Simulated Payment Approved Successfully!
                  </div>

                  <div className="bg-purple-50/50 p-6 rounded-2xl border border-purple-100 space-y-4">
                    <p className="text-xs text-gray-500 font-semibold uppercase">
                      YOUR SECURITY ACCESS KEYWORDS
                    </p>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-white p-3 rounded-xl border border-gray-100">
                        <span className="block text-[10px] font-bold text-gray-400 uppercase">
                          MARKA ID
                        </span>
                        <span className="text-xl font-mono font-black text-[#3B0042] tracking-wider select-all">
                          {generatedCreds.markaId}
                        </span>
                      </div>
                      <div className="bg-white p-3 rounded-xl border border-gray-100">
                        <span className="block text-[10px] font-bold text-gray-400 uppercase">
                          SECRET PIN
                        </span>
                        <span className="text-xl font-mono font-black text-amber-600 select-all">
                          {generatedCreds.pin}
                        </span>
                      </div>
                    </div>

                    <p className="text-[11px] text-gray-400 leading-normal">
                      Write these down or download the PDF receipt immediately. You will use these
                      anytime to log in and access your balance of{" "}
                      <strong className="text-purple-950">{generatedCreds.credits} credits</strong>.
                    </p>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-4">
                    <button
                      onClick={downloadReceiptAsPDF}
                      className="flex-1 py-3.5 border border-gray-200 text-gray-700 hover:bg-gray-50 font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2"
                    >
                      <Download className="w-4 h-4" />
                      Download Receipt PDF
                    </button>
                    <button
                      onClick={() => {
                        onLoginSuccess({
                          markaId: generatedCreds.markaId,
                          pin: generatedCreds.pin,
                          credits: generatedCreds.credits,
                          createdAt: new Date().toISOString()
                        });
                      }}
                      className="flex-1 py-3.5 bg-[#3B0042] text-white hover:bg-[#2c0032] font-bold text-sm rounded-xl transition-all"
                    >
                      Launch Dashboard
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {activeTab === "login" && (
            <motion.div
              key="login-screen"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              className="max-w-md mx-auto bg-white p-8 rounded-2xl border border-gray-100 shadow-xl space-y-8"
            >
              <div className="text-center space-y-2">
                <div className="w-12 h-12 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto mb-2">
                  <KeyRound className="w-6 h-6" />
                </div>
                <h2 className="text-2xl font-black text-gray-900">Access Your Credits</h2>
                <p className="text-xs text-gray-500">
                  No email or password registration is required.
                </p>
              </div>

              {loginError && (
                <div className="bg-red-50 text-red-700 p-3.5 rounded-xl border border-red-100 text-xs font-bold flex items-center gap-2">
                  <ShieldAlert className="w-4.5 h-4.5 flex-shrink-0" />
                  {loginError}
                </div>
              )}

              <form onSubmit={handleLogin} className="space-y-6">
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-gray-600 uppercase tracking-wide">
                    MARKA ID
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. MARKA-DEMO or M-123456"
                    value={loginId}
                    onChange={(e) => setLoginId(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] font-mono text-sm uppercase"
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-bold text-gray-600 uppercase tracking-wide">
                    PIN
                  </label>
                  <input
                    type="password"
                    required
                    maxLength={6}
                    placeholder="e.g. 1234"
                    value={loginPin}
                    onChange={(e) => setLoginPin(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] font-mono text-sm"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoggingIn}
                  className="w-full py-4 bg-[#3B0042] hover:bg-[#2c0032] disabled:bg-purple-900/50 text-white font-extrabold rounded-xl transition-all flex items-center justify-center gap-2 shadow-md active:scale-95"
                >
                  {isLoggingIn ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Verifying credits...
                    </>
                  ) : (
                    "Continue to Dashboard"
                  )}
                </button>
              </form>

              <div className="text-center pt-2">
                <button
                  onClick={() => {
                    setLoginId("MARKA-DEMO");
                    setLoginPin("1234");
                  }}
                  className="text-xs text-purple-700 hover:underline font-bold inline-flex items-center gap-1 bg-purple-50 px-3 py-1.5 rounded-full"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-500 animate-pulse" />
                  Auto-fill Demo Credentials
                </button>
              </div>
            </motion.div>
          )}

          {activeTab === "demo" && (
            <motion.div
              key="demo-screen"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              className="max-w-2xl mx-auto bg-white p-8 rounded-2xl border border-gray-100 shadow-xl space-y-8"
            >
              <div className="text-center space-y-2">
                <div className="inline-flex items-center gap-1.5 bg-amber-50 text-amber-700 px-3 py-1 rounded-full text-[11px] font-bold uppercase mb-2 border border-amber-100">
                  <Flame className="w-3.5 h-3.5 animate-pulse" />
                  INSTANT TRIAL ZONE
                </div>
                <h2 className="text-2xl font-black text-gray-900">Try MARKA Instantly</h2>
                <p className="text-xs text-gray-500">
                  Step in and try scanning simulated or printable OMR sheets.
                </p>
              </div>

              {demoDownloadErr && (
                <div className="bg-red-50 text-red-700 p-3.5 rounded-xl border border-red-100 text-xs font-bold">
                  {demoDownloadErr}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="border border-purple-100 bg-purple-50/20 p-6 rounded-2xl space-y-4">
                  <h3 className="font-bold text-[#3B0042] text-sm">Demo Access Pass</h3>
                  <p className="text-xs text-gray-500 leading-relaxed">
                    We have created a preloaded demo credentials block with{" "}
                    <strong>382 free credits</strong> so you can play around with answer key builder and
                    results instantly.
                  </p>
                  <div className="bg-white p-4 rounded-xl border border-gray-100 space-y-2 text-xs">
                    <div className="flex justify-between font-mono">
                      <span className="text-gray-400">DEMO ID:</span>
                      <strong className="text-purple-950 font-bold">MARKA-DEMO</strong>
                    </div>
                    <div className="flex justify-between font-mono">
                      <span className="text-gray-400">DEMO PIN:</span>
                      <strong className="text-purple-950 font-bold">1234</strong>
                    </div>
                  </div>
                  <button
                    onClick={onLaunchDemo}
                    className="w-full py-3 bg-[#3B0042] hover:bg-[#2c0032] text-white font-extrabold text-xs rounded-xl transition-all shadow-md active:scale-95"
                  >
                    Launch Sandbox Demo
                  </button>
                </div>

                <div className="border border-gray-150 p-6 rounded-2xl space-y-4 flex flex-col justify-between">
                  <div className="space-y-3">
                    <h3 className="font-bold text-gray-900 text-sm">Download Sample Sheets</h3>
                    <p className="text-xs text-gray-500 leading-relaxed">
                      Need papers to scan? Download standard 20-question, 4-option printable OMR templates.
                    </p>
                  </div>
                  <div className="space-y-3">
                    <button
                      onClick={downloadSamplePaper}
                      disabled={demoDownloading}
                      className="w-full py-3 bg-purple-50 hover:bg-purple-100 disabled:bg-gray-100 text-[#3B0042] disabled:text-gray-400 font-extrabold text-xs rounded-xl transition-all flex items-center justify-center gap-2 border border-purple-100"
                    >
                      {demoDownloading ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Downloading...
                        </>
                      ) : (
                        <>
                          <Download className="w-4 h-4" />
                          Download Mock Sheets ({demoCount}/{maxDemo})
                        </>
                      )}
                    </button>
                    <span className="block text-[10px] text-gray-400 leading-normal text-center">
                      Server strictly limits demo downloads to 5 per session to prevent abuse.
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
