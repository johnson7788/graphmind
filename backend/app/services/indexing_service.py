"""GraphRAG indexing service — runs graphrag init/index in background threads."""

from __future__ import annotations

import json as _json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.config import DATA_ROOT, DEFAULT_ENTITY_TYPES, get_llm_config
from app.models.schemas import ApiCheckResponse, IndexStatus
from app.utils.prompts import write_prompts
from app.utils.settings_generator import write_settings

log = logging.getLogger("graphrag-backend")

# Global status tracker: dataset_id -> IndexStatus
_index_status: dict[str, IndexStatus] = {}
_status_lock = threading.Lock()


def _set_status(dataset_id: str, **kwargs) -> None:
    """Update the indexing status for a dataset (thread-safe)."""
    with _status_lock:
        if dataset_id not in _index_status:
            _index_status[dataset_id] = IndexStatus(dataset_id=dataset_id, status="idle")
        current = _index_status[dataset_id]
        updated = current.model_dump()
        updated.update(kwargs)
        _index_status[dataset_id] = IndexStatus(**updated)
        # Log important status changes
        if kwargs.get('status') in ('completed', 'failed'):
            log.info("Status update for %s: %s", dataset_id, kwargs.get('status'))
        elif kwargs.get('progress'):
            log.debug("Progress update for %s: %s%%", dataset_id, kwargs.get('progress'))


def get_status(dataset_id: str) -> IndexStatus:
    """Return the current indexing status for a dataset."""
    with _status_lock:
        return _index_status.get(
            dataset_id,
            IndexStatus(dataset_id=dataset_id, status="idle"),
        )


def _check_api_connectivity() -> ApiCheckResponse:
    """Test both chat and embedding API endpoints for connectivity."""
    llm = get_llm_config()

    def _test_endpoint(api_base: str, api_key: str, model: str, path: str, label: str) -> str | None:
        url = api_base.rstrip("/") + path
        if path == "/chat/completions":
            body_dict = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
        else:
            body_dict = {"model": model, "input": "test"}
        body = _json.dumps(body_dict).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {api_key}")
            resp = urllib.request.urlopen(req, timeout=30)
            data = _json.loads(resp.read())
            if "choices" in data or "data" in data:
                log.info("%s connectivity check passed", label)
                return None
            return f"{label} unexpected response: {str(data)[:300]}"
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            return f"{label} failed (HTTP {e.code}): {body}"
        except Exception as e:
            return f"{label} connection failed: {e}"

    # Test chat endpoint
    chat_err = _test_endpoint(
        llm["api_base"], llm["api_key"], llm["model"],
        "/chat/completions", "Chat model",
    )

    # Test embedding endpoint
    emb_base = llm.get("emb_base") or llm["api_base"]
    emb_err = _test_endpoint(
        emb_base, llm["api_key"], llm["emb_model"],
        "/embeddings", "Embedding model",
    )

    return ApiCheckResponse(
        chat_ok=chat_err is None,
        embedding_ok=emb_err is None,
        chat_error=chat_err,
        embedding_error=emb_err,
    )


def discover_entity_types(sample_text: str) -> list[str]:
    """Call the LLM to automatically discover entity types from sample text."""
    llm = get_llm_config()
    sample = sample_text[:4000]

    prompt = """You are an expert at identifying entity types in text.
Given the following text, identify the most relevant entity types (categories) that would be useful for knowledge graph extraction.

Rules:
- Return ONLY a comma-separated list of entity type names in ENGLISH (e.g., person, organization, location, disease, drug, organ, symptom)
- Entity types should be general categories, not specific instances
- Avoid overly generic types like "other" or "thing"
- Aim for 5-12 types that best fit the content
- Entity type names MUST be in English regardless of the input text language

Text:
{sample}

Entity types (comma-separated, in English):""".format(sample=sample)

    api_key = llm["api_key"]
    base = llm["api_base"].rstrip("/")
    model = llm["model"]

    payload = _json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 256,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = _json.loads(resp.read().decode("utf-8"))

    content = data["choices"][0]["message"]["content"].strip()
    types = [t.strip() for t in content.split(",") if t.strip()]
    # Clean up formatting artifacts
    types = [t.strip('"\'[]()') for t in types]
    types = [t for t in types if t and len(t) < 30]
    return types if types else list(DEFAULT_ENTITY_TYPES)


