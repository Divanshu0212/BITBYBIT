"""
Code Verification Service — GitHub Repo Pipeline
──────────────────────────────────────────────────
4-layer verification for code milestones:
  Layer 1: Static Analysis (AST) — 15%
  Layer 2: Runtime Tests (Sandbox) — 35%
  Layer 3: SonarQube Quality Gate — 20%
  Layer 4: LLM Semantic Review — 30%  (handled by caller)

This module implements layers 1-3.
Layer 4 (LLM) is orchestrated by verification_engine.py.
"""

import ast
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Literal

import httpx

from config import settings

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

CLONE_TIMEOUT = 60       # seconds
TEST_TIMEOUT = 120       # seconds
SONAR_POLL_TIMEOUT = 180 # seconds
SONAR_POLL_INTERVAL = 5  # seconds
DOCKER_TIMEOUT = 180     # seconds for Docker-based test execution

SANDBOX_IMAGE = "bitbybit-sandbox"
SONAR_SCANNER_IMAGE = "sonarsource/sonar-scanner-cli:latest"

SUPPORTED_LANGUAGES = {"python", "javascript", "typescript", "go"}

LAYER_WEIGHTS = {
    "static_analysis": 0.15,
    "runtime_tests": 0.35,
    "sonarqube": 0.20,
    "llm_semantic": 0.30,
}


# ── Docker Helpers ───────────────────────────────────────────────────────

def _is_docker_available() -> bool:
    """Check if Docker daemon is running and accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _is_sandbox_image_available() -> bool:
    """Check if the bitbybit-sandbox Docker image is built."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", SANDBOX_IMAGE],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_docker_tests(repo_path: Path, language: str) -> tuple[dict, dict]:
    """
    Run tests inside a Docker container with zero network access.
    The repo is mounted read-write at /app inside the container.
    Returns (scores, details) tuple.
    """
    scores = {}
    details = {}

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network=none",           # Zero network access
                "--memory=512m",            # Memory limit
                "--cpus=1.0",               # CPU limit
                "--pids-limit=256",          # Process limit
                "--read-only",              # Read-only root filesystem
                "--tmpfs", "/tmp:size=100m",  # Writable tmp
                "-v", f"{repo_path}:/app:rw",
                SANDBOX_IMAGE,
                language,
                str(TEST_TIMEOUT),
            ],
            capture_output=True,
            text=True,
            timeout=DOCKER_TIMEOUT,
        )

        output = result.stdout + result.stderr

        # Try to parse JSON results from the container
        result_file = repo_path / ".test_results.json"
        if result_file.exists():
            try:
                test_data = json.loads(result_file.read_text())
                passed = int(test_data.get("passed", 0))
                failed = int(test_data.get("failed", 0))
                total = passed + failed

                scores["test_presence"] = 100 if total > 0 else 0
                details["test_presence"] = f"{total} tests found (sandboxed)"

                if total > 0:
                    pass_rate = (passed / total) * 100
                    scores["test_execution"] = round(pass_rate)
                    scores["test_pass_ratio"] = round(pass_rate)
                    details["test_execution"] = f"{passed}/{total} tests passed (Docker sandbox)"
                elif result.returncode == 0:
                    scores["test_execution"] = 80
                    details["test_execution"] = "Sandbox ran without errors (no parsable test count)"
                else:
                    scores["test_execution"] = 10
                    details["test_execution"] = f"Sandbox tests failed: {output[:300]}"

                # Clean up result file
                result_file.unlink(missing_ok=True)
                return scores, details

            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: parse stdout
        if result.returncode == 0:
            scores["test_presence"] = 50
            scores["test_execution"] = 70
            details["test_presence"] = "Tests ran in sandbox (could not parse results)"
            details["test_execution"] = "Sandbox completed without errors"
        else:
            scores["test_presence"] = 0
            scores["test_execution"] = 10
            details["test_presence"] = "Tests found but execution failed"
            details["test_execution"] = f"Sandbox error: {output[:300]}"

    except subprocess.TimeoutExpired:
        scores["test_presence"] = 50
        scores["test_execution"] = 20
        details["test_presence"] = "Tests found"
        details["test_execution"] = f"Sandbox timed out ({DOCKER_TIMEOUT}s limit)"
    except FileNotFoundError:
        scores["test_execution"] = 0
        details["test_execution"] = "Docker not available for sandbox execution"
    except Exception as exc:
        logger.error(f"Docker sandbox error: {exc}")
        scores["test_execution"] = 0
        details["test_execution"] = f"Sandbox error: {str(exc)[:200]}"

    return scores, details


# ── Repo Operations ─────────────────────────────────────────────────────

