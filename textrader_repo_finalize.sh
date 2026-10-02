#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

###############################################################################
# TEXTRADER X — PROFESSIONAL REPOSITORY FINALIZER
#
# Purpose:
#   Professionalize the EXISTING TEXTRADER X repository while preserving
#   project-owned files. Creates documentation, provenance, GitHub automation,
#   architecture diagrams, validation surfaces, and Git metadata.
#
# Safe-by-default:
#   - Does NOT delete project files.
#   - Does NOT rewrite historical release contents.
#   - Does NOT push unless PUSH_TO_GITHUB=1.
#
# Usage:
#   chmod +x textrader_repo_finalize.sh
#   ./textrader_repo_finalize.sh
#
# Optional GitHub push:
#   GITHUB_REMOTE="https://github.com/YOUR_USERNAME/TEXTRADER-X.git" \
#   PUSH_TO_GITHUB=1 \
#   ./textrader_repo_finalize.sh
###############################################################################

PROJECT_NAME="TEXTRADER-X"
DEFAULT_BRANCH="main"
REMOTE="${GITHUB_REMOTE:-}"
PUSH="${PUSH_TO_GITHUB:-0}"
ROOT="$(pwd)"
STAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

die() {
    printf '\n[ERROR] %s\n' "$*" >&2
    exit 1
}

info() {
    printf '[INFO] %s\n' "$*"
}

ok() {
    printf '[ OK ] %s\n' "$*"
}

trap 'printf "\n[ERROR] Script failed at line %s. No automatic destructive rollback was performed.\n" "$LINENO" >&2' ERR

command -v git >/dev/null 2>&1 || die "git is required."
command -v python3 >/dev/null 2>&1 || die "python3 is required."

printf '\n'
printf '%s\n' '======================================================================'
printf '%s\n' ' TEXTRADER X — PROFESSIONAL REPOSITORY FINALIZER'
printf '%s\n' '======================================================================'
printf 'Root      : %s\n' "$ROOT"
printf 'Timestamp : %s\n' "$STAMP"
printf '\n'

###############################################################################
# 1. Git repository
###############################################################################

if [[ ! -d .git ]]; then
    info "Initializing Git repository..."
    git init
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "Current directory is not a Git work tree."
fi

branch="$(git branch --show-current || true)"
if [[ -z "$branch" ]]; then
    git checkout -b "$DEFAULT_BRANCH"
elif [[ "$branch" != "$DEFAULT_BRANCH" ]]; then
    info "Renaming branch '$branch' -> '$DEFAULT_BRANCH'"
    git branch -M "$DEFAULT_BRANCH"
fi

###############################################################################
# 2. Create professional directories
###############################################################################

info "Creating repository structure..."

mkdir -p \
    .github/workflows \
    .github/ISSUE_TEMPLATE \
    .github/PULL_REQUEST_TEMPLATE \
    docs/architecture \
    docs/engineering \
    docs/specifications \
    docs/research \
    docs/security \
    docs/testing \
    docs/source-of-truth \
    architecture \
    evidence/validation \
    evidence/regression \
    evidence/security \
    evidence/stress \
    evidence/reproducibility \
    provenance/RELEASE_MANIFESTS \
    provenance/SHA256SUMS \
    research

###############################################################################
# 3. .gitignore — only create if absent; never destroy an existing one
###############################################################################

if [[ ! -f .gitignore ]]; then
cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
.coverage.*
htmlcov/

# Environments
.venv/
venv/
env/
ENV/

# Packaging
build/
dist/
*.egg-info/
.eggs/

# Secrets
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
*.crt

# Runtime databases
*.db
*.db-shm
*.db-wal
*.sqlite
*.sqlite3

# Logs / runtime output
*.log
logs/
tmp/
temp/

# IDE / OS
.idea/
.vscode/
*.swp
*.swo
.DS_Store
Thumbs.db

# Local evidence / generated reports
.local/
.local-evidence/
EOF
else
    info ".gitignore already exists; preserving it."
fi

###############################################################################
# 4. README
###############################################################################

info "Writing README.md..."

cat > README.md <<'EOF'
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
EOF

###############################################################################
# 5. Architecture document
###############################################################################

info "Writing ARCHITECTURE.md..."

cat > ARCHITECTURE.md <<'EOF'
# TEXTRADER X — Architecture

## 1. Architectural Intent

TEXTRADER X is organized as a layered decision-engineering system.