def _snapshot_input_files(root: Path) -> dict[str, bytes]:
    """Read all files in input/ into memory so we can restore them after init."""
    input_dir = root / "input"
    log.info("Snapshotting files from: %s (exists: %s)", input_dir, input_dir.exists())

    if not input_dir.exists():
        log.warning("Input directory does not exist: %s", input_dir)
        return {}

    snapshot = {}
    try:
        for f in input_dir.iterdir():
            if f.is_file():
                snapshot[f.name] = f.read_bytes()
                log.info("  snapshot: %s (%d bytes)", f.name, len(snapshot[f.name]))
            else:
                log.info("  skipping non-file item: %s", f.name)
    except Exception as e:
        log.error("Error reading input directory %s: %s", input_dir, e, exc_info=True)

    log.info("Snapshot complete: %d files found", len(snapshot))
    return snapshot


def _restore_input_files(root: Path, snapshot: dict[str, bytes]) -> None:
    """Write saved files back to input/ after graphrag init.

    Normalizes all text file extensions (.txt, .md, .csv) to .txt since
    GraphRAG only matches the glob pattern ``*.txt``.
    """
    input_dir = root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    for name, data in snapshot.items():
        # Normalize .md / .csv → .txt (GraphRAG requires *.txt)
        p = Path(name)
        if p.suffix.lower() in (".txt", ".md", ".csv"):
            name = p.stem + ".txt"
        dest = input_dir / name
        dest.write_bytes(data)
        log.info("  restored: %s (%d bytes)", name, len(data))


