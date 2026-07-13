import React from 'react';
import { Camera, Zap, FileSpreadsheet, ShieldCheck, CheckCircle2, ArrowRight, Download } from 'lucide-react';
import './Landing.css';

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
    <div className="landing-container">
      {/* Navigation */}
      <nav className="landing-nav">
        <div className="nav-brand">MARKA</div>
        <div className="nav-links">
          <a href="#features" className="nav-link">Features</a>
          <a href="#pricing" className="nav-link">Pricing</a>
          <button onClick={onGetStarted} className="btn btn-primary" style={{ padding: '0.5rem 1.25rem' }}>
            Login
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-badge">🚀 The Future of Grading in Nigeria</div>
        <h1 className="hero-title">Keep the Paper.<br/><span>Eliminate the Marking.</span></h1>
        <p className="hero-subtitle">
          Print standard OMR sheets on normal paper. Students shade with pencils. 
          Snap a picture with your phone. Instantly get grades and export to CSV.
        </p>
        <div className="hero-cta">
          <button onClick={onGetStarted} className="btn btn-primary btn-large">
            Get Your ID & Start Grading
          </button>
          <button onClick={handleDownloadDemo} className="btn btn-outline btn-large" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Download size={20} />
            Download Trial OMR Sheet
          </button>
        </div>

        {/* Visual Mockup */}
        <div className="hero-visual">
          <div className="mockup-container">
            <div className="mockup-header">
              <div className="mockup-dot"></div>
              <div className="mockup-dot"></div>
              <div className="mockup-dot"></div>
            </div>
            <div className="mockup-body">
              {/* Decorative mockup showing the grading engine */}
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <Camera size={64} style={{ margin: '0 auto 1rem', opacity: 0.5, color: 'var(--primary)' }} />
                <p style={{ fontWeight: 600, fontSize: '1.25rem' }}>Visual Zero ML Grading Engine in Action</p>
                <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>Takes a blurry photo → Isolates anchors → Grades bubbles → Outputs CSV</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="feature-section">
        <div className="section-header">
          <h2 className="section-title">Why Schools Trust MARKA</h2>
          <p className="hero-subtitle" style={{ margin: '0 auto' }}>Designed specifically for the realities of Nigerian classrooms.</p>
        </div>
        
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon"><Camera size={24} /></div>
            <h3>Works with Any Phone</h3>
            <p>No expensive scanner machines needed. The Visual Zero engine accurately corrects skewed, poorly-lit photos taken with regular Android or iOS cameras.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><FileSpreadsheet size={24} /></div>
            <h3>Instant CSV Export</h3>
            <p>Once you finish scanning the class pile, download a single ZIP containing a neatly formatted CSV of all scores and visual proof images for the records.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><ShieldCheck size={24} /></div>
            <h3>No Passwords Required</h3>
            <p>Forget forgotten passwords. We generate a secure MARKA ID and PIN for you instantly upon purchase. Keep it safe, and you're always good to go.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><Zap size={24} /></div>
            <h3>Lightning Fast Processing</h3>
            <p>Upload 100 images at once directly to our secure edge storage. Our asynchronous background workers grade them in seconds.</p>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="pricing-section">
        <div className="section-header">
          <h2 className="section-title">Pay As You Grade</h2>
          <p className="hero-subtitle" style={{ margin: '0 auto' }}>No monthly subscriptions. Just buy credits when exams arrive.</p>
        </div>

        <div className="pricing-grid">
          {/* Starter */}
          <div className="pricing-card">
            <div className="price-header">
              <div className="price-name">Starter</div>
              <div className="price-amount">₦5,000</div>
              <div className="price-sub">100 credits · ₦50 each</div>
            </div>
            <ul className="price-features">
              <li className="price-feature"><CheckCircle2 size={20} /> Instantly Generated ID</li>
              <li className="price-feature"><CheckCircle2 size={20} /> 100 Accurate Gradings</li>
              <li className="price-feature"><CheckCircle2 size={20} /> CSV Result Exports</li>
            </ul>
            <button onClick={onGetStarted} className="btn btn-outline" style={{ width: '100%', padding: '1rem' }}>Get Starter</button>
          </div>

          {/* Growth */}
          <div className="pricing-card popular">
            <div className="popular-badge">Most Popular</div>
            <div className="price-header">
              <div className="price-name">Growth</div>
              <div className="price-amount">₦11,250</div>
              <div className="price-sub">250 credits · ₦45 each</div>
            </div>
            <ul className="price-features">
              <li className="price-feature"><CheckCircle2 size={20} /> Instantly Generated ID</li>
              <li className="price-feature"><CheckCircle2 size={20} /> 250 Accurate Gradings</li>
              <li className="price-feature"><CheckCircle2 size={20} /> CSV Result Exports</li>
              <li className="price-feature"><CheckCircle2 size={20} /> Priority Background Queue</li>
            </ul>
            <button onClick={onGetStarted} className="btn btn-primary" style={{ width: '100%', padding: '1rem' }}>Get Growth Pack</button>
          </div>

          {/* School */}
          <div className="pricing-card">
            <div className="price-header">
              <div className="price-name">School</div>
              <div className="price-amount">₦20,000</div>
              <div className="price-sub">500 credits · ₦40 each</div>
            </div>
            <ul className="price-features">
              <li className="price-feature"><CheckCircle2 size={20} /> Instantly Generated ID</li>
              <li className="price-feature"><CheckCircle2 size={20} /> 500 Accurate Gradings</li>
              <li className="price-feature"><CheckCircle2 size={20} /> CSV Result Exports</li>
              <li className="price-feature"><CheckCircle2 size={20} /> Visual Proof Retention</li>
            </ul>
            <button onClick={onGetStarted} className="btn btn-outline" style={{ width: '100%', padding: '1rem' }}>Get School Pack</button>
          </div>

          {/* Institution */}
          <div className="pricing-card">
            <div className="price-header">
              <div className="price-name">Institution</div>
              <div className="price-amount">₦35,000</div>
              <div className="price-sub">1,000 credits · ₦35 each</div>
            </div>
            <ul className="price-features">
              <li className="price-feature"><CheckCircle2 size={20} /> Instantly Generated ID</li>
              <li className="price-feature"><CheckCircle2 size={20} /> 1,000 Accurate Gradings</li>
              <li className="price-feature"><CheckCircle2 size={20} /> CSV Result Exports</li>
              <li className="price-feature"><CheckCircle2 size={20} /> Best Per-Credit Rate</li>
            </ul>
            <button onClick={onGetStarted} className="btn btn-outline" style={{ width: '100%', padding: '1rem' }}>Get Institution Pack</button>
          </div>
        </div>
        <p className="hero-subtitle" style={{ margin: '1.5rem auto 0', textAlign: 'center' }}>
          Need 5,000+ credits? <a href="mailto:hello@marka.ng" style={{ color: 'var(--primary)', fontWeight: 600 }}>Contact us for Enterprise pricing.</a>
        </p>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-brand">MARKA OMR</div>
        <p className="footer-text">© {new Date().getFullYear()} MARKA. All rights reserved.</p>
        <p className="footer-text" style={{ marginTop: '0.5rem' }}>Built for fast, reliable assessment grading.</p>
      </footer>
    </div>
  );
}
