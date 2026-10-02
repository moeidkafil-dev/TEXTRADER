<div align="center">

# ⚡ TEXTRADER X

### Autonomous Trading Intelligence & Decision Engineering Platform

**Agentic orchestration · position sizing · deterministic risk controls · execution safety · memory · auditability**

<br>

[![Release](https://img.shields.io/badge/release-v4.0.2-111827?style=for-the-badge)](releases/v4.0.2)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://img.shields.io/github/actions/workflow/status/YOUR_USERNAME/TEXTRADER-X/ci.yml?style=for-the-badge&label=CI)](../../actions)
[![Security](https://img.shields.io/badge/security-engineered-0f766e?style=for-the-badge)](SECURITY.md)
[![Architecture](https://img.shields.io/badge/architecture-agentic%20systems-7c3aed?style=for-the-badge)](ARCHITECTURE.md)

</div>

---

## 🧭 System Overview

TEXTRADER X is an engineering platform for automated trading decision systems.

Its architecture separates market data, context construction, decision orchestration,
position sizing, risk controls, execution, persistence, and observability.

> **Engineering boundary:** validation of software behavior does not constitute a
> guarantee of profitability or financial performance.

```mermaid
flowchart TB
    A["📥 Market / Manual Input"]
    B["🔌 Data Adapters"]
    C["🧠 Context & Features"]
    D["🤖 Super-Agent"]
    E["📐 Position Sizer"]
    F["🛡️ Risk Engine"]
    G["⛔ Safety Interlocks"]
    H["⚙️ Execution"]
    I["💾 Memory & State"]
    J["📊 Audit / Observability"]
    K["🌐 FastAPI Control Plane"]
    L["⌨️ CLI"]

    A --> B --> C --> D --> E --> F
    F --> G
    G --> H
    F --> H
    H --> I --> J
    D --> I
    K --> D
    K --> J
    L --> D
    L --> J
```

---

## 🧠 Decision Pipeline

```mermaid
sequenceDiagram
    participant M as Market
    participant A as Adapter
    participant S as Super-Agent
    participant P as Position Sizer
    participant R as Risk Engine
    participant E as Execution
    participant X as Audit

    M->>A: Raw market data
    A->>S: Normalized context
    S->>P: Candidate decision
    P->>R: Proposed position
    R->>R: Constraint evaluation

    alt Approved
        R->>E: Authorized execution
        E->>X: Result + evidence
    else Rejected
        R->>X: Rejection + reason
    end
```

---

## 🧬 Release Lineage

```mermaid
gitGraph
    commit id: "v2.0.1"
    commit id: "v3.0.0"
    commit id: "v3.1.0"
    commit id: "v3.1.1"
    commit id: "v3.2.0"
    commit id: "v4.0.0"
    commit id: "v4.0.1"
    commit id: "v4.0.2"
```

```text
v2.0.1
  │
  ▼
v3.0.0
  │
  ▼
v3.1.0
  │
  ▼
v3.1.1
  │
  ▼
v3.2.0
  │
  ▼
v4.0.0
  │
  ▼
v4.0.1
  │
  ▼
v4.0.2
```

---

## 🏗️ Repository Architecture

```text
TEXTRADER-X/
│
├── .github/                    # CI, release automation, templates
├── trader/                     # Production implementation
├── tests/                      # Automated tests
├── benchmarks/                 # Benchmarks / reproducibility
├── configs/                    # Runtime configuration
│
├── docs/
│   ├── architecture/
│   ├── engineering/
│   ├── specifications/
│   ├── research/
│   ├── security/
│   ├── testing/
│   └── source-of-truth/
│
├── releases/                   # Preserved release-specific material
├── evidence/                   # Validation evidence
├── research/                   # Research material
├── architecture/               # Architecture artifacts
├── provenance/                 # SHA-256 + lineage + inventories
│
├── README.md
├── ARCHITECTURE.md
├── CHANGELOG.md
├── SECURITY.md
├── CONTRIBUTING.md
└── pyproject.toml
```

### Engineering layers

| Layer | Responsibility |
|---|---|
| 🔌 Adapters | External/market data boundaries |
| 🧠 Context | Normalize decision context |
| 🤖 Agent | Decision orchestration |
| 📐 Position Sizer | Position/trade sizing |
| 🛡️ Risk Engine | Risk constraints |
| ⛔ Interlocks | Safety and kill-switch boundaries |
| ⚙️ Execution | Approved action execution |
| 💾 Memory | State and decision history |
| 📊 Observability | Audit and diagnostics |
| 🌐 Web | Administrative control plane |
| ⌨️ CLI | Operator/developer interface |

---

## 🧪 Verification Surface

Typical checks:

```bash
python -m compileall -q trader tests
pytest -q
pip check
```

Repository evidence is organized under:

```text
evidence/
provenance/
releases/
```

---

## 🔐 Security

Security engineering includes:

- secret exclusion
- execution boundaries
- safety interlocks
- kill-switch behavior
- regression validation
- release checksums
- provenance
- auditable decision evidence

See [`SECURITY.md`](SECURITY.md).

---

## 📦 Release History

| Release | Role |
|---|---|
| `v2.0.1` | Historical baseline |
| `v3.0.0` | Major 3.x generation |
| `v3.1.0` | 3.1.x generation |
| `v3.1.1` | Debugged 3.1.x release |
| `v3.2.0` | 3.2.x generation |
| `v4.0.0` | Major 4.x generation |
| `v4.0.1` | 4.x refinement |
| `v4.0.2` | Current canonical release |

Exact release material is preserved under `releases/`.

---

## 🚀 Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/TEXTRADER-X.git
cd TEXTRADER-X

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[dev]"

python -m compileall -q trader tests
pytest -q
```

---

## 📚 Documentation Map

| Document | Purpose |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System architecture |
| [`CHANGELOG.md`](CHANGELOG.md) | Release evolution |
| [`SECURITY.md`](SECURITY.md) | Security policy |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Engineering workflow |
| `docs/engineering/` | Release engineering |
| `docs/testing/` | Validation |
| `provenance/` | File/source provenance |
| `releases/` | Historical release surfaces |

---

## 🧾 Provenance Philosophy

TEXTRADER X deliberately preserves historical project material.

The repository distinguishes between:

```text
SOURCE
  ↓
RELEASE
  ↓
EVIDENCE
  ↓
PROVENANCE
  ↓
CURRENT ENGINEERING SURFACE
```

Historical documents are not silently rewritten simply to make the repository
look cleaner. The engineering layer explains lineage while preserving source
material.

---

<div align="center">

### ⚡ TEXTRADER X

**Engineering · Risk · Agentic Systems · Reproducibility · Auditability**

</div>
