# MARKA 🎯

> **AI-Powered Exam Processing, Computer Vision OMR Scanner & Verified Student Assessment Engine**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-5.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![Supabase](https://img.shields.io/badge/Supabase-Database_%26_Auth-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com/)

---

## 🌟 Overview

**MARKA** bridges the physical and digital gap in education for developing markets and resource-constrained environments. Teachers and school administrators can effortlessly convert plain text exam questions into print-ready **Optical Mark Recognition (OMR) sheets**, scan completed student bubble sheets using any smartphone camera, and automatically generate itemized, tamper-proof **Assessment Receipts** in seconds.

Whether operating in offline classrooms or modern digital institutions, MARKA eliminates manual grading fatigue, guarantees high computer vision scanning accuracy, and delivers actionable learning analytics for educators.

---

## ✨ Key Features

### 📄 1. Automated OMR Sheet Generator
- **Dynamic Bubble Grid Engine**: Automatically calculates spacing, column layouts, and printable boundaries for 20, 40, 60, or 100-question multiple-choice exams.
- **Fiducial Alignment Markers**: Embedded high-precision corner targets ensure robust perspective correction regardless of camera angle.
- **QR-Coded Verification**: Unique QR identifiers on every sheet bind student index, subject code, and exam variant to prevent grading mix-ups.

### 📷 2. High-Precision Computer Vision Scanner
- **Perspective & Warp Correction**: Detects page boundaries and corrects rotational tilt, camera lens distortion, and uneven lighting.
- **Adaptive Thresholding**: Accurately scores pencil marks, pen fills, crosses, or light bubble shading.
- **Batch Processing API**: Upload multiple sheet scans simultaneously with instant queue processing and real-time status updates.

### 🧾 3. Student Assessment Receipt Engine
- **Printable Micro-Receipts**: Compact, ink-saver micro-receipts (up to 10 receipts per A4 sheet) for physical distribution to students & parents.
- **Itemized Score Breakdown**: Shows total score, percentage grade, question-by-question breakdown, and security verification hashes.

### 🏫 4. Full-Stack School Management Portal
- **Teacher Dashboard**: Create exams, review pending upload queues, inspect flagged sheets, and export gradebooks to CSV/PDF.
- **Supabase Authentication**: Role-based authentication for school owners, principal admins, and subject teachers.
- **Flexible Billing Integration**: Integrated with **Monnify** and **Paystack** for pay-as-you-go credit top-ups tailored for local school budgets.

---

## 🏗️ Architecture & Tech Stack

```
                     ┌──────────────────────────────────────────┐
                     │          React + Vite Frontend           │
                     │   (Dashboard, OMR Builder, Auth UI)      │
                     └────────────────────┬─────────────────────┘
                                          │  REST / Auth Tokens
                                          ▼
                     ┌──────────────────────────────────────────┐
                     │          FastAPI Server (Python)         │
                     │  - REST Endpoints & Webhook Handlers     │
                     │  - Authentication & JWT Middleware      │
                     └───────┬──────────────────────────┬───────┘
                             │                          │
              ┌──────────────▼──────────────┐  ┌────────▼──────────────┐
              │  Computer Vision Core       │  │  PDF & OMR Generator   │
              │  - OpenCV (Fiducial Align)  │  │  - ReportLab           │
              │  - NumPy Contour Analysis   │  │  - QR Code Generation  │
              └─────────────────────────────┘  └───────────────────────┘
                             │                          │
                             └──────────────┬───────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────┐
                     │        Supabase PostgreSQL DB            │
                     │   (User Profiles, Exams, Scans, Logs)   │
                     └──────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
MARKA/
├── api/                         # FastAPI Backend Server
│   ├── server.py                # REST API routes & app entry point
│   ├── auth.py                  # Supabase & JWT auth utilities
│   ├── database.py              # Database access layer
│   └── test_server.py           # Backend Integration Tests
├── omr_generator.py             # PDF Layout & OMR Sheet Generator
├── omr_scanner.py               # OpenCV Computer Vision Scoring Engine
├── receipt_generator.py         # Printable Assessment Receipt PDF Engine
├── src/                         # Core Python models & layout engine
│   ├── models.py                # Pydantic data schemas
│   ├── parser.py                # Exam text parser
│   └── layout_engine.py         # ReportLab layout engine
├── demo_site/                   # Production React + Vite Web App
│   ├── src/                     # UI Components (Dashboard, Builder, Upload)
│   ├── public/                  # Static assets & demo sheets
│   └── package.json             # Frontend dependencies
├── samples/                     # Clean sample exam text files for testing
│   ├── government_exam.txt
│   └── ss2_civic_exam.txt
├── tests/                       # Unit Test Suite
│   ├── test_parser.py           # Text parser tests
│   ├── test_layout.py           # PDF layout engine tests
│   ├── test_scanner.py          # OpenCV fiducial detection tests
│   └── test_flowable.py         # PDF flowable component tests
├── migrations/                  # PostgreSQL Schema & Supabase Migrations
├── requirements.txt             # Python Backend Dependencies
└── render.yaml                  # One-Click Deployment Configuration
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python**: `3.10+` (Python 3.12 recommended)
- **Node.js**: `v18+` and `npm`

---

### 1. Backend Setup

```bash
# Clone the repository
git clone git@github.com:dafedescribe/MARKA.git
cd MARKA

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your Supabase & Secret keys

# Run unit tests
python -m unittest discover -s tests -p "test_*.py"

# Start the FastAPI server
uvicorn api.server:app --reload --port 8000
```

The API documentation will be available locally at `http://localhost:8000/docs`.

---

### 2. Frontend Setup

```bash
# Navigate to the frontend app
cd demo_site

# Install dependencies
npm install

# Setup environment variables
cp .env.example .env.local

# Start dev server
npm run dev
```

Open `http://localhost:5173` in your browser to view the MARKA interactive portal.

---

## 🧪 Running Tests

To verify that all core engine modules pass integration testing:

```bash
# From the repository root with active virtualenv:
python -m unittest tests/test_parser.py tests/test_layout.py tests/test_scanner.py tests/test_flowable.py
```

Expected output:
```text
...
----------------------------------------------------------------------
Ran 3 tests in 0.20s

OK
```

---

## 🚢 Deployment

- **Backend**: Configured for continuous deployment on [Render](https://render.com) using `render.yaml`.
- **Frontend**: Single-command deploy to [Vercel](https://vercel.com) or Netlify (`cd demo_site && npm run build`).

---

## 🔒 Security & Privacy

MARKA is built with security first:
- All sensitive API credentials (`SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET`, `PAYSTACK_SECRET_KEY`) are loaded strictly via environment variables.
- Raw scan uploads are sanitized and authenticated via Supabase Row Level Security (RLS).

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.

---

<div align="center">
  <sub>Built with ❤️ for global education equality during Hackathon 2026.</sub>
</div>