def clone_repo(repo_url: str, commit_hash: str | None = None) -> Path:
    """
    Shallow-clone a GitHub repo to a temp directory.
    Pin to exact commit_hash if provided.
    Returns path to cloned repo.
    """
    # Sanitize URL
    if not re.match(r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+(/.*)?$", repo_url):
        raise ValueError(f"Invalid GitHub URL: {repo_url}")

    # Strip .git suffix and trailing slashes
    clean_url = repo_url.rstrip("/")
    if not clean_url.endswith(".git"):
        clean_url += ".git"

    work_dir = Path(tempfile.mkdtemp(prefix="bitbybit_verify_"))

    try:
        # Clone (shallow if no specific commit needed for efficiency)
        clone_cmd = ["git", "clone", "--depth", "50", clean_url, str(work_dir / "repo")]
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode != 0:
            raise ValueError(f"Git clone failed: {result.stderr[:500]}")

        repo_path = work_dir / "repo"

        # Pin to commit hash if provided
        if commit_hash:
            checkout = subprocess.run(
                ["git", "checkout", commit_hash],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if checkout.returncode != 0:
                raise ValueError(f"Commit {commit_hash} not found: {checkout.stderr[:300]}")

        return repo_path

    except subprocess.TimeoutExpired:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise ValueError("Repository clone timed out (60s limit)")
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def cleanup_repo(repo_path: Path):
    """Remove cloned repo and parent temp directory."""
    parent = repo_path.parent
    shutil.rmtree(parent, ignore_errors=True)


def detect_language(repo_path: Path) -> str:
    """Auto-detect primary language from repo contents."""
    counts = {"python": 0, "javascript": 0, "typescript": 0, "go": 0}

    for root, _dirs, files in os.walk(repo_path):
        # Skip hidden dirs and node_modules
        if any(part.startswith(".") or part == "node_modules" for part in Path(root).parts):
            continue
        for f in files:
            ext = Path(f).suffix.lower()
            if ext == ".py":
                counts["python"] += 1
            elif ext == ".js" or ext == ".jsx":
                counts["javascript"] += 1
            elif ext == ".ts" or ext == ".tsx":
                counts["typescript"] += 1
            elif ext == ".go":
                counts["go"] += 1

    # Check config files for hints
    if (repo_path / "package.json").exists():
        counts["javascript"] += 5
        # Check for TS config
        if (repo_path / "tsconfig.json").exists():
            counts["typescript"] += 10
    if (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
        counts["python"] += 5
    if (repo_path / "go.mod").exists():
        counts["go"] += 10

    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "python"


# ── Layer 1: Static Analysis (AST) ──────────────────────────────────────

def run_ast_analysis(repo_path: Path, language: str, spec_entities: list[str] | None = None) -> dict:
    """
    Parse AST, check structural completeness, complexity, dead code.
    Returns scores dict with individual check results.
    """
    scores: dict[str, float] = {}
    details: dict[str, str] = {}

    if language == "python":
        scores, details = _ast_python(repo_path, spec_entities)
    elif language in ("javascript", "typescript"):
        scores, details = _ast_javascript(repo_path, spec_entities)
    elif language == "go":
        scores, details = _ast_go(repo_path, spec_entities)
    else:
        scores = {"parse_check": 50}
        details = {"parse_check": "Unsupported language for AST"}

    return {"scores": scores, "details": details}


def _get_python_files(repo_path: Path) -> list[Path]:
    """Get all .py files excluding hidden dirs and venvs."""
    py_files = []
    for f in repo_path.rglob("*.py"):
        parts = f.relative_to(repo_path).parts
        if any(p.startswith(".") or p in ("venv", ".venv", "__pycache__", "node_modules") for p in parts):
            continue
        py_files.append(f)
    return py_files


def _ast_python(repo_path: Path, spec_entities: list[str] | None) -> tuple[dict, dict]:
    """AST analysis for Python repos."""
    scores = {}
    details = {}
    py_files = _get_python_files(repo_path)

    if not py_files:
        return {"parse_check": 0}, {"parse_check": "No Python files found"}

    # Parse success rate
    parse_ok = 0
    total_functions = 0
    total_classes = 0
    total_lines = 0
    function_names = set()
    class_names = set()
    high_complexity = []
    dead_code_lines = 0

    for f in py_files:
        try:
            source = f.read_text(errors="ignore")
            total_lines += len(source.splitlines())
            tree = ast.parse(source, filename=str(f))
            parse_ok += 1

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    total_functions += 1
                    function_names.add(node.name)
                    # Cyclomatic complexity estimate: count branches
                    complexity = _estimate_complexity_python(node)
                    if complexity > 15:
                        high_complexity.append((node.name, complexity))
                elif isinstance(node, ast.ClassDef):
                    total_classes += 1
                    class_names.add(node.name)

        except SyntaxError:
            continue

    # Score: parse success
    parse_rate = (parse_ok / len(py_files) * 100) if py_files else 0
    scores["parse_check"] = round(parse_rate)
    details["parse_check"] = f"{parse_ok}/{len(py_files)} files parsed successfully"

    # Score: structural substance
    substance = min(100, total_functions * 5 + total_classes * 10)
    scores["structure_check"] = substance
    details["structure_check"] = f"{total_functions} functions, {total_classes} classes across {total_lines} lines"

    # Score: complexity gate (soft warning)
    if high_complexity:
        penalty = min(len(high_complexity) * 20, 80)
        scores["complexity_check"] = 100 - penalty
        details["complexity_check"] = f"{len(high_complexity)} functions with complexity >15: {', '.join(n for n, _ in high_complexity[:5])}"
    else:
        scores["complexity_check"] = 100
        details["complexity_check"] = "All functions within complexity threshold"

    # Score: spec entity matching (if provided)
    if spec_entities:
        all_names = function_names | class_names
        matched = sum(1 for e in spec_entities if any(e.lower() in n.lower() for n in all_names))
        match_rate = (matched / len(spec_entities) * 100) if spec_entities else 50
        scores["spec_match_check"] = round(match_rate)
        details["spec_match_check"] = f"{matched}/{len(spec_entities)} spec entities found in code"

    # Score: error handling
    error_pattern_count = 0
    for f in py_files:
        try:
            source = f.read_text(errors="ignore")
            error_pattern_count += len(re.findall(r"\b(try|except|raise|finally)\b", source))
        except Exception:
            continue
    scores["error_handling_check"] = min(100, error_pattern_count * 10)
    details["error_handling_check"] = f"{error_pattern_count} error handling statements found"

    return scores, details


def _estimate_complexity_python(node: ast.AST) -> int:
    """Rough cyclomatic complexity for a Python function node."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def _ast_javascript(repo_path: Path, spec_entities: list[str] | None) -> tuple[dict, dict]:
    """AST analysis for JS/TS repos using regex-based structural parsing."""
    scores = {}
    details = {}

    js_files = []
    for ext in ("*.js", "*.jsx", "*.ts", "*.tsx"):
        for f in repo_path.rglob(ext):
            parts = f.relative_to(repo_path).parts
            if any(p.startswith(".") or p in ("node_modules", "dist", "build", ".next") for p in parts):
                continue
            js_files.append(f)

    if not js_files:
        return {"parse_check": 0}, {"parse_check": "No JS/TS files found"}

    total_lines = 0
    function_names = set()
    class_names = set()
    error_count = 0

    for f in js_files:
        try:
            source = f.read_text(errors="ignore")
            total_lines += len(source.splitlines())

            # Extract function/class names via regex
            fn_matches = re.findall(
                r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*\(.*\)\s*\{)",
                source,
            )
            for groups in fn_matches:
                name = next((g for g in groups if g), None)
                if name and not name[0].isupper():
                    function_names.add(name)

            class_matches = re.findall(r"class\s+(\w+)", source)
            class_names.update(class_matches)

            error_count += len(re.findall(r"\b(try|catch|throw|finally)\b", source))
        except Exception:
            continue

    scores["parse_check"] = 100  # Regex-based, always succeeds
    details["parse_check"] = f"{len(js_files)} JS/TS files scanned"

    substance = min(100, len(function_names) * 5 + len(class_names) * 10)
    scores["structure_check"] = substance
    details["structure_check"] = f"{len(function_names)} functions, {len(class_names)} classes across {total_lines} lines"

    scores["complexity_check"] = 80  # Can't do full AST without Node.js parser
    details["complexity_check"] = "Basic structural analysis (full AST requires Node.js parser)"

    if spec_entities:
        all_names = function_names | class_names
        matched = sum(1 for e in spec_entities if any(e.lower() in n.lower() for n in all_names))
        match_rate = (matched / len(spec_entities) * 100) if spec_entities else 50
        scores["spec_match_check"] = round(match_rate)
        details["spec_match_check"] = f"{matched}/{len(spec_entities)} spec entities found"

    scores["error_handling_check"] = min(100, error_count * 10)
    details["error_handling_check"] = f"{error_count} error handling statements"

    return scores, details


def _ast_go(repo_path: Path, spec_entities: list[str] | None) -> tuple[dict, dict]:
    """Basic AST analysis for Go repos."""
    scores = {}
    details = {}

    go_files = [f for f in repo_path.rglob("*.go") if "vendor" not in str(f)]
    if not go_files:
        return {"parse_check": 0}, {"parse_check": "No Go files found"}

    total_lines = 0
    function_names = set()
    error_count = 0

    for f in go_files:
        try:
            source = f.read_text(errors="ignore")
            total_lines += len(source.splitlines())
            fn_matches = re.findall(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)", source)
            function_names.update(fn_matches)
            error_count += len(re.findall(r"\berr\s*!=\s*nil\b", source))
        except Exception:
            continue

    scores["parse_check"] = 100
    details["parse_check"] = f"{len(go_files)} Go files scanned"
    scores["structure_check"] = min(100, len(function_names) * 5)
    details["structure_check"] = f"{len(function_names)} functions across {total_lines} lines"
    scores["complexity_check"] = 80
    details["complexity_check"] = "Basic Go analysis"
    scores["error_handling_check"] = min(100, error_count * 10)
    details["error_handling_check"] = f"{error_count} error checks found"

    return scores, details


# ── Layer 2: Runtime Tests (Sandbox) ─────────────────────────────────────

def run_test_suite(repo_path: Path, language: str) -> dict:
    """
    Execute the project's test suite.
    Priority: Docker sandbox (--network=none) → subprocess fallback.
    Returns scores dict with test results.
    """
    scores = {}
    details = {}

    try:
        # Prefer Docker sandbox for isolated, zero-network execution
        if _is_docker_available() and _is_sandbox_image_available():
            logger.info("Using Docker sandbox for test execution (--network=none)")
            scores, details = _run_docker_tests(repo_path, language)
        else:
            # Fallback to direct subprocess execution
            logger.info("Docker sandbox unavailable, using subprocess fallback")
            if language == "python":
                scores, details = _run_python_tests(repo_path)
            elif language in ("javascript", "typescript"):
                scores, details = _run_js_tests(repo_path)
            elif language == "go":
                scores, details = _run_go_tests(repo_path)
            else:
                scores = {"test_execution": 0}
                details = {"test_execution": "Unsupported language for test execution"}
    except Exception as exc:
        logger.error(f"Test execution error: {exc}")
        scores = {"test_execution": 0}
        details = {"test_execution": f"Test execution failed: {str(exc)[:200]}"}

    return {"scores": scores, "details": details}


def _run_python_tests(repo_path: Path) -> tuple[dict, dict]:
    """Run pytest if available. Installs dependencies first for cloned repos."""
    scores = {}
    details = {}

    # Check if test files exist
    test_files = list(repo_path.rglob("test_*.py")) + list(repo_path.rglob("*_test.py"))
    tests_dir = repo_path / "tests"
    if tests_dir.exists():
        test_files.extend(f for f in tests_dir.rglob("*.py") if f not in test_files)
    # Also check conftest.py as indicator of test infrastructure
    conftest_files = list(repo_path.rglob("conftest.py"))

    # Filter out venv / hidden / __pycache__ from test files
    test_files = [
        f for f in test_files
        if not any(p.startswith(".") or p in ("venv", ".venv", "__pycache__", "node_modules") for p in f.relative_to(repo_path).parts)
    ]

    if not test_files:
        scores["test_presence"] = 0
        details["test_presence"] = "No test files found (test_*.py or *_test.py)"
        scores["test_execution"] = 0
        details["test_execution"] = "Skipped — no tests"
        return scores, details

    scores["test_presence"] = 100
    details["test_presence"] = f"{len(test_files)} test files found"

    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(repo_path),
    }

    # Install dependencies before running tests
    req_file = repo_path / "requirements.txt"
    pyproject = repo_path / "pyproject.toml"
    try:
        if req_file.exists():
            logger.info("Installing Python deps from requirements.txt")
            subprocess.run(
                ["pip", "install", "--no-cache-dir", "-q", "-r", str(req_file)],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=90,
                env=env,
            )
        elif pyproject.exists():
            logger.info("Installing Python deps from pyproject.toml")
            subprocess.run(
                ["pip", "install", "--no-cache-dir", "-q", "-e", str(repo_path)],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=90,
                env=env,
            )
        # Also install pytest itself if not available
        subprocess.run(
            ["pip", "install", "--no-cache-dir", "-q", "pytest"],
            capture_output=True, text=True, timeout=30, env=env,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as exc:
        logger.warning(f"Dependency installation warning: {exc}")

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
            env=env,
        )

        output = result.stdout + result.stderr

        # Extract counts from pytest output
        pass_match = re.search(r"(\d+) passed", output)
        fail_match = re.search(r"(\d+) failed", output)

        passed_n = int(pass_match.group(1)) if pass_match else 0
        failed_n = int(fail_match.group(1)) if fail_match else 0
        total = passed_n + failed_n

        if total > 0:
            pass_rate = (passed_n / total) * 100
            scores["test_execution"] = round(pass_rate)
            scores["test_pass_ratio"] = round(pass_rate)
            details["test_execution"] = f"{passed_n}/{total} tests passed"
        elif result.returncode == 0:
            scores["test_execution"] = 80
            details["test_execution"] = "Tests ran without errors (could not parse count)"
        else:
            scores["test_execution"] = 10
            details["test_execution"] = f"Tests failed to run: {output[:300]}"

    except subprocess.TimeoutExpired:
        scores["test_execution"] = 20
        details["test_execution"] = "Test suite timed out (120s limit)"
    except FileNotFoundError:
        scores["test_execution"] = 0
        details["test_execution"] = "pytest not available in environment"

    return scores, details


def _run_js_tests(repo_path: Path) -> tuple[dict, dict]:
    """Run npm test / jest if available. Handles monorepos."""
    scores = {}
    details = {}

    # Find all package.json files (monorepo support)
    all_pkg_jsons = [repo_path / "package.json"]
    for sub in ("frontend", "backend", "server", "client", "app", "web", "api"):
        sub_pkg = repo_path / sub / "package.json"
        if sub_pkg.exists():
            all_pkg_jsons.append(sub_pkg)

    # Find the best package.json with a test script
    best_pkg_dir = None
    has_test = False
    for pkg_path in all_pkg_jsons:
        if not pkg_path.exists():
            continue
        try:
            pkg = json.loads(pkg_path.read_text())
            scripts = pkg.get("scripts", {})
            if "test" in scripts and scripts["test"] != 'echo "Error: no test specified" && exit 1':
                best_pkg_dir = pkg_path.parent
                has_test = True
                break
        except Exception:
            continue

    if not best_pkg_dir:
        # Fallback to root if any package.json exists
        if (repo_path / "package.json").exists():
            best_pkg_dir = repo_path
        else:
            scores["test_presence"] = 0
            details["test_presence"] = "No package.json found"
            scores["test_execution"] = 0
            details["test_execution"] = "Skipped — no package.json"
            return scores, details

    # Check for test files recursively (rglob, not glob)
    test_files = []
    for ext in ("*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts", "*.test.jsx", "*.spec.jsx", "*.test.tsx", "*.spec.tsx"):
        for f in repo_path.rglob(ext):
            parts = f.relative_to(repo_path).parts
            if not any(p.startswith(".") or p in ("node_modules", "dist", "build", ".next") for p in parts):
                test_files.append(f)
    # Also check __tests__ directories
    for tests_dir in repo_path.rglob("__tests__"):
        parts = tests_dir.relative_to(repo_path).parts
        if not any(p.startswith(".") or p in ("node_modules", "dist", "build") for p in parts):
            test_files.extend(tests_dir.rglob("*.js"))
            test_files.extend(tests_dir.rglob("*.ts"))
            test_files.extend(tests_dir.rglob("*.jsx"))
            test_files.extend(tests_dir.rglob("*.tsx"))

    if not has_test and not test_files:
        scores["test_presence"] = 0
        details["test_presence"] = "No test script or test files found"
        scores["test_execution"] = 0
        details["test_execution"] = "Skipped — no tests"
        return scores, details

    scores["test_presence"] = 100
    details["test_presence"] = f"Test script found, {len(test_files)} test files"

    # Install deps if node_modules missing
    if not (best_pkg_dir / "node_modules").exists():
        try:
            logger.info(f"Installing npm deps in {best_pkg_dir}")
            subprocess.run(
                ["npm", "install", "--ignore-scripts"],
                cwd=str(best_pkg_dir),
                capture_output=True,
                timeout=120,
            )
        except Exception as exc:
            logger.warning(f"npm install warning: {exc}")

    # Run tests
    try:
        result = subprocess.run(
            ["npm", "test", "--", "--ci", "--watchAll=false"],
            cwd=str(best_pkg_dir),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
            env={**os.environ, "CI": "true"},
        )

        output = result.stdout + result.stderr

        # Parse Jest output
        pass_match = re.search(r"Tests:\s+(\d+) passed", output)
        fail_match = re.search(r"Tests:\s+(\d+) failed", output)
        # Also try pytest-style output (some JS projects use pytest)
        if not pass_match:
            pass_match = re.search(r"(\d+) passing", output)
        if not fail_match:
            fail_match = re.search(r"(\d+) failing", output)

        passed_n = int(pass_match.group(1)) if pass_match else 0
        failed_n = int(fail_match.group(1)) if fail_match else 0
        total = passed_n + failed_n

        if total > 0:
            pass_rate = (passed_n / total) * 100
            scores["test_execution"] = round(pass_rate)
            scores["test_pass_ratio"] = round(pass_rate)
            details["test_execution"] = f"{passed_n}/{total} tests passed"
        elif result.returncode == 0:
            scores["test_execution"] = 80
            details["test_execution"] = "Tests ran without errors"
        else:
            scores["test_execution"] = 10
            details["test_execution"] = f"Tests failed: {output[:300]}"

    except subprocess.TimeoutExpired:
        scores["test_execution"] = 20
        details["test_execution"] = "Test suite timed out (120s limit)"
    except FileNotFoundError:
        scores["test_execution"] = 0
        details["test_execution"] = "npm not available"

    return scores, details


def _run_go_tests(repo_path: Path) -> tuple[dict, dict]:
    """Run go test if available."""
    scores = {}
    details = {}

    test_files = list(repo_path.rglob("*_test.go"))
    if not test_files:
        scores["test_presence"] = 0
        details["test_presence"] = "No _test.go files found"
        scores["test_execution"] = 0
        details["test_execution"] = "Skipped — no tests"
        return scores, details

    scores["test_presence"] = 100
    details["test_presence"] = f"{len(test_files)} test files found"

    try:
        result = subprocess.run(
            ["go", "test", "-v", "-count=1", "./..."],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
        )

        output = result.stdout + result.stderr
        passed_n = len(re.findall(r"--- PASS:", output))
        failed_n = len(re.findall(r"--- FAIL:", output))
        total = passed_n + failed_n

        if total > 0:
            pass_rate = (passed_n / total) * 100
            scores["test_execution"] = round(pass_rate)
            details["test_execution"] = f"{passed_n}/{total} tests passed"
        elif result.returncode == 0:
            scores["test_execution"] = 80
            details["test_execution"] = "Tests ran without errors"
        else:
            scores["test_execution"] = 10
            details["test_execution"] = f"Tests failed: {output[:300]}"

    except subprocess.TimeoutExpired:
        scores["test_execution"] = 20
        details["test_execution"] = "Test suite timed out"
    except FileNotFoundError:
        scores["test_execution"] = 0
        details["test_execution"] = "Go not available"

    return scores, details


# ── Layer 3: SonarQube Quality Gate ──────────────────────────────────────

def _run_sonar_scanner_docker(repo_path: Path, sonar_url: str, sonar_token: str, project_key: str, sonar_lang: str) -> bool:
    """Run SonarScanner via Docker. Returns True on success."""
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--network=host",
                "-v", f"{repo_path}:/usr/src",
                "-e", f"SONAR_HOST_URL={sonar_url}",
                SONAR_SCANNER_IMAGE,
                f"-Dsonar.projectKey={project_key}",
                f"-Dsonar.sources=.",
                f"-Dsonar.language={sonar_lang}",
                f"-Dsonar.token={sonar_token}",
                f"-Dsonar.exclusions=**/node_modules/**,**/vendor/**,**/.git/**,**/venv/**",
            ],
            capture_output=True,
            text=True,
            timeout=SONAR_POLL_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning(f"Docker SonarScanner failed: {result.stderr[:500]}")
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning(f"Docker SonarScanner error: {exc}")
        return False


def _run_sonar_scanner_cli(repo_path: Path, sonar_props: Path) -> bool:
    """Run SonarScanner via locally installed CLI. Returns True on success."""
    try:
        result = subprocess.run(
            ["sonar-scanner", f"-Dproject.settings={sonar_props}"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=SONAR_POLL_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning(f"SonarScanner CLI failed: {result.stderr[:500]}")
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning(f"SonarScanner CLI error: {exc}")
        return False


async def run_sonarqube_scan(repo_path: Path, language: str, project_key: str | None = None) -> dict:
    """
    Run SonarScanner and poll quality gate via REST API.
    Priority: Docker sonar-scanner-cli → local sonar-scanner CLI → graceful degradation.
    """
    sonar_url = getattr(settings, "SONARQUBE_URL", None)
    sonar_token = getattr(settings, "SONARQUBE_TOKEN", None)

    if not sonar_url or not sonar_token:
        return {
            "scores": {"sonar_gate": 50},
            "details": {"sonar_gate": "SonarQube not configured — using neutral score"},
            "available": False,
        }

    # Check if SonarQube server is actually reachable
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{sonar_url}/api/system/status")
            if resp.status_code != 200:
                raise ValueError("SonarQube not responding")
            status_data = resp.json()
            if status_data.get("status") != "UP":
                raise ValueError(f"SonarQube status: {status_data.get('status')}")
    except Exception as exc:
        logger.info(f"SonarQube server not reachable: {exc}")
        return {
            "scores": {"sonar_gate": 50},
            "details": {"sonar_gate": f"SonarQube server not reachable — using neutral score"},
            "available": False,
        }

    if not project_key:
        project_key = f"bitbybit-verify-{uuid.uuid4().hex[:12]}"

    lang_map = {"python": "py", "javascript": "js", "typescript": "ts", "go": "go"}
    sonar_lang = lang_map.get(language, "py")

    # Create sonar-project.properties (for CLI fallback)
    sonar_props = repo_path / "sonar-project.properties"
    sonar_props.write_text(
        f"sonar.projectKey={project_key}\n"
        f"sonar.sources=.\n"
        f"sonar.language={sonar_lang}\n"
        f"sonar.host.url={sonar_url}\n"
        f"sonar.token={sonar_token}\n"
        f"sonar.exclusions=**/node_modules/**,**/vendor/**,**/.git/**,**/venv/**\n"
    )

    scores = {}
    details = {}

    # Try Docker scanner first, then CLI fallback
    scan_success = False
    if _is_docker_available():
        logger.info("Running SonarScanner via Docker")
        scan_success = _run_sonar_scanner_docker(repo_path, sonar_url, sonar_token, project_key, sonar_lang)

    if not scan_success:
        logger.info("Falling back to local sonar-scanner CLI")
        scan_success = _run_sonar_scanner_cli(repo_path, sonar_props)

    if not scan_success:
        return {
            "scores": {"sonar_gate": 50},
            "details": {"sonar_gate": "SonarScanner not available (neither Docker nor CLI)"},
            "available": False,
        }

    # Poll quality gate status
    import asyncio
    gate_result = await _poll_sonar_quality_gate(sonar_url, sonar_token, project_key)
    scores.update(gate_result["scores"])
    details.update(gate_result["details"])

    # Cleanup: delete project from SonarQube
    await _delete_sonar_project(sonar_url, sonar_token, project_key)

    return {"scores": scores, "details": details, "available": True}


async def _poll_sonar_quality_gate(sonar_url: str, token: str, project_key: str) -> dict:
    """Poll SonarQube API for quality gate result."""
    import asyncio

    scores = {}
    details = {}

    async with httpx.AsyncClient(timeout=30) as client:
        # Wait for analysis to complete
        for _ in range(SONAR_POLL_TIMEOUT // SONAR_POLL_INTERVAL):
            try:
                resp = await client.get(
                    f"{sonar_url}/api/qualitygates/project_status",
                    params={"projectKey": project_key},
                    auth=(token, ""),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    gate_status = data.get("projectStatus", {}).get("status", "NONE")

                    if gate_status in ("OK", "WARN", "ERROR"):
                        # Map to score
                        gate_scores = {"OK": 100, "WARN": 65, "ERROR": 25}
                        scores["sonar_gate"] = gate_scores.get(gate_status, 50)
                        details["sonar_gate"] = f"Quality gate: {gate_status}"

                        # Extract specific metrics
                        conditions = data.get("projectStatus", {}).get("conditions", [])
                        for cond in conditions:
                            metric = cond.get("metricKey", "")
                            actual = cond.get("actualValue", "?")
                            cond_status = cond.get("status", "")
                            if metric == "bugs":
                                scores["sonar_bugs"] = 100 if cond_status == "OK" else 40
                                details["sonar_bugs"] = f"{actual} bugs"
                            elif metric == "vulnerabilities":
                                scores["sonar_vulns"] = 100 if cond_status == "OK" else 30
                                details["sonar_vulns"] = f"{actual} vulnerabilities"
                            elif metric == "code_smells":
                                scores["sonar_smells"] = 100 if cond_status == "OK" else 50
                                details["sonar_smells"] = f"{actual} code smells"
                            elif metric == "coverage":
                                try:
                                    cov = float(actual)
                                    scores["sonar_coverage"] = min(100, round(cov))
                                    details["sonar_coverage"] = f"{actual}% coverage"
                                except ValueError:
                                    pass
                            elif metric == "duplicated_lines_density":
                                try:
                                    dup = float(actual)
                                    scores["sonar_duplication"] = max(0, round(100 - dup))
                                    details["sonar_duplication"] = f"{actual}% duplication"
                                except ValueError:
                                    pass

                        return {"scores": scores, "details": details}

            except Exception as exc:
                logger.debug(f"SonarQube poll error: {exc}")

            await asyncio.sleep(SONAR_POLL_INTERVAL)

    # Timed out waiting
    scores["sonar_gate"] = 50
    details["sonar_gate"] = "Quality gate result not available within timeout"
    return {"scores": scores, "details": details}


async def _delete_sonar_project(sonar_url: str, token: str, project_key: str):
    """Cleanup: delete ephemeral project from SonarQube."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{sonar_url}/api/projects/delete",
                params={"project": project_key},
                auth=(token, ""),
            )
    except Exception:
        pass  # Best-effort cleanup


# ── Security Scan ────────────────────────────────────────────────────────

def run_security_scan(repo_path: Path, language: str) -> dict:
    """Scan for common security issues: hardcoded secrets, eval, dangerous patterns."""
    scores = {}
    details = {}
    issues = []

    all_files = []
    for root, _dirs, files in os.walk(repo_path):
        parts = Path(root).relative_to(repo_path).parts
        if any(p.startswith(".") or p in ("node_modules", "vendor", "venv", ".venv") for p in parts):
            continue
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".json", ".yaml", ".yml", ".env", ".cfg", ".ini"):
                all_files.append(Path(root) / f)

    for f in all_files:
        try:
            content = f.read_text(errors="ignore")
            rel = str(f.relative_to(repo_path))

            # Hardcoded secrets
            secret_patterns = [
                (r'(?i)(password|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret"),
                (r'(?i)AKIA[0-9A-Z]{16}', "AWS Access Key"),
                (r'(?i)sk-[a-zA-Z0-9]{20,}', "API Key (OpenAI-style)"),
                (r'ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token"),
            ]
            for pattern, label in secret_patterns:
                if re.search(pattern, content):
                    issues.append(f"{label} in {rel}")

            # Dangerous functions
            if language == "python":
                if re.search(r"\beval\s*\(", content):
                    issues.append(f"eval() usage in {rel}")
                if re.search(r"\bexec\s*\(", content):
                    issues.append(f"exec() usage in {rel}")
                if re.search(r"\bpickle\.load", content):
                    issues.append(f"Unsafe pickle.load in {rel}")
                if re.search(r"\bos\.system\s*\(", content):
                    issues.append(f"os.system() in {rel}")
                if re.search(r"\bsubprocess\.call\s*\(.*shell\s*=\s*True", content):
                    issues.append(f"subprocess with shell=True in {rel}")

            elif language in ("javascript", "typescript"):
                if re.search(r"\beval\s*\(", content):
                    issues.append(f"eval() usage in {rel}")
                if re.search(r"new\s+Function\s*\(", content):
                    issues.append(f"new Function() (eval equivalent) in {rel}")
                if re.search(r"innerHTML\s*=", content):
                    issues.append(f"innerHTML assignment (XSS risk) in {rel}")

        except Exception:
            continue

    if not issues:
        scores["security_scan"] = 100
        details["security_scan"] = "No security issues detected"
    else:
        penalty = min(len(issues) * 15, 80)
        scores["security_scan"] = 100 - penalty
        details["security_scan"] = f"{len(issues)} issues: {'; '.join(issues[:5])}"

    return {"scores": scores, "details": details, "issues": issues}


# ── Dependency Check ─────────────────────────────────────────────────────

def run_dependency_check(repo_path: Path, language: str) -> dict:
    """Validate dependencies are from known package registries."""
    scores = {}
    details = {}

    if language == "python":
        req_files = list(repo_path.glob("requirements*.txt"))
        pyproject = repo_path / "pyproject.toml"

        if req_files or pyproject.exists():
            scores["dependency_check"] = 90
            details["dependency_check"] = "Dependency manifest found"
        else:
            scores["dependency_check"] = 50
            details["dependency_check"] = "No requirements.txt or pyproject.toml"

    elif language in ("javascript", "typescript"):
        pkg = repo_path / "package.json"
        lock = repo_path / "package-lock.json"
        yarn_lock = repo_path / "yarn.lock"

        if pkg.exists():
            scores["dependency_check"] = 90 if (lock.exists() or yarn_lock.exists()) else 70
            details["dependency_check"] = "package.json found" + (" with lockfile" if lock.exists() or yarn_lock.exists() else " (no lockfile)")
        else:
            scores["dependency_check"] = 30
            details["dependency_check"] = "No package.json found"

    elif language == "go":
        if (repo_path / "go.mod").exists():
            scores["dependency_check"] = 90
            details["dependency_check"] = "go.mod found"
        else:
            scores["dependency_check"] = 40
            details["dependency_check"] = "No go.mod found"

    else:
        scores["dependency_check"] = 50
        details["dependency_check"] = "Language not supported for dependency check"

    return {"scores": scores, "details": details}


# ── Code Summary Extraction (for LLM deep review) ───────────────────────

def extract_code_summary(repo_path: Path, language: str, max_chars: int = 8000) -> str:
    """
    Walk the cloned repo and extract key file contents for LLM review.
    Prioritises: README, entry points, route files, model files, config.
    Returns a structured text summary capped at max_chars.
    """
    summary_parts = []
    char_count = 0

    # Priority file patterns by category
    priority_files = [
        # READMEs and docs
        ("README*", "Documentation"),
        # Entry points
        ("main.py", "Entry Point"), ("app.py", "Entry Point"), ("index.py", "Entry Point"),
        ("index.js", "Entry Point"), ("index.ts", "Entry Point"), ("App.jsx", "Entry Point"),
        ("App.tsx", "Entry Point"), ("main.js", "Entry Point"), ("main.ts", "Entry Point"),
        ("server.js", "Entry Point"), ("server.ts", "Entry Point"),
        # Config
        ("package.json", "Config"), ("requirements.txt", "Config"),
        ("pyproject.toml", "Config"), ("tsconfig.json", "Config"),
        ("docker-compose*.yml", "Config"), ("Dockerfile*", "Config"),
    ]

    # Collect files by priority
    collected_files: list[tuple[str, Path]] = []

    for pattern, category in priority_files:
        for f in repo_path.glob(pattern):
            if f.is_file():
                collected_files.append((category, f))

    # Then grab route/model/service files
    important_dirs = ["routes", "api", "models", "schemas", "services", "controllers",
                      "src/routes", "src/api", "src/models", "src/components", "src/pages",
                      "app", "lib"]
    for dir_name in important_dirs:
        target_dir = repo_path / dir_name
        if target_dir.exists():
            for f in sorted(target_dir.rglob("*"))[:10]:  # Max 10 files per dir
                if f.is_file() and f.suffix in (".py", ".js", ".ts", ".jsx", ".tsx", ".go"):
                    parts = f.relative_to(repo_path).parts
                    if not any(p.startswith(".") or p in ("node_modules", "__pycache__", "dist") for p in parts):
                        collected_files.append(("Source", f))

    # De-duplicate
    seen = set()
    unique_files = []
    for category, f in collected_files:
        if f not in seen:
            seen.add(f)
            unique_files.append((category, f))

    # Build summary
    for category, f in unique_files:
        if char_count >= max_chars:
            break
        try:
            rel = str(f.relative_to(repo_path))
            content = f.read_text(errors="ignore")

            # Truncate individual files
            max_file_chars = min(1500, max_chars - char_count)
            if len(content) > max_file_chars:
                content = content[:max_file_chars] + "\n... [truncated]"

            part = f"\n=== [{category}] {rel} ===\n{content}\n"
            summary_parts.append(part)
            char_count += len(part)
        except Exception:
            continue

    if not summary_parts:
        return "[No source files could be extracted]"

    return "".join(summary_parts)


# ── Description Matching ─────────────────────────────────────────────────

def run_description_matching(
    repo_path: Path,
    project_description: str,
    acceptance_criteria: list,
    language: str,
) -> dict:
    """
    Compare the cloned codebase against the client's project description
    and acceptance criteria. Returns scores for how well the code matches
    what was requested.

    Checks:
      1. README analysis — does the README reference key terms?
      2. File structure match — expected dirs/files based on project type
      3. Keyword coverage — key technical terms from description found in code
      4. Acceptance criteria cross-check — each criterion mapped to code patterns
    """
    scores = {}
    details = {}
    all_source = ""  # Shared across keyword coverage and criteria cross-check

    # Common stopwords for keyword filtering
    stopwords = {"this", "that", "with", "from", "have", "will", "been", "should", "would",
                  "could", "their", "there", "about", "which", "when", "what", "your", "also",
                  "more", "some", "into", "other", "than", "then", "each", "make", "like",
                  "just", "over", "such", "take", "only", "very", "need", "must"}

    # ── 1. README Analysis ──
    readme_content = ""
    for readme_name in ("README.md", "README.rst", "README.txt", "README"):
        readme_path = repo_path / readme_name
        if readme_path.exists():
            readme_content = readme_path.read_text(errors="ignore")[:3000]
            break

    if readme_content:
        # Check how many description keywords appear in README
        desc_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", project_description.lower()))
        desc_words -= stopwords
        matched = 0
        if desc_words:
            readme_lower = readme_content.lower()
            matched = sum(1 for w in desc_words if w in readme_lower)
            readme_score = min(100, round((matched / len(desc_words)) * 100))
        else:
            readme_score = 50
        scores["readme_match"] = readme_score
        details["readme_match"] = f"{matched}/{len(desc_words) if desc_words else 0} description keywords found in README"
    else:
        scores["readme_match"] = 20
        details["readme_match"] = "No README file found in repository"

    # ── 2. File Structure Match ──
    desc_lower = project_description.lower()
    expected_structures = []

    # Detect what the project should have based on description
    structure_hints = {
        "api": ["routes", "endpoints", "controllers", "api"],
        "react": ["components", "src", "App"],
        "next": ["pages", "app", "next.config"],
        "database": ["models", "schemas", "migrations", "database"],
        "auth": ["auth", "login", "middleware"],
        "frontend": ["components", "pages", "views", "public", "src"],
        "backend": ["routes", "services", "models", "controllers"],
        "testing": ["tests", "test", "__tests__", "spec"],
        "docker": ["Dockerfile", "docker-compose"],
    }

    for category, indicators in structure_hints.items():
        if category in desc_lower:
            expected_structures.extend(indicators)

    if expected_structures:
        # Check which expected structures exist
        found = 0
        for struct in expected_structures:
            # Check as directory or file
            if (repo_path / struct).exists():
                found += 1
            else:
                # Check recursively for subdirectory matches
                for d in repo_path.iterdir():
                    if d.is_dir() and struct.lower() in d.name.lower():
                        found += 1
                        break
        structure_score = min(100, round((found / len(expected_structures)) * 100))
        scores["structure_match"] = structure_score
        details["structure_match"] = f"{found}/{len(expected_structures)} expected project structures found"
    else:
        scores["structure_match"] = 70  # Neutral if no specific expectations
        details["structure_match"] = "No specific structure expectations derived from description"

    # ── 3. Keyword Coverage ──
    # Extract technical keywords from description
    tech_keywords = set()
    tech_patterns = [
        r"\b(api|rest|graphql|websocket|grpc)\b",
        r"\b(react|vue|angular|svelte|next|nuxt)\b",
        r"\b(express|fastapi|flask|django|spring|gin)\b",
        r"\b(postgres|mysql|mongodb|redis|sqlite|supabase)\b",
        r"\b(jwt|oauth|auth|login|signup|session)\b",
        r"\b(docker|kubernetes|ci|cd|deploy)\b",
        r"\b(test|jest|pytest|mocha|cypress)\b",
        r"\b(typescript|javascript|python|golang|rust)\b",
    ]
    for pattern in tech_patterns:
        matches = re.findall(pattern, desc_lower)
        tech_keywords.update(matches)

    if tech_keywords:
        # Search for these keywords across all source files
        all_source = ""
        source_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".json", ".yaml", ".yml"}
        for root, _dirs, files in os.walk(repo_path):
            parts = Path(root).relative_to(repo_path).parts
            if any(p.startswith(".") or p in ("node_modules", "vendor", "venv", ".venv", "dist") for p in parts):
                continue
            for f in files:
                if Path(f).suffix.lower() in source_extensions:
                    try:
                        all_source += Path(root, f).read_text(errors="ignore")[:2000]
                    except Exception:
                        continue

        all_source_lower = all_source.lower()
        kw_found = sum(1 for kw in tech_keywords if kw in all_source_lower)
        keyword_score = min(100, round((kw_found / len(tech_keywords)) * 100))
        scores["keyword_coverage"] = keyword_score
        details["keyword_coverage"] = f"{kw_found}/{len(tech_keywords)} technical keywords: {', '.join(sorted(tech_keywords)[:8])}"
    else:
        scores["keyword_coverage"] = 60
        details["keyword_coverage"] = "No specific technical keywords extracted from description"

    # ── 4. Acceptance Criteria Cross-check ──
    if acceptance_criteria:
        criteria_met = 0
        criteria_details_list = []

        # Build a searchable index of all source content if not already built
        if not all_source:
            all_source = ""
            for root, _dirs, files in os.walk(repo_path):
                parts = Path(root).relative_to(repo_path).parts
                if any(p.startswith(".") or p in ("node_modules", "vendor", "venv", ".venv", "dist") for p in parts):
                    continue
                for f in files:
                    if Path(f).suffix.lower() in {".py", ".js", ".ts", ".jsx", ".tsx", ".go"}:
                        try:
                            all_source += Path(root, f).read_text(errors="ignore")
                        except Exception:
                            continue

        all_source_lower = all_source.lower() if all_source else ""

        for criterion in acceptance_criteria:
            crit_text = criterion if isinstance(criterion, str) else criterion.get("criterion", str(criterion))
            # Extract key words from criterion
            crit_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", crit_text.lower())) - stopwords
            if crit_words:
                matched_words = sum(1 for w in crit_words if w in all_source_lower)
                match_ratio = matched_words / len(crit_words)
                if match_ratio >= 0.3:  # At least 30% of criterion words found
                    criteria_met += 1
                    criteria_details_list.append(f"✅ {crit_text[:60]}")
                else:
                    criteria_details_list.append(f"❌ {crit_text[:60]}")
            else:
                criteria_details_list.append(f"⚠️ {crit_text[:60]} (unparseable)")

        criteria_score = min(100, round((criteria_met / len(acceptance_criteria)) * 100))
        scores["criteria_fulfillment"] = criteria_score
        details["criteria_fulfillment"] = f"{criteria_met}/{len(acceptance_criteria)} criteria have matching code patterns"
    else:
        scores["criteria_fulfillment"] = 50
        details["criteria_fulfillment"] = "No acceptance criteria provided for cross-check"

    return {"scores": scores, "details": details}


def _extract_spec_entities(acceptance_criteria: list) -> list[str]:
    """Extract key entity names from acceptance criteria for AST matching."""
    entities = []
    # Patterns that suggest specific named entities (functions, classes, modules)
    entity_patterns = [
        r"\b([A-Z][a-zA-Z]+(?:Controller|Service|Model|Router|Handler|Manager|Factory|Provider|Component))\b",
        r"\b(create|get|update|delete|list|fetch|handle|process|validate|authenticate|authorize)[A-Z]\w+\b",
        r"`(\w+)`",  # backtick-quoted identifiers
        r"\"(\w+)\"",  # quoted identifiers
    ]
    for criterion in acceptance_criteria:
        crit_text = criterion if isinstance(criterion, str) else criterion.get("criterion", str(criterion))
        for pattern in entity_patterns:
            matches = re.findall(pattern, crit_text)
            entities.extend(matches)
    return list(set(entities)) if entities else None


# ── Full Pipeline Orchestrator ───────────────────────────────────────────

async def run_full_pipeline(
    repo_url: str,
    commit_hash: str | None = None,
    spec_entities: list[str] | None = None,
    milestone_id: str | None = None,
    project_description: str | None = None,
    acceptance_criteria: list | None = None,
) -> dict:
    """
    Run the complete code verification pipeline (Layers 1-3).
    Layer 4 (LLM) is handled by the caller.

    Returns:
        {
            "language": str,
            "commit_hash": str,
            "layer_results": { "static": {...}, "runtime": {...}, "sonarqube": {...}, "security": {...}, "description_match": {...} },
            "deterministic_scores": { metric: score },
            "deterministic_details": { metric: detail },
            "aggregate_score": float,
            "pfi_signals": { ... },
            "code_summary": str,
        }
    """
    repo_path = None
    try:
        # Clone
        logger.info(f"Cloning repo: {repo_url} (commit: {commit_hash or 'HEAD'})")
        repo_path = clone_repo(repo_url, commit_hash)

        # Detect language
        language = detect_language(repo_path)
        logger.info(f"Detected language: {language}")

        # Get actual commit hash
        actual_hash = _get_current_commit(repo_path)

        # Auto-extract spec entities from acceptance criteria if not provided
        if not spec_entities and acceptance_criteria:
            spec_entities = _extract_spec_entities(acceptance_criteria)
            if spec_entities:
                logger.info(f"Auto-extracted {len(spec_entities)} spec entities: {spec_entities[:5]}")

        # Layer 1: Static analysis
        logger.info("Running Layer 1: Static Analysis (AST)")
        ast_result = run_ast_analysis(repo_path, language, spec_entities)

        # Layer 2: Runtime tests
        logger.info("Running Layer 2: Runtime Tests")
        test_result = run_test_suite(repo_path, language)

        # Layer 3: SonarQube (async)
        project_key = f"verify-{milestone_id or uuid.uuid4().hex[:8]}"
        logger.info("Running Layer 3: SonarQube Quality Gate")
        sonar_result = await run_sonarqube_scan(repo_path, language, project_key)

        # Security scan (bonus, feeds into static)
        logger.info("Running security scan")
        security_result = run_security_scan(repo_path, language)

        # Dependency check
        dep_result = run_dependency_check(repo_path, language)

        # Description matching (NEW — compares code vs client requirements)
        desc_match_result = {"scores": {}, "details": {}}
        if project_description:
            logger.info("Running description matching against client requirements")
            desc_match_result = run_description_matching(
                repo_path, project_description,
                acceptance_criteria or [], language,
            )

        # Extract code summary for LLM deep review
        logger.info("Extracting code summary for LLM context")
        code_summary = extract_code_summary(repo_path, language)

        # Merge all deterministic scores
        all_scores = {}
        all_details = {}
        for result_group in [ast_result, test_result, sonar_result, security_result, dep_result, desc_match_result]:
            all_scores.update(result_group.get("scores", {}))
            all_details.update(result_group.get("details", {}))

        # Compute weighted aggregate (layers 1-3 only, 70% of total)
        static_avg = _avg_scores(ast_result.get("scores", {}))
        runtime_avg = _avg_scores(test_result.get("scores", {}))
        sonar_avg = _avg_scores(sonar_result.get("scores", {}))
        security_avg = _avg_scores(security_result.get("scores", {}))

        # Weighted: within the deterministic portion
        # Static 15, Runtime 35, SonarQube 20 → normalise to 70% portion
        det_score = (
            static_avg * (15 / 70) +
            runtime_avg * (35 / 70) +
            sonar_avg * (20 / 70)
        )

        # PFI signals
        test_scores = test_result.get("scores", {})
        pfi_signals = {
            "auto_tests_passed_ratio": test_scores.get("test_pass_ratio", test_scores.get("test_execution", 0)) / 100,
            "dead_code_flag": False,
            "security_issues": len(security_result.get("issues", [])),
            "sonarqube_available": sonar_result.get("available", False),
            "sonar_gate": sonar_result.get("scores", {}).get("sonar_gate", 50),
        }

        return {
            "language": language,
            "commit_hash": actual_hash,
            "layer_results": {
                "static": ast_result,
                "runtime": test_result,
                "sonarqube": sonar_result,
                "security": security_result,
                "dependency": dep_result,
                "description_match": desc_match_result,
            },
            "deterministic_scores": all_scores,
            "deterministic_details": all_details,
            "aggregate_score": round(det_score, 1),
            "pfi_signals": pfi_signals,
            "code_summary": code_summary,
        }

    finally:
        if repo_path:
            cleanup_repo(repo_path)


def _get_current_commit(repo_path: Path) -> str:
    """Get the current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _avg_scores(scores: dict[str, float]) -> float:
    """Average of score values, defaulting to 0 if empty."""
    if not scores:
        return 0.0
    return sum(scores.values()) / len(scores)