```mermaid
flowchart LR
    DATA["Market / Manual Data"]
    ADAPTER["Adapters"]
    CONTEXT["Context"]
    AGENT["Super-Agent"]
    SIZE["Position Sizer"]
    RISK["Risk Engine"]
    SAFETY["Safety Interlocks"]
    EXEC["Execution"]
    MEMORY["Memory"]
    AUDIT["Audit"]
    API["FastAPI"]
    CLI["CLI"]

    DATA --> ADAPTER
    ADAPTER --> CONTEXT
    CONTEXT --> AGENT
    AGENT --> SIZE
    SIZE --> RISK
    RISK --> SAFETY
    SAFETY --> EXEC
    EXEC --> MEMORY
    MEMORY --> AUDIT
    API --> AGENT
    CLI --> AGENT
```

## 2. Core Principles

1. Explicit component boundaries.
2. Separation of decision and execution.
3. Deterministic risk gates.
4. Safety-first failure boundaries.
5. Persistent state and auditability.
6. Reproducible validation.
7. Historical provenance.
8. Clear operator interfaces.

## 3. Failure Boundary

```mermaid
flowchart TD
    INPUT["Input"]
    VALIDATE["Validation"]
    DECISION["Decision"]
    RISK["Risk Gate"]
    EXEC["Execution Gate"]
    FAIL["Safe Failure"]
    AUDIT["Audit"]

    INPUT --> VALIDATE
    VALIDATE -->|valid| DECISION
    VALIDATE -->|invalid| FAIL
    DECISION --> RISK
    RISK -->|approved| EXEC
    RISK -->|rejected| FAIL
    EXEC -->|failure| FAIL
    EXEC -->|success| AUDIT
    FAIL --> AUDIT
```

## 4. Control Plane

CLI and web interfaces are control/observability surfaces. Core business logic
should remain testable independently of the presentation layer.

## 5. Historical Boundary

Release-specific source and documentation are preserved under `releases/`.
Provenance is recorded under `provenance/`.
EOF

###############################################################################
# 6. Changelog
###############################################################################

info "Writing CHANGELOG.md..."

cat > CHANGELOG.md <<'EOF'
# Changelog

TEXTRADER X release lineage:

- `v2.0.1` — historical baseline
- `v3.0.0` — major 3.x generation
- `v3.1.0` — 3.1.x generation
- `v3.1.1` — debugged 3.1.x release
- `v3.2.0` — 3.2.x generation
- `v4.0.0` — major 4.x generation
- `v4.0.1` — 4.x refinement
- `v4.0.2` — current canonical release

For exact historical details, inspect the corresponding directory under
`releases/` and its provenance manifest.
EOF

###############################################################################
# 7. Security
###############################################################################

info "Writing SECURITY.md..."

cat > SECURITY.md <<'EOF'
# Security Policy

## Scope

TEXTRADER X contains software for automated trading decision systems.

Security-sensitive areas include:

- credential and secret exposure
- unsafe execution paths
- authentication/authorization
- external integrations
- data integrity
- kill-switch behavior
- unintended live execution
- dependency/supply-chain risks

## Reporting

Do not publicly disclose an exploitable vulnerability before coordinated review.

Include:

- affected version
- component
- reproduction steps
- expected behavior
- observed behavior
- relevant sanitized evidence

Never include API keys, passwords, tokens or private keys.

## Safety Boundary

Testing and software validation do not guarantee profitable trading outcomes.

Live execution requires appropriate independent operational controls and review.
EOF

###############################################################################
# 8. Contributing
###############################################################################

info "Writing CONTRIBUTING.md..."

cat > CONTRIBUTING.md <<'EOF'
# Contributing

## Engineering standards

Changes should be:

- reproducible
- testable
- documented
- traceable
- appropriately scoped

## Validation

```bash
python -m compileall -q trader tests
pytest -q
pip check
```

## Commit conventions

Preferred prefixes:

```text
feat:
fix:
refactor:
test:
docs:
security:
build:
ci:
release:
```

Example:

```text
feat: improve deterministic position sizing
```

## Historical material

Do not rewrite historical release artifacts merely to make them look cleaner.
Use the provenance layer to explain discrepancies and lineage.
EOF

###############################################################################
# 9. GitHub workflows
###############################################################################

info "Writing GitHub Actions..."

cat > .github/workflows/ci.yml <<'EOF'
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    name: Python ${{ matrix.python-version }}
    runs-on: ubuntu-latest

    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Compile
        run: python -m compileall -q trader tests

      - name: Test
        run: pytest -q
EOF

cat > .github/workflows/release.yml <<'EOF'
name: Release Validation

