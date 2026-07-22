# Contributing to MARKA 🎯

Thank you for your interest in contributing to MARKA! We welcome bug reports, feature requests, documentation improvements, and pull requests from developers around the world.

---

## 🚀 Getting Started

1. **Fork the Repository**: Click "Fork" on GitHub.
2. **Clone your Fork**:
   ```bash
   git clone git@github.com:YOUR_USERNAME/MARKA.git
   cd MARKA
   ```
3. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/my-amazing-feature
   ```

---

## 🛠️ Development Setup

### Python Backend
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py"
```

### React Frontend
```bash
cd demo_site
npm install
npm run build
```

---

## 🧪 Testing Guidelines

Before opening a Pull Request, please ensure all unit tests pass locally:

```bash
# Run unit tests
python -m unittest tests/test_parser.py tests/test_layout.py tests/test_scanner.py tests/test_flowable.py

# Verify frontend build
cd demo_site && npm run build
```

---

## 📝 Commit Messages & Style

- Follow standard conventional commit conventions (`feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).
- Keep commit descriptions clear and concise.

Thank you for helping empower educators and students worldwide! 🚀
