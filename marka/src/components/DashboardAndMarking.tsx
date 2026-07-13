import React, { useState, useRef, useEffect } from "react";
import {
  Coins,
  PlusCircle,
  History,
  HardDrive,
  Trash2,
  Upload,
  Camera,
  AlertTriangle,
  RefreshCw,
  Play,
  ArrowRight,
  Sparkles,
  Check,
  X,
  Plus,
  Minus,
  Download,
  Search,
  Filter,
  Maximize2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  User,
  BadgeAlert,
  Loader2
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { UserAccount, BatchMarking, GradedPaper } from "../types";
import PrintableOMRSheet from "./PrintableOMRSheet";

interface DashboardAndMarkingProps {
  user: UserAccount;
  initialBatches: BatchMarking[];
  initialPapers: GradedPaper[];
  onLogout: () => void;
  apiBase: string;
}

export default function DashboardAndMarking({
  user,
  initialBatches,
  initialPapers,
  onLogout,
  apiBase
}: DashboardAndMarkingProps) {
  // Navigation states
  const [currentView, setCurrentView] = useState<"dashboard" | "builder" | "upload" | "results" | "gallery">("dashboard");

  // Core records
  const [credits, setCredits] = useState(user.credits);
  const [batches, setBatches] = useState<BatchMarking[]>(initialBatches);
  const [papers, setPapers] = useState<GradedPaper[]>(initialPapers);

  // Active session parameters
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(batches[0]?.id || null);
  const [newBatchTitle, setNewBatchTitle] = useState("");
  const [newBatchSubject, setNewBatchSubject] = useState("Biology");
  const [questionsCount, setQuestionsCount] = useState(20);
  const [optionsCount, setOptionsCount] = useState(4);
  const [answerKey, setAnswerKey] = useState<Record<number, string>>({});
  const [activeBuilderQ, setActiveBuilderQ] = useState(1);

  // Expandable marking settings
  const [bonusEnabled, setBonusEnabled] = useState(false);
  const [bonusMarks, setBonusMarks] = useState(2);
  const [negativeMarking, setNegativeMarking] = useState(0);

  // Upload/Queue states
  const [uploadQueue, setUploadQueue] = useState<{
    id: string;
    filename: string;
    base64: string;
    status: "queued" | "compressing" | "uploading" | "grading" | "complete" | "rejected";
    error: string | null;
    paper?: GradedPaper;
  }[]>([]);
  const [isUploadingBatch, setIsUploadingBatch] = useState(false);
  const [blurryHold, setBlurryHold] = useState<{
    id: string;
    filename: string;
    base64: string;
  } | null>(null);

  // Camera capture modal states
  const [showCamera, setShowCamera] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Gallery Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("All");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");

  // Results display
  const [activeResultsPaper, setActiveResultsPaper] = useState<GradedPaper | null>(null);

  // Delete confirmations
  const [deleteTarget, setDeleteTarget] = useState<{ type: "paper" | "batch" | "all"; id?: string } | null>(null);

  // Setup initial key when count changes
  useEffect(() => {
    const key: Record<number, string> = {};
    for (let i = 1; i <= questionsCount; i++) {
      key[i] = answerKey[i] || "A";
    }
    setAnswerKey(key);
  }, [questionsCount]);

  // Keyboard navigation for Answer Key Builder
  useEffect(() => {
    if (currentView !== "builder") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveBuilderQ((prev) => Math.min(questionsCount, prev + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveBuilderQ((prev) => Math.max(1, prev - 1));
      } else if (["a", "b", "c", "d", "e", "A", "B", "C", "D", "E"].includes(e.key)) {
        const option = e.key.toUpperCase();
        if (optionsCount >= (option.charCodeAt(0) - 64)) {
          setAnswerKey((prev) => ({ ...prev, [activeBuilderQ]: option }));
          // Auto advance for ultra fast flows
          if (activeBuilderQ < questionsCount) {
            setActiveBuilderQ((prev) => prev + 1);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentView, activeBuilderQ, questionsCount, optionsCount]);

  // Web camera activation
  const startCamera = async () => {
    setShowCamera(true);
    setTimeout(async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        alert("Camera permission denied or camera unsupported.");
        setShowCamera(false);
      }
    }, 100);
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
    }
    setShowCamera(false);
  };

  const capturePhoto = () => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL("image/jpeg");
        
        // Add to queue as compressed camera capture
        handleFilesAdded([{ file: null, customUrl: dataUrl, name: `camera_scan_${Date.now()}.jpg` }]);
        stopCamera();
      }
    }
  };

  // Immediate Client-Side Compression to 1600px JPEG 80-85%
  const handleFilesAdded = async (items: { file: File | null; customUrl?: string; name: string }[]) => {
    const newItems = [];

    for (const item of items) {
      let dataUrl = item.customUrl || "";
      if (item.file) {
        dataUrl = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve(e.target?.result as string || "");
          reader.readAsDataURL(item.file!);
        });
      }

      // Perform canvas compression
      const compressedUrl = await new Promise<string>((resolve) => {
        const img = new Image();
        img.src = dataUrl;
        img.onload = () => {
          const canvas = document.createElement("canvas");
          const ctx = canvas.getContext("2d");
          const max_size = 1600;
          let width = img.width;
          let height = img.height;

          if (width > height) {
            if (width > max_size) {
              height *= max_size / width;
              width = max_size;
            }
          } else {
            if (height > max_size) {
              width *= max_size / height;
              height = max_size;
            }
          }

          canvas.width = width;
          canvas.height = height;
          ctx?.drawImage(img, 0, 0, width, height);
          resolve(canvas.toDataURL("image/jpeg", 0.82));
        };
      });

      newItems.push({
        id: `q-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
        filename: item.name,
        base64: compressedUrl,
        status: "queued" as const,
        error: null
      });
    }

    setUploadQueue((prev) => [...prev, ...newItems]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files) as File[];
    const validFiles = files.filter((f) => f.type.startsWith("image/")).map((f) => ({ file: f, name: f.name }));
    if (validFiles.length > 0) {
      handleFilesAdded(validFiles);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files) as File[];
      const validFiles = files.map((f) => ({ file: f, name: f.name }));
      handleFilesAdded(validFiles);
    }
  };

  // Start Batch Processing Queue
  const runBatchProcessing = async () => {
    if (!selectedBatchId) return;
    setIsUploadingBatch(true);

    // Process items sequentially to prevent high concurrency rate limits
    const currentQueue = [...uploadQueue];
    for (let i = 0; i < currentQueue.length; i++) {
      const item = currentQueue[i];
      if (item.status === "complete" || item.status === "rejected") continue;

      // Update item state to uploading
      setUploadQueue((prev) =>
        prev.map((itm) => (itm.id === item.id ? { ...itm, status: "uploading" } : itm))
      );

      // Simple network animation latency
      await new Promise((resolve) => setTimeout(resolve, 300));

      setUploadQueue((prev) =>
        prev.map((itm) => (itm.id === item.id ? { ...itm, status: "grading" } : itm))
      );

      try {
        const response = await fetch(`${apiBase}/api/grade-paper`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            batchId: selectedBatchId,
            filename: item.filename,
            image: item.base64,
            markaId: user.markaId,
            pin: user.pin
          })
        });

        const data = await response.json();

        if (response.ok) {
          // Success
          setCredits(data.remainingCredits);
          setPapers((prev) => [data.paper, ...prev]);
          setUploadQueue((prev) =>
            prev.map((itm) =>
              itm.id === item.id ? { ...itm, status: "complete", paper: data.paper } : itm
            )
          );
        } else {
          // If blurry, catch blurry exception for user correction overlay without interrupting rest of batch
          if (data.isBlurry) {
            setBlurryHold({
              id: item.id,
              filename: item.filename,
              base64: item.base64
            });
            setUploadQueue((prev) =>
              prev.map((itm) =>
                itm.id === item.id ? { ...itm, status: "rejected", error: data.paper.errorMessage, paper: data.paper } : itm
              )
            );
            // Non-blocking wait for manual correction or skip
            // The loop will freeze or we can continue grading others. Let's CONTINUE grading other papers!
            // "Never block good papers because of one bad paper."
            continue;
          } else {
            // General failure
            setUploadQueue((prev) =>
              prev.map((itm) =>
                itm.id === item.id ? { ...itm, status: "rejected", error: data.error || "Grading failed." } : itm
              )
            );
          }
        }
      } catch (err) {
        setUploadQueue((prev) =>
          prev.map((itm) =>
            itm.id === item.id ? { ...itm, status: "rejected", error: "Connection error." } : itm
          )
        );
      }
    }

    // Refresh batch listing count
    const res = await fetch(`${apiBase}/api/user-data?markaId=${user.markaId}&pin=${user.pin}`);
    const uData = await res.json();
    if (res.ok) {
      setBatches(uData.batches);
    }
    setIsUploadingBatch(false);
  };

  // Blurry error corrections
  const handleBlurrySkip = () => {
    setBlurryHold(null);
  };

  const handleBlurryReplace = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0] && blurryHold) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = async (ev) => {
        const replacementBase64 = ev.target?.result as string;
        const targetId = blurryHold.id;

        // Reset state in queue to retry
        setUploadQueue((prev) =>
          prev.map((itm) =>
            itm.id === targetId ? { ...itm, base64: replacementBase64, status: "queued", error: null } : itm
          )
        );
        setBlurryHold(null);
        // Automatically rerun queue
        setTimeout(() => {
          runBatchProcessing();
        }, 300);
      };
      reader.readAsDataURL(file);
    }
  };

  // Submit Answer Key Builder to generate batch
  const handleCreateBatch = async () => {
    if (!newBatchTitle) {
      alert("Please provide an Exam Title.");
      return;
    }

    try {
      const res = await fetch(`${apiBase}/api/create-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newBatchTitle,
          subject: newBatchSubject,
          questionsCount,
          optionsCount,
          answerKey,
          bonusEnabled,
          bonusMarks,
          negativeMarking,
          markaId: user.markaId,
          pin: user.pin
        })
      });

      const data = await res.json();
      if (res.ok) {
        setBatches((prev) => [data.batch, ...prev]);
        setSelectedBatchId(data.batch.id);
        setUploadQueue([]); // clear queue
        setCurrentView("upload");
      } else {
        alert(data.error || "Failed to establish batch.");
      }
    } catch (err) {
      alert("Network error creating batch.");
    }
  };

  // Delete actions (Papers, Batches, or All)
  const executeDelete = async () => {
    if (!deleteTarget) return;

    try {
      if (deleteTarget.type === "paper") {
        const res = await fetch(`${apiBase}/api/delete-paper`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            paperId: deleteTarget.id,
            markaId: user.markaId,
            pin: user.pin
          })
        });
        if (res.ok) {
          setPapers((prev) => prev.filter((p) => p.id !== deleteTarget.id));
        }
      } else if (deleteTarget.type === "all") {
        const res = await fetch(`${apiBase}/api/delete-all-images`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            markaId: user.markaId,
            pin: user.pin
          })
        });
        if (res.ok) {
          // Clear base64 strings locally as well
          setPapers((prev) => prev.map((p) => ({ ...p, imageUrl: "" })));
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setDeleteTarget(null);
    }
  };

  // CSV Generation hook
  const downloadBatchCSV = (bId: string) => {
    const batchPapers = papers.filter((p) => p.batchId === bId && p.status === "complete");
    if (batchPapers.length === 0) {
      alert("No graded papers available in this batch yet.");
      return;
    }

    const headers = "Filename,Student Name,Score,Correct,Wrong,Blank,Percentage,Confidence\n";
    const rows = batchPapers
      .map((p) =>
        `"${p.filename}","${p.studentName}",${p.score},${p.correctCount},${p.wrongCount},${p.blankCount},${p.percentage}%,${Math.round(p.confidence * 100)}%`
      )
      .join("\n");

    const file = new Blob([headers + rows], { type: "text/csv" });
    const element = document.createElement("a");
    element.href = URL.createObjectURL(file);
    element.download = `marka_results_batch_${bId}.csv`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  // Filter papers for Screen 11: Gallery
  const filteredPapers = papers.filter((p) => {
    const matchSearch =
      p.studentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.filename.toLowerCase().includes(searchQuery.toLowerCase());

    const batch = batches.find((b) => b.id === p.batchId);
    const matchSubject = subjectFilter === "All" || (batch && batch.subject === subjectFilter);

    return matchSearch && matchSubject;
  });

  if (sortOrder === "oldest") {
    filteredPapers.sort((a, b) => new Date(a.gradedAt).getTime() - new Date(b.gradedAt).getTime());
  } else {
    filteredPapers.sort((a, b) => new Date(b.gradedAt).getTime() - new Date(a.gradedAt).getTime());
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      {/* Mini App Top Header */}
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex flex-col md:flex-row justify-between items-center gap-4 sticky top-0 z-20 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-[#3B0042] flex items-center justify-center text-white font-extrabold text-lg shadow">
            M
          </div>
          <div>
            <h1 className="text-lg font-black text-[#3B0042] tracking-wider uppercase">MARKA</h1>
            <p className="text-[10px] text-gray-400 font-bold uppercase font-mono">
              CREDENTIAL ID: <span className="text-purple-950 font-black">{user.markaId}</span>
            </p>
          </div>
        </div>

        {/* Action tabs bar */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setCurrentView("dashboard")}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              currentView === "dashboard"
                ? "bg-[#3B0042] text-white shadow"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => {
              setNewBatchTitle("");
              setQuestionsCount(20);
              setCurrentView("builder");
            }}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              currentView === "builder"
                ? "bg-[#3B0042] text-white shadow"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            New Exam Sheet
          </button>
          <button
            onClick={() => setCurrentView("gallery")}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              currentView === "gallery"
                ? "bg-[#3B0042] text-white shadow"
                : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            OMR Library
          </button>
          <button
            onClick={onLogout}
            className="px-4 py-2 rounded-xl text-xs font-bold text-red-600 hover:bg-red-50 transition-all border border-transparent hover:border-red-100"
          >
            Log Out
          </button>
        </div>
      </header>

      {/* Main Body content wrapper */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">
        <AnimatePresence mode="wait">
          {/* SCREEN 4: DASHBOARD */}
          {currentView === "dashboard" && (
            <motion.div
              key="dashboard-view"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="space-y-8"
            >
              {/* Warnings permanent deletion alert */}
              <div className="bg-amber-50 border border-amber-200 p-4 rounded-2xl flex flex-col md:flex-row justify-between items-center gap-4 text-amber-950 text-xs font-semibold">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                  <span>
                    <strong>Caution:</strong> To protect school server storage, original paper images will be
                    automatically cleared in <strong className="text-amber-600">6 Days</strong>. Scores remain forever.
                  </span>
                </div>
                <button
                  onClick={() => setDeleteTarget({ type: "all" })}
                  className="px-3 py-1.5 bg-amber-600/10 hover:bg-amber-600 text-amber-950 hover:text-white rounded-lg transition-all"
                >
                  Clear images now
                </button>
              </div>

              {/* Status metrics grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Remaining Credits Card */}
                <div className="bg-white p-6 rounded-2xl border border-gray-150 shadow-sm flex flex-col justify-between space-y-4">
                  <div className="flex justify-between items-start">
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block">
                      REMAINING CREDITS
                    </span>
                    <div className="p-2 bg-purple-50 text-[#3B0042] rounded-xl">
                      <Coins className="w-5 h-5" />
                    </div>
                  </div>
                  <div>
                    <span className="text-3xl font-black text-purple-950 block">{credits} Credits</span>
                    <span className="text-[10px] text-gray-400 font-semibold block mt-1">
                      1 Credit used per successfully graded exam paper
                    </span>
                  </div>
                  <a
                    href="/"
                    className="w-full text-center py-2.5 rounded-xl bg-purple-50 text-[#3B0042] font-bold text-xs hover:bg-[#3B0042] hover:text-white transition-all block"
                  >
                    Buy more credits
                  </a>
                </div>

                {/* Storage space indicator */}
                <div className="bg-white p-6 rounded-2xl border border-gray-150 shadow-sm flex flex-col justify-between space-y-4">
                  <div className="flex justify-between items-start">
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block">
                      STORAGE ALLOCATION
                    </span>
                    <div className="p-2 bg-purple-50 text-[#3B0042] rounded-xl">
                      <HardDrive className="w-5 h-5" />
                    </div>
                  </div>
                  <div>
                    <span className="text-2xl font-black text-gray-800 block">32.8 MB / 500 MB Used</span>
                    <div className="w-full bg-gray-100 rounded-full h-2 mt-2">
                      <div className="bg-[#3B0042] h-2 rounded-full" style={{ width: "8.5%" }}></div>
                    </div>
                  </div>
                  <button
                    onClick={() => setDeleteTarget({ type: "all" })}
                    className="w-full text-center py-2.5 rounded-xl border border-gray-200 hover:bg-gray-50 text-gray-600 font-bold text-xs transition-all"
                  >
                    Delete original images
                  </button>
                </div>

                {/* Quick launch card */}
                <div className="bg-[#3B0042] text-white p-6 rounded-2xl flex flex-col justify-between shadow-lg relative overflow-hidden">
                  <div className="absolute -right-12 -bottom-12 w-32 h-32 bg-white/5 rounded-full"></div>
                  <div className="space-y-2">
                    <h2 className="text-lg font-bold">Start Grading Sheet</h2>
                    <p className="text-xs text-purple-200 leading-normal">
                      Establish an Answer Key, upload photo sheets, and see instant grades.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setNewBatchTitle("");
                      setQuestionsCount(20);
                      setCurrentView("builder");
                    }}
                    className="w-full py-3 bg-white text-[#3B0042] hover:bg-amber-400 hover:text-[#3B0042] font-extrabold text-xs rounded-xl transition-all shadow mt-4 flex items-center justify-center gap-2"
                  >
                    <PlusCircle className="w-4 h-4" />
                    Start Marking Now
                  </button>
                </div>
              </div>

              {/* Recent markings table and preview section */}
              <div className="bg-white rounded-2xl border border-gray-150 p-6 space-y-6 shadow-sm">
                <div className="flex justify-between items-center">
                  <h3 className="font-extrabold text-gray-900 text-sm flex items-center gap-2">
                    <History className="w-4 h-4 text-purple-600" />
                    Recent Exam Markings
                  </h3>
                </div>

                {batches.length === 0 ? (
                  <div className="text-center py-16 space-y-4">
                    <div className="w-16 h-16 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto">
                      <ClipboardList className="w-8 h-8" />
                    </div>
                    <h4 className="text-sm font-bold text-gray-800">No papers marked yet</h4>
                    <p className="text-xs text-gray-500 max-w-xs mx-auto">
                      Create an exam sheet key and upload files to see grading diagnostics here.
                    </p>
                    <button
                      onClick={() => setCurrentView("builder")}
                      className="px-5 py-2.5 bg-[#3B0042] hover:bg-[#2c0032] text-white text-xs font-bold rounded-xl transition-all"
                    >
                      Mark Your First Paper
                    </button>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-gray-100 text-gray-400 font-bold uppercase tracking-wider">
                          <th className="pb-3 font-semibold">Exam Title</th>
                          <th className="pb-3 font-semibold">Subject</th>
                          <th className="pb-3 font-semibold">Total Scanned</th>
                          <th className="pb-3 font-semibold">Status</th>
                          <th className="pb-3 font-semibold">Date Created</th>
                          <th className="pb-3 text-right font-semibold">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {batches.map((b) => (
                          <tr key={b.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="py-4 font-bold text-purple-950">{b.title}</td>
                            <td className="py-4">
                              <span className="px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 text-[10px] font-bold">
                                {b.subject}
                              </span>
                            </td>
                            <td className="py-4">
                              <span className="font-bold text-gray-800">{b.processedCount} processed</span>
                              {b.rejectedCount > 0 && (
                                <span className="text-red-500 ml-2">({b.rejectedCount} blurry)</span>
                              )}
                            </td>
                            <td className="py-4 font-medium text-green-600">Complete</td>
                            <td className="py-4 text-gray-400 font-mono">
                              {new Date(b.date).toLocaleDateString()}
                            </td>
                            <td className="py-4 text-right space-x-2">
                              <button
                                onClick={() => {
                                  setSelectedBatchId(b.id);
                                  setCurrentView("results");
                                }}
                                className="px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-[#3B0042] font-bold rounded-lg transition-all"
                              >
                                View results
                              </button>
                              <button
                                onClick={() => downloadBatchCSV(b.id)}
                                className="px-2.5 py-1.5 border border-gray-200 hover:bg-gray-50 text-gray-500 rounded-lg transition-all"
                                title="Download CSV"
                              >
                                <Download className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* SCREEN 7: ANSWER KEY BUILDER */}
          {currentView === "builder" && (
            <motion.div
              key="builder-view"
              initial={{ opacity: 0, scale: 0.99 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.99 }}
              transition={{ duration: 0.15 }}
              className="max-w-4xl mx-auto space-y-8"
            >
              <div className="flex justify-between items-center border-b pb-4">
                <div>
                  <h2 className="text-xl font-black text-[#3B0042]">Create Objective Answer Key</h2>
                  <p className="text-xs text-gray-400">
                    Draft parameters for the OMR scanning. Arrow keys up/down changes question. Press A/B/C/D key to mark option!
                  </p>
                </div>
                <button
                  onClick={() => setCurrentView("dashboard")}
                  className="px-4 py-2 border border-gray-200 hover:bg-gray-50 text-gray-600 text-xs font-bold rounded-xl"
                >
                  Cancel
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
                {/* Control Options */}
                <div className="md:col-span-5 space-y-6">
                  <div className="bg-white p-6 rounded-2xl border border-gray-150 space-y-4 shadow-sm">
                    <h3 className="text-xs font-extrabold text-[#3B0042] uppercase tracking-wider">
                      Exam Information
                    </h3>

                    <div className="space-y-2">
                      <label className="block text-xs font-bold text-gray-600 uppercase">Exam Title</label>
                      <input
                        type="text"
                        placeholder="e.g. Biology Term 1"
                        value={newBatchTitle}
                        onChange={(e) => setNewBatchTitle(e.target.value)}
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] text-sm font-bold"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label className="block text-xs font-bold text-gray-600 uppercase">Subject</label>
                        <select
                          value={newBatchSubject}
                          onChange={(e) => setNewBatchSubject(e.target.value)}
                          className="w-full px-3 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] text-sm bg-white"
                        >
                          <option>Biology</option>
                          <option>Physics</option>
                          <option>Mathematics</option>
                          <option>Chemistry</option>
                          <option>English</option>
                        </select>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-xs font-bold text-gray-600 uppercase">Total Questions</label>
                        <select
                          value={questionsCount}
                          onChange={(e) => setQuestionsCount(parseInt(e.target.value, 10))}
                          className="w-full px-3 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-[#3B0042] text-sm bg-white font-bold"
                        >
                          <option value={10}>10 Questions</option>
                          <option value={20}>20 Questions</option>
                          <option value={30}>30 Questions</option>
                          <option value={50}>50 Questions</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Expandable Custom Grading Structure */}
                  <div className="bg-white border border-gray-150 rounded-2xl overflow-hidden shadow-sm">
                    <button
                      type="button"
                      onClick={() => setBonusEnabled(!bonusEnabled)}
                      className="w-full p-4 flex justify-between items-center bg-gray-50/50 border-b font-extrabold text-xs text-purple-950 uppercase"
                    >
                      <span>Custom Grading Settings</span>
                      <span className="text-[10px] text-purple-600 lowercase bg-purple-50 px-2 py-0.5 rounded">
                        {bonusEnabled ? "enabled" : "disabled"}
                      </span>
                    </button>

                    {bonusEnabled && (
                      <div className="p-6 space-y-4">
                        <div className="space-y-2">
                          <div className="flex justify-between items-center text-xs">
                            <label className="font-bold text-gray-600 uppercase">Bonus Marks</label>
                            <span className="font-bold text-[#3B0042]">+{bonusMarks} pts</span>
                          </div>
                          <input
                            type="range"
                            min={0}
                            max={5}
                            step={0.5}
                            value={bonusMarks}
                            onChange={(e) => setBonusMarks(parseFloat(e.target.value))}
                            className="w-full accent-[#3B0042]"
                          />
                          <span className="block text-[10px] text-gray-400">
                            Points added unconditionally for students with non-zero grades.
                          </span>
                        </div>

                        <div className="space-y-2">
                          <div className="flex justify-between items-center text-xs">
                            <label className="font-bold text-gray-600 uppercase">Negative Marking Penalty</label>
                            <span className="font-bold text-red-600">-{negativeMarking} pts</span>
                          </div>
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.25}
                            value={negativeMarking}
                            onChange={(e) => setNegativeMarking(parseFloat(e.target.value))}
                            className="w-full accent-red-600"
                          />
                          <span className="block text-[10px] text-gray-400">
                            Penalty subtracted for each incorrect answer bubble.
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={handleCreateBatch}
                    className="w-full py-4 bg-[#3B0042] hover:bg-[#2c0032] text-white font-extrabold text-sm rounded-xl transition-all shadow-md active:scale-95 flex items-center justify-center gap-2"
                  >
                    Generate Sheet Layout Key
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>

                {/* Question builder grid with Arrow key focus indicators */}
                <div className="md:col-span-7 bg-white p-6 rounded-2xl border border-gray-150 shadow-sm space-y-6">
                  <h3 className="text-xs font-extrabold text-gray-400 uppercase tracking-widest">
                    Options Key Builder
                  </h3>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[420px] overflow-y-auto pr-2">
                    {Array.from({ length: questionsCount }).map((_, idx) => {
                      const qNum = idx + 1;
                      const activeOpt = answerKey[qNum] || "A";

                      return (
                        <div
                          key={qNum}
                          onClick={() => setActiveBuilderQ(qNum)}
                          className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all ${
                            activeBuilderQ === qNum
                              ? "border-[#3B0042] bg-purple-50/20 ring-2 ring-[#3B0042]/10"
                              : "border-gray-100"
                          }`}
                        >
                          <span className="font-mono text-xs font-bold text-gray-400">
                            Q{String(qNum).padStart(2, "0")}
                          </span>

                          <div className="flex items-center gap-2">
                            {["A", "B", "C", "D"].slice(0, optionsCount).map((opt) => (
                              <button
                                key={opt}
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setAnswerKey((prev) => ({ ...prev, [qNum]: opt }));
                                }}
                                className={`w-7 h-7 rounded-full text-xs font-bold transition-all ${
                                  activeOpt === opt
                                    ? "bg-[#3B0042] text-white"
                                    : "bg-gray-50 text-gray-500 hover:bg-gray-100"
                                }`}
                              >
                                {opt}
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* SCREEN 5 & 6: UPLOAD ZONE & BATCH PROCESSING QUEUE */}
          {currentView === "upload" && (
            <motion.div
              key="upload-view"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="space-y-8"
            >
              <div className="flex flex-col md:flex-row justify-between items-start gap-4 border-b pb-4">
                <div>
                  <h2 className="text-xl font-black text-purple-950">
                    Grade Scanning Session: {batches.find((b) => b.id === selectedBatchId)?.title}
                  </h2>
                  <p className="text-xs text-gray-400">
                    Maximum 50 image papers per batch. Drag sheets or trigger webcam scanning below.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={startCamera}
                    className="px-4 py-2 bg-purple-50 hover:bg-purple-100 text-[#3B0042] text-xs font-bold rounded-xl transition-all flex items-center gap-2 border border-purple-100"
                  >
                    <Camera className="w-4 h-4" />
                    Webcam Scan
                  </button>
                  <button
                    onClick={() => {
                      setUploadQueue([]);
                      setCurrentView("dashboard");
                    }}
                    className="px-4 py-2 border border-gray-200 hover:bg-gray-50 text-gray-500 text-xs font-bold rounded-xl"
                  >
                    Cancel Session
                  </button>
                </div>
              </div>

              {/* Blurry hold overlay popup - non-blocking error handler */}
              <AnimatePresence>
                {blurryHold && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="bg-amber-50 border border-amber-200 p-6 rounded-2xl shadow-lg space-y-4 max-w-lg mx-auto"
                  >
                    <div className="flex gap-4 items-start">
                      <div className="p-2.5 bg-amber-100 text-amber-700 rounded-full">
                        <BadgeAlert className="w-6 h-6 animate-pulse" />
                      </div>
                      <div className="space-y-1">
                        <h4 className="font-extrabold text-amber-950 text-sm">
                          Paper scan detected as blurry!
                        </h4>
                        <p className="text-xs text-amber-800 leading-normal">
                          The filename <strong>{blurryHold.filename}</strong> has poor visual readability.
                          You can replace the photo, skip, or continue processing other sheets.
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-3 pt-2 justify-end">
                      <button
                        onClick={handleBlurrySkip}
                        className="px-4 py-2 text-xs font-bold text-amber-900 hover:bg-amber-100 rounded-xl"
                      >
                        Skip paper
                      </button>
                      <label className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-extrabold rounded-xl cursor-pointer">
                        Replace and Retry
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleBlurryReplace}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Upload Drop Zone Card */}
              {uploadQueue.length === 0 && (
                <div
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  className="bg-white border-2 border-dashed border-gray-200 hover:border-[#3B0042] rounded-3xl p-12 text-center space-y-6 transition-all shadow-sm cursor-pointer relative"
                >
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={handleFileChange}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                  <div className="w-16 h-16 bg-purple-50 text-[#3B0042] rounded-full flex items-center justify-center mx-auto shadow-inner">
                    <Upload className="w-8 h-8" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="text-lg font-black text-gray-900">Drop sheets here or click to select</h3>
                    <p className="text-xs text-gray-400 max-w-sm mx-auto leading-normal">
                      We support high-speed batching of up to <strong>50 files</strong>. Paste clipboard clips or connect scanner feeds.
                    </p>
                  </div>
                  <div className="text-xs text-[#3B0042] font-bold">Max upload counts and compression indicators active</div>
                </div>
              )}

              {/* Thumbnail grid list with progress statuses */}
              {uploadQueue.length > 0 && (
                <div className="space-y-6 bg-white p-6 rounded-2xl border border-gray-150 shadow-sm">
                  <div className="flex justify-between items-center pb-4 border-b">
                    <div>
                      <span className="text-xs font-bold text-gray-400 uppercase">BATCH QUEUE</span>
                      <h3 className="text-sm font-black text-gray-800 mt-1">
                        {uploadQueue.filter((q) => q.status === "complete").length} / {uploadQueue.length} sheets graded
                      </h3>
                    </div>

                    <button
                      onClick={runBatchProcessing}
                      disabled={isUploadingBatch || uploadQueue.every((q) => q.status === "complete")}
                      className="px-6 py-3 bg-[#3B0042] hover:bg-[#2c0032] disabled:bg-gray-200 text-white font-extrabold text-xs rounded-xl shadow-md transition-all flex items-center gap-2"
                    >
                      {isUploadingBatch ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4" />
                          Start Grading Batch
                        </>
                      )}
                    </button>
                  </div>

                  {/* Progressive upload bar */}
                  <div className="w-full bg-gray-50 rounded-full h-3 border overflow-hidden">
                    <div
                      className="bg-green-500 h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${
                          (uploadQueue.filter((q) => q.status === "complete").length / uploadQueue.length) * 100
                        }%`
                      }}
                    ></div>
                  </div>

                  {/* Gallery item containers */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    {uploadQueue.map((item, idx) => {
                      let ringColor = "border-gray-150";
                      let badgeColor = "bg-gray-100 text-gray-600";
                      let label = "Queued";

                      if (item.status === "uploading") {
                        ringColor = "border-blue-400 ring-2 ring-blue-50";
                        badgeColor = "bg-blue-50 text-blue-600";
                        label = "Uploading";
                      } else if (item.status === "grading") {
                        ringColor = "border-purple-400 ring-2 ring-purple-50";
                        badgeColor = "bg-purple-50 text-purple-600";
                        label = "Grading";
                      } else if (item.status === "complete") {
                        ringColor = "border-green-400 ring-2 ring-green-50";
                        badgeColor = "bg-green-50 text-green-600";
                        label = `Pass (${item.paper?.score}/${item.paper?.maxScore})`;
                      } else if (item.status === "rejected") {
                        ringColor = "border-red-400 ring-2 ring-red-50";
                        badgeColor = "bg-red-50 text-red-600";
                        label = "Rejected";
                      }

                      return (
                        <div
                          key={item.id}
                          className={`border rounded-xl p-2 bg-gray-50 flex flex-col justify-between space-y-2 relative overflow-hidden transition-all ${ringColor}`}
                        >
                          {/* Image preview background */}
                          <div className="w-full h-24 rounded-lg bg-gray-200 overflow-hidden relative">
                            <img
                              src={item.base64}
                              alt="Scanned sheet"
                              className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-black/5"></div>
                          </div>

                          <div className="space-y-1 text-center">
                            <span className="block text-[10px] font-bold text-gray-500 truncate px-1">
                              {item.filename}
                            </span>
                            <span className={`inline-block px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider ${badgeColor}`}>
                              {label}
                            </span>
                          </div>

                          {/* Quick single-file retry or skip action overlay if failed */}
                          {item.status === "rejected" && (
                            <div className="text-center pt-1 border-t border-red-100 flex justify-around">
                              <button
                                onClick={() => {
                                  setBlurryHold({
                                    id: item.id,
                                    filename: item.filename,
                                    base64: item.base64
                                  });
                                }}
                                className="text-[10px] font-bold text-purple-700 hover:underline"
                              >
                                Replace
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {uploadQueue.every((q) => q.status === "complete") && (
                    <div className="p-4 bg-green-50 border border-green-200 rounded-xl flex justify-between items-center gap-4 text-green-900 text-xs font-semibold">
                      <span>✓ Completed grading of all objective papers!</span>
                      <button
                        onClick={() => {
                          setCurrentView("results");
                        }}
                        className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-all"
                      >
                        View Results Panel
                      </button>
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          )}

          {/* SCREEN 9: RESULTS GALLERY */}
          {currentView === "results" && (
            <motion.div
              key="results-view"
              initial={{ opacity: 0, scale: 0.99 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.99 }}
              transition={{ duration: 0.15 }}
              className="space-y-8"
            >
              <div className="flex flex-col md:flex-row justify-between items-start gap-4 border-b pb-4">
                <div>
                  <h2 className="text-xl font-black text-purple-950">
                    Graded Diagnostic Scores: {batches.find((b) => b.id === selectedBatchId)?.title}
                  </h2>
                  <p className="text-xs text-gray-400">
                    Student metrics scanned from OMR bubble cards. Export to excel sheet or CSV with one click.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => downloadBatchCSV(selectedBatchId || "")}
                    className="px-4 py-2 bg-[#3B0042] hover:bg-[#2c0032] text-white text-xs font-bold rounded-xl transition-all flex items-center gap-2 shadow"
                  >
                    <Download className="w-4 h-4" />
                    Export CSV results
                  </button>
                  <button
                    onClick={() => setCurrentView("dashboard")}
                    className="px-4 py-2 border border-gray-200 hover:bg-gray-50 text-gray-500 text-xs font-bold rounded-xl"
                  >
                    Back to dashboard
                  </button>
                </div>
              </div>

              {/* Graded student cards gallery */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {papers
                  .filter((p) => p.batchId === selectedBatchId)
                  .map((p) => (
                    <div
                      key={p.id}
                      className="bg-white border border-gray-150 rounded-2xl p-5 shadow-sm hover:border-[#3B0042] transition-all flex flex-col justify-between space-y-4"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-purple-50 flex items-center justify-center text-[#3B0042]">
                            <User className="w-4 h-4" />
                          </div>
                          <div>
                            <span className="block font-bold text-purple-950 text-sm truncate max-w-[120px]">
                              {p.studentName}
                            </span>
                            <span className="block text-[10px] text-gray-400 font-mono">
                              {p.filename}
                            </span>
                          </div>
                        </div>

                        <span className="inline-block px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-green-50 text-green-600">
                          {p.status}
                        </span>
                      </div>

                      <div className="bg-gray-50 p-4 rounded-xl text-center space-y-1">
                        <span className="text-xs font-bold text-gray-400 block uppercase">
                          SCORE GRADED
                        </span>
                        <span className="text-3xl font-black text-purple-950 block">
                          {p.score} / {p.maxScore}
                        </span>
                        <span className="text-[10px] text-gray-400 font-bold block">
                          {p.percentage}% Accuracy • {Math.round(p.confidence * 100)}% Confidence
                        </span>
                      </div>

                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setActiveResultsPaper(p);
                          }}
                          className="flex-1 py-2 bg-purple-50 hover:bg-[#3B0042] hover:text-white text-[#3B0042] font-bold text-xs rounded-lg transition-all"
                        >
                          View sheet
                        </button>
                        <button
                          onClick={() => setDeleteTarget({ type: "paper", id: p.id })}
                          className="p-2 border border-red-100 hover:bg-red-50 text-red-600 rounded-lg transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
              </div>

              {/* Diagnostic visual sheet overlay modal */}
              <AnimatePresence>
                {activeResultsPaper && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-6 backdrop-blur-sm"
                  >
                    <motion.div
                      initial={{ scale: 0.95 }}
                      animate={{ scale: 1 }}
                      exit={{ scale: 0.95 }}
                      className="bg-white rounded-3xl p-6 md:p-8 max-w-4xl w-full max-h-[90vh] overflow-y-auto space-y-6 relative"
                    >
                      <button
                        onClick={() => setActiveResultsPaper(null)}
                        className="absolute top-6 right-6 p-2 rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-900 transition-all"
                      >
                        <X className="w-6 h-6" />
                      </button>

                      <div className="border-b pb-4">
                        <h3 className="text-lg font-black text-[#3B0042]">
                          Diagnostic Overlay: {activeResultsPaper.studentName}
                        </h3>
                        <p className="text-xs text-gray-400">
                          Individual answers verified by Gemini OMR scanning engine against answer keys.
                        </p>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div>
                          {/* Printable sheet mockup overlay */}
                          <PrintableOMRSheet
                            questionsCount={batches.find((b) => b.id === selectedBatchId)?.questionsCount}
                            optionsCount={batches.find((b) => b.id === selectedBatchId)?.optionsCount}
                            studentName={activeResultsPaper.studentName}
                            markedAnswers={activeResultsPaper.studentAnswers}
                            correctAnswers={batches.find((b) => b.id === selectedBatchId)?.answerKey}
                          />
                        </div>

                        <div className="space-y-6 flex flex-col justify-between">
                          <div className="space-y-4">
                            <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                              Diagnostic Analytics
                            </h4>

                            <div className="grid grid-cols-3 gap-4 text-center">
                              <div className="p-3 bg-green-50 border border-green-100 rounded-xl">
                                <span className="block text-[10px] text-green-700 font-bold uppercase">
                                  Correct
                                </span>
                                <span className="text-lg font-extrabold text-green-900">
                                  {activeResultsPaper.correctCount}
                                </span>
                              </div>
                              <div className="p-3 bg-red-50 border border-red-100 rounded-xl">
                                <span className="block text-[10px] text-red-700 font-bold uppercase">
                                  Incorrect
                                </span>
                                <span className="text-lg font-extrabold text-red-900">
                                  {activeResultsPaper.wrongCount}
                                </span>
                              </div>
                              <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl">
                                <span className="block text-[10px] text-amber-700 font-bold uppercase">
                                  Blank
                                </span>
                                <span className="text-lg font-extrabold text-amber-900">
                                  {activeResultsPaper.blankCount}
                                </span>
                              </div>
                            </div>

                            {activeResultsPaper.imageUrl && (
                              <div className="border rounded-2xl overflow-hidden bg-gray-100 p-2">
                                <span className="block text-[9px] font-bold text-gray-400 uppercase mb-1">
                                  Uploaded Raw Sheet
                                </span>
                                <img
                                  src={activeResultsPaper.imageUrl}
                                  alt="raw OMR sheet scanned upload"
                                  className="w-full h-40 object-contain rounded-lg"
                                />
                              </div>
                            )}
                          </div>

                          <div className="space-y-3">
                            <button
                              onClick={() => window.print()}
                              className="w-full py-3 bg-[#3B0042] hover:bg-[#2c0032] text-white font-extrabold text-xs rounded-xl transition-all shadow flex items-center justify-center gap-2"
                            >
                              Print Candidate Diagnostic Card
                            </button>
                            <button
                              onClick={() => setActiveResultsPaper(null)}
                              className="w-full py-3 border border-gray-200 text-gray-700 hover:bg-gray-50 text-xs font-bold rounded-xl transition-all"
                            >
                              Close Diagnostic View
                            </button>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}

          {/* SCREEN 11: GALLERY */}
          {currentView === "gallery" && (
            <motion.div
              key="gallery-view"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="space-y-8"
            >
              <div className="flex flex-col md:flex-row justify-between items-start gap-4 border-b pb-4">
                <div>
                  <h2 className="text-xl font-black text-purple-950">OMR Library</h2>
                  <p className="text-xs text-gray-400">
                    Browse all historically scanned student papers. Fulfills the Google Photos-like responsive grid.
                  </p>
                </div>
                <button
                  onClick={() => {
                    setNewBatchTitle("");
                    setQuestionsCount(20);
                    setCurrentView("builder");
                  }}
                  className="px-5 py-2.5 bg-[#3B0042] hover:bg-[#2c0032] text-white text-xs font-bold rounded-xl transition-all shadow flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Grade New Sheets
                </button>
              </div>

              {/* Filters toolbar */}
              <div className="bg-white p-4 rounded-2xl border border-gray-150 flex flex-col md:flex-row justify-between gap-4 shadow-sm text-xs font-semibold">
                <div className="flex flex-1 items-center gap-3 bg-gray-50 border px-3 py-2 rounded-xl">
                  <Search className="w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search candidate name or filename..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-transparent border-none outline-none flex-1 text-xs"
                  />
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-purple-600" />
                    <span>Subject:</span>
                  </div>
                  <select
                    value={subjectFilter}
                    onChange={(e) => setSubjectFilter(e.target.value)}
                    className="border px-3 py-2 rounded-xl bg-white focus:outline-none focus:border-[#3B0042]"
                  >
                    <option>All</option>
                    <option>Biology</option>
                    <option>Physics</option>
                    <option>Mathematics</option>
                    <option>Chemistry</option>
                    <option>English</option>
                  </select>

                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as any)}
                    className="border px-3 py-2 rounded-xl bg-white focus:outline-none focus:border-[#3B0042]"
                  >
                    <option value="newest">Newest Scanned</option>
                    <option value="oldest">Oldest Scanned</option>
                  </select>
                </div>
              </div>

              {/* Library Grid */}
              {filteredPapers.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-2xl border border-gray-100">
                  <ClipboardList className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                  <h4 className="font-bold text-gray-800">No scanned papers matching query</h4>
                  <p className="text-xs text-gray-400 mt-1">Adjust your filters or start fresh uploads.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
                  {filteredPapers.map((p) => {
                    const batch = batches.find((b) => b.id === p.batchId);

                    return (
                      <div
                        key={p.id}
                        onClick={() => setActiveResultsPaper(p)}
                        className="bg-white border rounded-2xl p-4 shadow-sm hover:border-[#3B0042] transition-all cursor-pointer flex flex-col justify-between space-y-3"
                      >
                        <div className="w-full h-28 bg-gray-100 rounded-xl overflow-hidden relative group">
                          {p.imageUrl ? (
                            <img
                              src={p.imageUrl}
                              alt="raw omr scan preview"
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-xs text-gray-400 font-mono bg-purple-50/50">
                              No image cached
                            </div>
                          )}
                          <div className="absolute inset-0 bg-[#3B0042]/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white">
                            <Maximize2 className="w-5 h-5" />
                          </div>
                        </div>

                        <div>
                          <span className="block font-bold text-purple-950 text-xs truncate">
                            {p.studentName}
                          </span>
                          <span className="block text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-0.5">
                            {batch?.subject || "General"}
                          </span>
                        </div>

                        <div className="flex justify-between items-center pt-2 border-t border-gray-50 text-[10px] font-bold">
                          <span className="text-purple-950">
                            {p.score} / {p.maxScore}
                          </span>
                          <span className="text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full text-[9px]">
                            {p.percentage}%
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* WEBCAM CAMERA MODAL */}
      <AnimatePresence>
        {showCamera && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black z-50 flex flex-col justify-between p-6"
          >
            <div className="flex justify-between items-center text-white">
              <span className="text-xs font-bold uppercase tracking-widest font-mono text-purple-200">
                MARKA WEBCAM OMR SCANNER
              </span>
              <button
                onClick={stopCamera}
                className="p-2 rounded-full hover:bg-white/10 text-white"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="flex-1 flex items-center justify-center max-w-xl mx-auto w-full relative">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                className="w-full h-full object-cover rounded-2xl border-4 border-white/20"
              ></video>
              <div className="absolute border-2 border-amber-400 border-dashed w-72 h-96 rounded-xl pointer-events-none opacity-80 flex items-center justify-center">
                <span className="text-[10px] text-amber-400 font-bold uppercase tracking-widest bg-black/45 px-2 py-1 rounded">
                  Align answer sheet here
                </span>
              </div>
            </div>

            <div className="flex justify-center pb-6">
              <button
                onClick={capturePhoto}
                className="w-16 h-16 rounded-full bg-white border-4 border-gray-300 hover:border-amber-400 transition-all flex items-center justify-center cursor-pointer shadow-lg active:scale-95"
              ></button>
            </div>
            <canvas ref={canvasRef} className="hidden" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* SCREEN 12: DELETE CONFIRMATION MODAL */}
      <AnimatePresence>
        {deleteTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-6 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="bg-white p-6 rounded-2xl shadow-xl max-w-sm w-full space-y-6 text-center"
            >
              <div className="w-12 h-12 bg-red-50 text-red-600 rounded-full flex items-center justify-center mx-auto">
                <Trash2 className="w-6 h-6" />
              </div>

              <div className="space-y-2">
                <h3 className="font-extrabold text-gray-900 text-sm">
                  {deleteTarget.type === "all" ? "Delete All Cached Images?" : "Delete Paper Record?"}
                </h3>
                <p className="text-xs text-gray-500 leading-normal">
                  {deleteTarget.type === "all"
                    ? "This action will permanently reclaim approx. 21.4 MB of server database storage. Graded scores and metadata are unaffected."
                    : "This student record and scored sheet will be deleted permanently. You will not reclaim credits consumed."}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-2">
                <button
                  onClick={() => setDeleteTarget(null)}
                  className="py-3 border border-gray-200 text-gray-600 text-xs font-bold rounded-xl transition-all hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={executeDelete}
                  className="py-3 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-xl transition-all"
                >
                  Confirm Delete
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