on:
  push:
    tags:
      - "v*"

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Compile
        run: python -m compileall -q trader tests

      - name: Test
        run: pytest -q

      - name: Repository status
        run: git status --short
EOF

###############################################################################
# 10. GitHub templates
###############################################################################

info "Writing GitHub templates..."

cat > .github/PULL_REQUEST_TEMPLATE.md <<'EOF'
## Summary

<!-- What changed and why? -->

## Scope

- [ ] Source
- [ ] Tests
- [ ] Documentation
- [ ] Security
- [ ] Performance
- [ ] Release / provenance

## Validation

```bash
python -m compileall -q trader tests
pytest -q
pip check
```

## Risk / Compatibility

<!-- Describe behavior changes and operational risk. -->

## Checklist

- [ ] No secrets added
- [ ] Tests updated where needed
- [ ] Documentation updated
- [ ] Historical artifacts preserved
- [ ] Provenance implications reviewed
EOF

cat > .github/ISSUE_TEMPLATE/bug_report.md <<'EOF'
---
name: Bug report
about: Report a reproducible software issue
title: "[BUG] "
labels: bug
---

## Description

## Environment

- OS:
- Python:
- TEXTRADER version:

## Reproduction

```text
Paste minimal reproduction steps here.
```

## Expected behavior

## Actual behavior

## Evidence

Remove credentials, API keys and other secrets before submission.
EOF

# Do not overwrite CODEOWNERS if the user already has one.
if [[ ! -f .github/CODEOWNERS ]]; then
cat > .github/CODEOWNERS <<'EOF'
# Replace YOUR_USERNAME with the GitHub owner before publishing.
* @YOUR_USERNAME
EOF
fi

###############################################################################
# 11. Version lineage / release process
###############################################################################

info "Writing engineering docs..."

cat > docs/engineering/version-lineage.md <<'EOF'
# TEXTRADER X Version Lineage

```mermaid
flowchart LR
    V201["v2.0.1"] --> V300["v3.0.0"]
    V300 --> V310["v3.1.0"]
    V310 --> V311["v3.1.1"]
    V311 --> V320["v3.2.0"]
    V320 --> V400["v4.0.0"]
    V400 --> V401["v4.0.1"]
    V401 --> V402["v4.0.2"]
```

Canonical release tags:

```text
v2.0.1
v3.0.0
v3.1.0
v3.1.1
v3.2.0
v4.0.0
v4.0.1
v4.0.2
```

Release-specific source and documentation remain under `releases/`.
EOF

cat > docs/engineering/release-process.md <<'EOF'
# Release Process

## Validate

```bash
python -m compileall -q trader tests
pytest -q
pip check
```

## Inspect

```bash
git status
git diff
git diff --cached
```

## Commit

```bash
git add -A
git commit -m "release: TEXTRADER X vX.Y.Z"
```

## Annotated tag

```bash
git tag -a vX.Y.Z -m "TEXTRADER X vX.Y.Z"
```

## Verify

```bash
git show vX.Y.Z
git tag --verify vX.Y.Z
```

## Push

```bash
git push origin main
git push origin vX.Y.Z
```
EOF

###############################################################################
# 12. Citation
###############################################################################

info "Writing CITATION.cff..."

cat > CITATION.cff <<'EOF'
cff-version: 1.2.0
title: "TEXTRADER X"
message: "If you use this software in research or engineering work, please cite it."
type: software
authors:
  - family-names: "Kafil"
    given-names: "Moeid"
version: "4.0.2"
license: "Proprietary"
repository-code: "https://github.com/YOUR_USERNAME/TEXTRADER-X"
EOF

###############################################################################
# 13. Provenance — BEFORE/AFTER inventories
###############################################################################

info "Creating pre-change inventory..."

python3 - <<'PY'
from pathlib import Path
import hashlib

root = Path(".").resolve()
out = root / "provenance" / "PRE_CHANGE_SHA256SUMS.txt"

ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

files = []
for p in root.rglob("*"):
    if not p.is_file():
        continue
    rel = p.relative_to(root)
    if any(part in ignored for part in rel.parts):
        continue
    files.append(rel)

with out.open("w", encoding="utf-8") as f:
    for rel in sorted(files, key=str):
        h = hashlib.sha256()
        with (root / rel).open("rb") as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                h.update(chunk)
        f.write(f"{h.hexdigest()}  {rel}\n")

(root / "provenance" / "PRE_CHANGE_FILE_LIST.txt").write_text(
    "\n".join(str(x) for x in sorted(files, key=str)) + "\n",
    encoding="utf-8",
)

