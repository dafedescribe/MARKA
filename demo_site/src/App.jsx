import { useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || ''

function App() {
  const [mode, setMode] = useState(null) // 'demo' | 'scan' | 'answer-key'
  const [examCode, setExamCode] = useState('')
  const [files, setFiles] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  // Answer key state
  const [numQuestions, setNumQuestions] = useState(100)
  const [numChoices, setNumChoices] = useState(5)
  const [answerKey, setAnswerKey] = useState({})
  const [keySubmitted, setKeySubmitted] = useState(null)

  const handleFileChange = (e) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files))
      setResults(null)
      setError(null)
    }
  }

  const handleScan = async () => {
    if (!files.length || !examCode.trim()) return
    setIsProcessing(true)
    setError(null)

    const formData = new FormData()
    formData.append('exam_code', examCode.trim().toUpperCase())

    if (files.length === 1) {
      formData.append('image', files[0])
      try {
        const res = await fetch(`${API_URL}/scan`, { method: 'POST', body: formData })
        if (!res.ok) {
          const err = await res.json()
          throw new Error(err.detail || 'Scan failed')
        }
        const data = await res.json()
        setResults({ type: 'single', data })
      } catch (err) {
        setError(err.message)
      }
    } else {
      files.forEach(f => formData.append('images', f))
      try {
        const res = await fetch(`${API_URL}/batch-scan`, { method: 'POST', body: formData })
        if (!res.ok) {
          const err = await res.json()
          throw new Error(err.detail || 'Batch scan failed')
        }
        const data = await res.json()
        setResults({ type: 'batch', data })
      } catch (err) {
        setError(err.message)
      }
    }
    setIsProcessing(false)
  }

  const handleSubmitKey = async () => {
    if (!examCode.trim() || Object.keys(answerKey).length === 0) return
    setIsProcessing(true)
    setError(null)

    const formData = new FormData()
    formData.append('exam_code', examCode.trim().toUpperCase())
    formData.append('answers', JSON.stringify(answerKey))

    try {
      const res = await fetch(`${API_URL}/answer-key`, { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to submit answer key')
      }
      const data = await res.json()
      setKeySubmitted(data)
    } catch (err) {
      setError(err.message)
    }
    setIsProcessing(false)
  }

  const reset = () => {
    setMode(null)
    setExamCode('')
    setFiles([])
    setResults(null)
    setError(null)
    setKeySubmitted(null)
    setAnswerKey({})
  }

  const choices = Array.from({ length: numChoices }, (_, i) => String.fromCharCode(65 + i))

  // ── Landing ──
  if (!mode) {
    return (
      <div className="container">
        <header className="header">
          <h1>MARKA</h1>
          <p>Instant exam grading from a phone photo.</p>
        </header>
        <div className="path-chooser">
          <div className="path-card" onClick={() => setMode('demo')}>
            <h2>Try the Demo</h2>
            <p>Download a sample exam, fill it in, and see instant grading.</p>
            <span className="path-tag free">Free</span>
          </div>
          <div className="path-card" onClick={() => setMode('scan')}>
            <h2>Scan & Grade</h2>
            <p>Upload student answer sheets for your exam. Bulk uploads supported.</p>
            <span className="path-tag paid">School Access</span>
          </div>
          <div className="path-card" onClick={() => setMode('answer-key')}>
            <h2>Submit Answer Key</h2>
            <p>Provide the correct answers to grade all previously scanned sheets.</p>
            <span className="path-tag paid">School Access</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <header className="header">
        <h1>MARKA</h1>
        <p>Instant exam grading from a phone photo.</p>
        <button className="back-link" onClick={reset}>← Back</button>
      </header>

      <main className="main-content">
        {/* ── DEMO MODE ── */}
        {mode === 'demo' && (
          <>
            <section className="step-card">
              <div className="step-number">1</div>
              <h2>Download & Print</h2>
              <p>Download the sample exam, print it, and shade some bubbles.</p>
              <a href="/demo_exam.pdf" download className="button secondary">Download Sample Exam PDF</a>
            </section>
            <section className="step-card">
              <div className="step-number">2</div>
              <h2>Upload Photo</h2>
              <p>Take a clear photo with all 4 corner squares visible.</p>
              <div className="upload-area">
                <input type="file" accept="image/*" onChange={handleFileChange} id="file-upload" className="file-input" />
                <label htmlFor="file-upload" className="file-label">
                  {files.length ? files[0].name : 'Choose an image...'}
                </label>
                {files.length > 0 && (
                  <button onClick={() => { setExamCode('DEMO'); handleScan() }} disabled={isProcessing} className="button primary">
                    {isProcessing ? 'Grading...' : 'Grade Exam'}
                  </button>
                )}
              </div>
            </section>
          </>
        )}

        {/* ── SCAN MODE ── */}
        {mode === 'scan' && (
          <>
            <section className="step-card">
              <div className="step-number">1</div>
              <h2>Enter Exam Code</h2>
              <input type="text" value={examCode} onChange={(e) => setExamCode(e.target.value)}
                placeholder="e.g. KCL-2T-2026" className="code-input" />
              <p style={{marginTop: '0.75rem', fontSize: '0.85rem', color: '#64748b'}}>
                Need the answer sheet? <a href="/demo_omr.pdf" download style={{color: '#2563eb'}}>Download OMR Sheet PDF</a>
              </p>
            </section>
            <section className="step-card">
              <div className="step-number">2</div>
              <h2>Upload Photos</h2>
              <p>Select one or many answer sheet photos at once.</p>
              <div className="upload-area">
                <input type="file" accept="image/*" multiple onChange={handleFileChange} id="file-upload" className="file-input" />
                <label htmlFor="file-upload" className="file-label">
                  {files.length ? `${files.length} file(s) selected` : 'Choose images...'}
                </label>
                <button onClick={handleScan} disabled={!files.length || !examCode.trim() || isProcessing} className="button primary">
                  {isProcessing ? `Processing ${files.length} images...` : `Scan ${files.length} Image${files.length !== 1 ? 's' : ''}`}
                </button>
              </div>
            </section>
          </>
        )}

        {/* ── ANSWER KEY MODE ── */}
        {mode === 'answer-key' && (
          <>
            <section className="step-card">
              <div className="step-number">1</div>
              <h2>Exam Code & Setup</h2>
              <input type="text" value={examCode} onChange={(e) => setExamCode(e.target.value)}
                placeholder="e.g. KCL-2T-2026" className="code-input" />
              <div className="key-setup">
                <label>Questions: <input type="number" value={numQuestions} onChange={(e) => setNumQuestions(parseInt(e.target.value) || 1)} min="1" max="200" /></label>
                <label>Choices: <input type="number" value={numChoices} onChange={(e) => setNumChoices(parseInt(e.target.value) || 2)} min="2" max="8" /></label>
              </div>
            </section>
            <section className="step-card">
              <div className="step-number">2</div>
              <h2>Fill in Correct Answers</h2>
              <div className="answer-grid">
                {Array.from({ length: numQuestions }, (_, i) => i + 1).map(q => (
                  <div key={q} className="answer-row">
                    <span className="q-label">{q}.</span>
                    {choices.map(c => (
                      <button key={c}
                        className={`choice-btn ${answerKey[q] === c ? 'selected' : ''}`}
                        onClick={() => setAnswerKey({ ...answerKey, [q]: c })}
                      >{c}</button>
                    ))}
                  </div>
                ))}
              </div>
              <div className="key-summary">
                {Object.keys(answerKey).length} / {numQuestions} answered
              </div>
              <button onClick={handleSubmitKey}
                disabled={!examCode.trim() || Object.keys(answerKey).length === 0 || isProcessing}
                className="button primary">
                {isProcessing ? 'Submitting...' : 'Submit Answer Key & Grade All'}
              </button>
            </section>
          </>
        )}
      </main>

      {/* ── ERROR ── */}
      {error && <section className="error-section"><p>{error}</p></section>}

      {/* ── RESULTS ── */}
      {results && results.type === 'single' && (
        <section className="result-section">
          <h2>Scan Complete!</h2>
          <p className="time-badge">Read in {results.data.time_ms}ms</p>
          {results.data.graded && <p className="score-badge">{results.data.score}/{results.data.total} ({results.data.percentage}%)</p>}
          {!results.data.graded && <p className="info-badge">Marks extracted. Submit an answer key to see scores.</p>}
          <div className="marks-table">
            <table>
              <thead><tr><th>Q</th><th>Answer</th></tr></thead>
              <tbody>
                {Object.entries(results.data.marks).sort((a, b) => parseInt(a[0]) - parseInt(b[0])).map(([q, a]) => (
                  <tr key={q}><td>{q}</td><td>{a || '—'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {results && results.type === 'batch' && (
        <section className="result-section">
          <h2>Batch Complete!</h2>
          <p className="time-badge">{results.data.successful} scanned in {results.data.total_time_ms}ms</p>
          {results.data.failed > 0 && <p className="error-badge">{results.data.failed} failed</p>}
          <div className="marks-table">
            <table>
              <thead><tr><th>#</th><th>File</th><th>Time</th><th>Result</th></tr></thead>
              <tbody>
                {results.data.results.map((r, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td>{r.filename || r.scan_id}</td>
                    <td>{r.time_ms ? `${r.time_ms}ms` : '—'}</td>
                    <td>{r.error ? `❌ ${r.error}` : r.graded ? `${r.score}/${r.total}` : '✅ Marks saved'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {keySubmitted && (
        <section className="result-section">
          <h2>Answer Key Submitted!</h2>
          <p>{keySubmitted.scans_retrograded} existing scans graded.</p>
          {keySubmitted.results.length > 0 && (
            <div className="marks-table">
              <table>
                <thead><tr><th>Scan ID</th><th>Score</th></tr></thead>
                <tbody>
                  {keySubmitted.results.map((r, i) => (
                    <tr key={i}>
                      <td>{r.scan_id}</td>
                      <td>{r.error ? `❌ ${r.error}` : `${r.score}/${r.total} (${r.percentage}%)`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  )
}

export default App