def _run_index_thread(dataset_id: str, entity_types: list[str]) -> None:
    """Internal: the actual indexing work, executed in a background thread."""
    root = DATA_ROOT / dataset_id
    llm = get_llm_config()
    log_file = root / "index.log"
    et = entity_types or list(DEFAULT_ENTITY_TYPES)

    log.info("=" * 60)
    log.info("INDEXING START: dataset=%s root=%s entity_types=%s", dataset_id, root, et)
    log.info("Python: %s", sys.executable)
    log.info("LLM model=%s api_base=%s emb_model=%s emb_base=%s",
             llm["model"], llm["api_base"], llm["emb_model"], llm.get("emb_base"))
    log.info("Input directory: %s (exists: %s)", root / "input", (root / "input").exists())

    env = os.environ.copy()
    env["GRAPHRAG_API_KEY"] = llm["api_key"]

    try:
        # ── Pre-flight: verify input files exist with retry ──────────────────
        log.info("Checking input files before starting indexing...")
        input_dir = root / "input"
        max_retries = 5
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            input_snapshot = _snapshot_input_files(root)
            if input_snapshot:
                log.info("Found %d input files on attempt %d", len(input_snapshot), attempt + 1)
                break
            elif attempt < max_retries - 1:
                log.warning("No files found in %s on attempt %d, retrying...",
                           input_dir, attempt + 1)
                import time as _time
                _time.sleep(retry_delay)
            else:
                # Final attempt failed
                log.error("No files found in %s after %d attempts", input_dir, max_retries)
                _set_status(
                    dataset_id,
                    status="failed",
                    step="preflight",
                    progress=0,
                    message="No input files found",
                    error=f"No input files found in {input_dir} after {max_retries} attempts. "
                          f"Please ensure files were uploaded successfully and try again.",
                )
                return

        # ── Step 0: Skip graphrag init (we'll create prompts manually) ────
        _set_status(
            dataset_id,
            status="running",
            step="initializing",
            progress=26,
            message="Step 0/4: Preparing configuration...",
        )
        log.info("Skipping graphrag init - will create prompts manually")
        # graphrag init is non-deterministic and can fail interactively
        # We'll create the necessary structure manually instead

        # ── Step 0.5: Ensure input files exist ───────────────────────────────
        log.info("Verifying input files...")
        # Input files should already be in place from upload
        # No need to restore since we skipped graphrag init

        # Verify files exist
        input_dir = root / "input"
        txt_files = [f for f in input_dir.iterdir() if f.suffix.lower() == ".txt"]
        all_files = [f for f in input_dir.iterdir() if f.is_file()]
        log.info("Input dir contents: %s exists, %d total files, %d .txt files",
                 input_dir.exists(), len(all_files), len(txt_files))
        for f in all_files:
            try:
                log.info("  - %s (%d bytes)", f.name, f.stat().st_size)
            except Exception as e:
                log.error("  - %s (error reading file info: %s)", f.name, e)

        if not txt_files:
            log.error("ERROR: No .txt files in input/! Files: %s",
                      [f.name for f in all_files])
            _set_status(
                dataset_id,
                status="failed",
                step="preflight",
                progress=0,
                message="No .txt files in input directory",
                error=(
                    f"No .txt files found in {input_dir}. "
                    f"Files present: {[f.name for f in all_files]}. "
                    "GraphRAG requires .txt files in the input/ directory."
                ),
            )
            return

        # ── Step 1: Write custom settings.yaml ───────────────────────────
        _set_status(
            dataset_id,
            status="running",
            step="configuring",
            progress=32,
            message="Step 1/4: Writing custom configuration...",
        )
        write_settings(root, llm, et)
        log.info("Written settings.yaml")

        # ── Step 1.5: Write language-adaptive prompts ────────────────────
        _set_status(
            dataset_id,
            status="running",
            step="configuring",
            progress=38,
            message="Step 1.5/4: Writing language-adaptive prompts...",
        )
        write_prompts(root)
        log.info("Written language-adaptive prompts")

        # ── Step 2: Check API connectivity ───────────────────────────────
        _set_status(
            dataset_id,
            status="running",
            step="validating",
            progress=44,
            message="Step 2/4: Verifying API connectivity...",
        )
        api_check = _check_api_connectivity()
        log.info("API check: chat_ok=%s embedding_ok=%s", api_check.chat_ok, api_check.embedding_ok)
        if not api_check.chat_ok:
            _set_status(
                dataset_id,
                status="failed",
                step="check api",
                progress=0,
                message="API connectivity check failed",
                error=f"Chat API check failed:\n{api_check.chat_error}",
            )
            return
        if not api_check.embedding_ok:
            _set_status(
                dataset_id,
                status="failed",
                step="check api",
                progress=0,
                message="API connectivity check failed",
                error=(
                    f"Embedding API check failed:\n{api_check.embedding_error}\n\n"
                    "Chat model passed. Please check embedding configuration."
                ),
            )
            return

        # ── Step 3: graphrag index (main work) ──────────────────────────
        _set_status(
            dataset_id,
            status="running",
            step="building",
            progress=50,
            message="Step 3/4: Building knowledge graph...",
        )
        log.info("Running: graphrag index --root %s", root)
        log.info("Working directory: %s", root)
        log.info("Input files present: %s", [f.name for f in (root / "input").iterdir()])

        # Workflow progress mapping: (base_pct, weight) within index phase (50→95)
        import re as _re
        _WF_BASE = 50
        _WF_SPAN = 45  # 50→95
        _WF_MAP: list[tuple[str, float]] = [
            ("load_input_documents",     0.02),
            ("create_base_text_units",   0.04),
            ("create_final_documents",   0.02),
            ("extract_graph",            0.48),
            ("finalize_graph",           0.04),
            ("extract_covariates",       0.08),
            ("create_communities",       0.08),
            ("create_final_text_units",  0.04),
            ("create_community_reports", 0.10),
            ("generate_text_embeddings", 0.10),
        ]
        _wf_index: dict[str, tuple[int, float]] = {}
        _cum = 0.0
        for _i, (_name, _w) in enumerate(_WF_MAP):
            _wf_index[_name] = (_i, _cum)
            _cum += _w
        _TOTAL_WF = len(_WF_MAP)

        # Match fraction patterns like "42/118", " 42 / 118 ...", "Progress: 42/118"
        _progress_sub = _re.compile(r"\b(\d+)\s*/\s*(\d+)\b")
        _workflow_re = _re.compile(r"Starting workflow:\s+(.+)")

        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write("=== graphrag index log ===\n")
            lf.flush()
            proc = subprocess.Popen(
                [sys.executable, "-m", "graphrag", "index", "--root", str(root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=str(root),
            )
            lines_collected = 0
            last_update = time.time()
            current_wf: str | None = None
            current_wf_idx = 0
            wf_start_time = 0.0
            last_sub_progress_pct = _WF_BASE  # track last known sub-progress value

            try:
                for line in proc.stdout:
                    lf.write(line)
                    lf.flush()
                    lines_collected += 1

                    # Detect workflow transitions
                    _wm = _workflow_re.search(line)
                    if _wm:
                        _name = _wm.group(1).strip()
                        current_wf = _name
                        wf_start_time = time.time()
                        if _name in _wf_index:
                            current_wf_idx, _cum_start = _wf_index[_name]
                            _base_pct = _WF_BASE + round(_cum_start * _WF_SPAN)
                            last_sub_progress_pct = _base_pct
                            _set_status(
                                dataset_id,
                                status="running",
                                step="building",
                                progress=_base_pct,
                                message=f"Step 3/4: {_name} ({current_wf_idx + 1}/{_TOTAL_WF})",
                            )

                    # Parse sub-progress within current workflow (e.g. "  42 / 118 ...")
                    _pm = _progress_sub.search(line)
                    if _pm and current_wf and current_wf in _wf_index:
                        _cur = int(_pm.group(1))
                        _tot = int(_pm.group(2))
                        if _tot > 0:
                            _idx, _cum_start = _wf_index[current_wf]
                            _wf_weight = _WF_MAP[_idx][1]
                            _sub = _cur / _tot
                            _pct = _WF_BASE + round((_cum_start + _sub * _wf_weight) * _WF_SPAN)
                            _pct = min(_pct, 94)  # cap before final workflows
                            if _pct > last_sub_progress_pct:
                                last_sub_progress_pct = _pct
                                _set_status(
                                    dataset_id,
                                    status="running",
                                    step="building",
                                    progress=_pct,
                                    message=f"Step 3/4: {current_wf} ({_cur}/{_tot}) [{current_wf_idx + 1}/{_TOTAL_WF}]",
                                )

                    now = time.time()
                    if now - last_update >= 3:
                        last_update = now
                        # Fallback: always active, uses different heuristics depending on state
                        if current_wf and current_wf in _wf_index:
                            # Inside a known workflow but no sub-progress matched.
                            # Advance slowly based on elapsed time to avoid frozen progress.
                            _idx, _cum_start = _wf_index[current_wf]
                            _wf_weight = _WF_MAP[_idx][1]
                            _elapsed_in_wf = now - wf_start_time if wf_start_time > 0 else 0
                            # Trickle at ~1% per 10 seconds within current workflow's range
                            _trickle_pct = int(_elapsed_in_wf / 10)
                            _max_wf_pct = round(_wf_weight * _WF_SPAN)
                            _trickle_pct = min(_trickle_pct, _max_wf_pct - 2)
                            _pct = _WF_BASE + round(_cum_start * _WF_SPAN) + _trickle_pct
                            _pct = min(_pct, 94)
                            if _pct > last_sub_progress_pct:
                                _set_status(
                                    dataset_id,
                                    status="running",
                                    step="building",
                                    progress=_pct,
                                    message=f"Step 3/4: {current_wf} (elapsed {int(_elapsed_in_wf)}s) [{current_wf_idx + 1}/{_TOTAL_WF}]",
                                )
                        elif lines_collected > 5:
                            # Before first workflow detected — use line-count heuristic
                            _pct = min(_WF_BASE + lines_collected // 5, 94)
                            if _pct > last_sub_progress_pct:
                                _set_status(
                                    dataset_id,
                                    status="running",
                                    step="building",
                                    progress=_pct,
                                    message=f"Step 3/4: Building knowledge graph... ({lines_collected} lines output)",
                                )

                proc.wait(timeout=3600)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                _set_status(
                    dataset_id,
                    status="failed",
                    step="building",
                    progress=0,
                    message="Index timed out (>60 minutes)",
                    error="Indexing timed out (>60 minutes). Check API connectivity or try smaller files.",
                )
                return

        log.info("graphrag index exit code: %d", proc.returncode)

        if proc.returncode != 0:
            with open(log_file, encoding="utf-8") as lf:
                tail = "".join(lf.readlines()[-40:])
            _set_status(
                dataset_id,
                status="failed",
                step="building",
                progress=0,
                message=f"Index failed (exit {proc.returncode})",
                error=f"Index failed (exit {proc.returncode}):\n{tail}",
            )
            return

        # ── Success ──────────────────────────────────────────────────────
        _set_status(
            dataset_id,
            status="completed",
            step="done",
            progress=100,
            message="Indexing completed successfully!",
            error=None,
        )
        log.info("Indexing completed for dataset: %s", dataset_id)

    except Exception as e:
        log.exception("_run_index_thread exception")
        _set_status(
            dataset_id,
            status="failed",
            step="unknown",
            progress=0,
            message="Unknown error during indexing",
            error=str(e),
        )


def start_indexing(dataset_id: str, entity_types: list[str] | None = None) -> IndexStatus:
    """Start the indexing process in a background thread.

    Returns immediately with the initial status.
    """
    # Check if already running
    current = get_status(dataset_id)
    if current.status == "running":
        return current

    # Initialize status
    _set_status(
        dataset_id,
        status="running",
        step="starting",
        progress=25,
        message="Starting indexing...",
        error=None,
    )

    et = entity_types or list(DEFAULT_ENTITY_TYPES)
    thread = threading.Thread(
        target=_run_index_thread,
        args=(dataset_id, et),
        daemon=True,
    )
    thread.start()

    return get_status(dataset_id)