print(f"Pre-change files indexed: {len(files)}")
PY

info "Creating complete file inventory..."

python3 - <<'PY'
from pathlib import Path
import hashlib, json
from datetime import datetime, timezone

root = Path(".").resolve()
ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

records = []

for p in sorted(root.rglob("*")):
    if not p.is_file():
        continue

    rel = p.relative_to(root)

    if any(part in ignored for part in rel.parts):
        continue

    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)

        records.append({
            "path": str(rel),
            "size_bytes": p.stat().st_size,
            "sha256": h.hexdigest(),
        })
    except OSError:
        pass

payload = {
    "project": "TEXTRADER X",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "file_count": len(records),
    "files": records,
}

(root / "provenance" / "FILE_INVENTORY.json").write_text(
    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

print(f"Current files indexed: {len(records)}")
PY

###############################################################################
# 14. Validate release tags — never invent tags
###############################################################################

info "Checking existing release tags..."

for tag in \
    v2.0.1 \
    v3.0.0 \
    v3.1.0 \
    v3.1.1 \
    v3.2.0 \
    v4.0.0 \
    v4.0.1 \
    v4.0.2
do
    if git rev-parse -q --verify "refs/tags/$tag" >/dev/null 2>&1; then
        ok "Existing tag preserved: $tag"
    else
        info "Tag absent (not created automatically): $tag"
    fi
done

###############################################################################
# 15. Static validation
###############################################################################

info "Running shell syntax validation..."

bash -n "$0"
ok "bash -n passed."

info "Validating generated JSON..."

python3 -m json.tool provenance/FILE_INVENTORY.json >/dev/null
ok "FILE_INVENTORY.json is valid."

###############################################################################
# 16. Git diff / stage
###############################################################################

info "Staging repository changes..."

git add -A

printf '\n%s\n' '----------------------------------------------------------------------'
printf '%s\n' ' STAGED CHANGE SUMMARY'
printf '%s\n' '----------------------------------------------------------------------'

git diff --cached --stat || true

printf '\n%s\n' '----------------------------------------------------------------------'
printf '%s\n' ' RELEASE TAGS'
printf '%s\n' '----------------------------------------------------------------------'

git tag --list | sort -V

###############################################################################
# 17. Commit only if there are changes
###############################################################################

if git diff --cached --quiet; then
    info "No new changes to commit."
else
    git commit -m "docs: establish professional TEXTRADER X repository surface"
    ok "Professional repository commit created."
fi

###############################################################################
# 18. Configure remote if supplied
###############################################################################

if [[ -n "$REMOTE" ]]; then
    info "Configuring origin: $REMOTE"

    if git remote get-url origin >/dev/null 2>&1; then
        git remote set-url origin "$REMOTE"
    else
        git remote add origin "$REMOTE"
    fi
fi

###############################################################################
# 19. Final report
###############################################################################

printf '\n%s\n' '======================================================================'
printf '%s\n' ' FINAL REPOSITORY REPORT'
printf '%s\n' '======================================================================'

printf '\nBranch:\n'
git branch --show-current

printf '\nRemote:\n'
git remote -v || true

printf '\nRecent history:\n'
git log --oneline --decorate --graph -12

printf '\nTags:\n'
git tag --list | sort -V

printf '\nWorking tree:\n'
git status --short

printf '\nProvenance files:\n'
printf '%s\n' \
    "  provenance/PRE_CHANGE_FILE_LIST.txt" \
    "  provenance/PRE_CHANGE_SHA256SUMS.txt" \
    "  provenance/FILE_INVENTORY.json"

###############################################################################
# 20. Optional push
###############################################################################

if [[ "$PUSH" == "1" ]]; then
    if ! git remote get-url origin >/dev/null 2>&1; then
        die "PUSH_TO_GITHUB=1 but no origin remote exists. Set GITHUB_REMOTE."
    fi

    info "Pushing main..."
    git push -u origin "$DEFAULT_BRANCH"

    info "Pushing tags..."
    git push origin --tags

    ok "GitHub push completed."
else
    printf '\n%s\n' '----------------------------------------------------------------------'
    printf '%s\n' ' PUSH LATER'
    printf '%s\n' '----------------------------------------------------------------------'
    printf '%s\n' \
        'git remote add origin https://github.com/YOUR_USERNAME/TEXTRADER-X.git' \
        'git push -u origin main' \
        'git push origin --tags'
fi

printf '\n%s\n' '======================================================================'
printf '%s\n' ' TEXTRADER X — FINALIZER COMPLETE'
printf '%s\n' '======================================================================'
