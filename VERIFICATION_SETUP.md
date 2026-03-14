# 🔬 Code Verification Infrastructure — Setup Guide

## Quick Start

```bash
# 1. Start SonarQube (port 9000)
docker compose -f docker-compose.verify.yml up -d

# 2. Build the sandbox test runner image
docker build -f Backend/Dockerfile.sandbox -t bitbybit-sandbox .

# 3. Configure SonarQube token (see below)
# 4. Start the backend as usual
cd Backend && uvicorn main:app --reload
```

---

## SonarQube Setup (Layer 3)

### First Boot
SonarQube takes ~60 seconds to fully start. Wait until healthy:

```bash
docker compose -f docker-compose.verify.yml ps
# Wait for STATUS to show "healthy"
```

### Generate API Token
1. Open http://localhost:9000
2. Login: `admin` / `admin` (you'll be prompted to change the password)
3. Go to **My Account → Security → Generate Token**
4. Name: `bitbybit-verify`, Type: `Global Analysis Token`
5. Copy the token and paste into `Backend/.env`:
   ```
   SONARQUBE_TOKEN=squ_abc123...
   ```

### Stop / Remove
```bash
docker compose -f docker-compose.verify.yml down        # Stop
docker compose -f docker-compose.verify.yml down -v      # Stop + delete data
```

---

## Sandbox Runner (Layer 2)

### Build
```bash
docker build -f Backend/Dockerfile.sandbox -t bitbybit-sandbox .
```

### What It Does
- Runs freelancer test suites in a **zero-network** Docker container
- Supports Python (pytest), JavaScript (jest/npm test), and Go (go test)
- Security constraints: `--network=none`, `--memory=512m`, `--cpus=1.0`, `--pids-limit=256`, `--read-only`
- Results output as JSON to `.test_results.json`

### Manual Test
```bash
# Clone a sample repo and run tests in sandbox
git clone https://github.com/some/repo /tmp/test-repo
docker run --rm --network=none -v /tmp/test-repo:/app:rw bitbybit-sandbox python 120
```

---

## How the Pipeline Degrades

The system is designed to work at **any infrastructure level**:

| Docker + SonarQube | Behavior |
|--------------------|----------|
| ✅ Both available | Full 4-layer pipeline with Docker sandbox isolation |
| ✅ Docker only | Sandboxed tests + SonarQube neutral (50/100) |
| ❌ Neither | Subprocess tests + SonarQube neutral (50/100) |

No infrastructure is required for development. The pipeline always completes — it just produces more accurate results with Docker + SonarQube.

---

## Architecture

```
Submission (repo_url + commit_hash)
       │
       ▼
   clone_repo()
       │
       ├─► Layer 1: Static AST Analysis    (15%)  — always runs
       │
       ├─► Layer 2: Runtime Tests           (35%)  — Docker sandbox or subprocess
       │         └─ Docker: --network=none, --memory=512m, --read-only
       │
       ├─► Layer 3: SonarQube Quality Gate  (20%)  — Docker scanner or CLI or neutral
       │         └─ Docker: sonarsource/sonar-scanner-cli → poll API
       │
       └─► Layer 4: LLM Semantic Review     (30%)  — via Groq API
                └─ Cannot exceed 84/100 alone (anti-gaming)
```
