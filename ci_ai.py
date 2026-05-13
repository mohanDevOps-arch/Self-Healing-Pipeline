import json
import os
import urllib.error
import urllib.request
import zipfile
from io import BytesIO


STAGE_CONFIG = {
    "dev": {
        "name": "DEV",
        "branch": "dev",
        "accent": "green",
        "failure": "Syntax, lint, formatting, and compile failures",
        "automation": "Auto-fix, push bot branch, and auto-merge when checks pass.",
        "approval": "No manual approval for low-risk generated fixes.",
        "threshold": 0.80,
    },
    "staging": {
        "name": "STAGING",
        "branch": "staging",
        "accent": "blue",
        "failure": "Unit test, coverage, logic, and security failures",
        "automation": (
            "AI proposes a patch. Auto-push and merge only when confidence is at least "
            "90% and verification is positive."
        ),
        "approval": "Human review required below 90% confidence or when risk is medium/high.",
        "threshold": 0.90,
    },
    "main": {
        "name": "MAIN",
        "branch": "main",
        "accent": "amber",
        "failure": "Deployment, config, build, and production-readiness failures",
        "automation": "AI generates root cause, fix options, rollback notes, and PR summary only.",
        "approval": "Mandatory production approval before merge, rollback, or deployment.",
        "threshold": 1.00,
    },
}

SAMPLE_LOGS = {
    "dev": 'File "app.py", line 8\n    def get_users()\n                   ^\nSyntaxError: expected \':\'',
    "staging": (
        "FAILED test_app.py::test_create_user - assert 400 == 201\n"
        "E response.json = {'error': 'Name required'}"
    ),
    "main": (
        "KeyError: 'DB_HOST'\n"
        "Deployment readiness failed because production environment variable DB_HOST is not configured."
    ),
}


def stage_list():
    return [STAGE_CONFIG[key] | {"key": key} for key in ("dev", "staging", "main")]


def agent_action(stage_key, automation):
    if automation == "auto_push_and_merge":
        return {
            "agent_state": "self_healing",
            "agent_action": "Create repair branch, patch app.py, open PR, and enable auto-merge after checks.",
            "agent_scope": "Autonomous DEV repair",
        }
    if automation == "auto_push_merge_after_positive_report":
        return {
            "agent_state": "self_healing_with_confidence_gate",
            "agent_action": "Create repair branch only after low-risk analysis with confidence >= 90%.",
            "agent_scope": "Guarded STAGING repair",
        }
    if automation == "human_approval_required":
        return {
            "agent_state": "human_gated",
            "agent_action": "Publish triage, risk, verification, and PR summary. Do not patch or merge.",
            "agent_scope": "Production advisory mode",
        }
    return {
        "agent_state": "analysis_only",
        "agent_action": "Publish diagnosis and wait for a safer signal before patching.",
        "agent_scope": "No autonomous repair",
    }


def enrich_analysis(stage_key, analysis):
    action = agent_action(stage_key, analysis.get("automation_decision", "report_only"))
    for key, value in action.items():
        analysis.setdefault(key, value)
    analysis.setdefault("agent_name", "Self-Healing CI Agent")
    return analysis


def fallback_analysis(stage_key, log_text):
    text = log_text or SAMPLE_LOGS[stage_key]
    lower = text.lower()
    stage = STAGE_CONFIG[stage_key]
    confidence = 0.72
    risk = "medium"
    root_cause = "The CI log shows a pipeline failure, but the exact failing code path needs review."
    fix = (
        "Inspect the failing command output, patch the smallest affected code path, "
        "and rerun the same pipeline checks."
    )
    verification = "Rerun the failed GitHub Actions job and local tests before merging."

    if "syntaxerror" in lower and any(token in text for token in ("\n-\n", "\n.\n", "\n/\n")):
        confidence = 0.95
        risk = "low"
        root_cause = "Python compilation failed because the source contains a standalone invalid token line."
        fix = "Remove the stray punctuation line, then run `python -m py_compile app.py test_app.py`."
        verification = "Compile succeeds and dev lint/syntax checks pass."
    elif (
        "would reformat" in lower
        or "imports are incorrectly sorted" in lower
        or "isort" in lower and "incorrectly" in lower
        or "e302" in lower
    ):
        confidence = 0.98
        risk = "low"
        root_cause = "DEV validation failed because formatting/import style checks did not match Black, flake8, or isort rules."
        fix = "Run Black and isort on app.py and test_app.py, then rerun DEV validation."
        verification = "Black, flake8, isort, pylint, and py_compile all pass."
    elif ")strip(" in lower or "))strip()" in lower or "strip()" in lower and "syntaxerror" in lower:
        confidence = 0.96
        risk = "low"
        root_cause = "Python compilation failed because the `strip()` method call is missing the dot before `strip`."
        fix = (
            "Change `str(data.get(\"name\", \"\"))strip()` to "
            "`str(data.get(\"name\", \"\")).strip()`, then run `python -m py_compile app.py test_app.py`."
        )
        verification = "Compile succeeds and dev lint/syntax checks pass."
    elif "::" in text and "def " in lower:
        confidence = 0.96
        risk = "low"
        root_cause = "Python compilation failed because a function definition contains a malformed double colon."
        fix = (
            "Replace the malformed function definition line with exactly `def get_users():`, "
            "then run `python -m py_compile app.py test_app.py`."
        )
        verification = "Compile succeeds and dev lint/syntax checks pass."
    elif "syntaxerror" in lower or "expected ':'" in lower or "missing colon" in lower:
        confidence = 0.96
        risk = "low"
        root_cause = "Python compilation failed because a function definition is malformed or missing a colon."
        fix = (
            "Replace the malformed function definition line with exactly `def get_users():`, "
            "then run `python -m py_compile app.py test_app.py`."
        )
        verification = "Compile succeeds and dev lint/syntax checks pass."
    elif "assert 400 == 201" in lower or "name required" in lower:
        confidence = 0.93
        risk = "low"
        root_cause = (
            "The create-user validation is inverted or rejects valid `name` input, "
            "causing POST /users to return 400 instead of 201."
        )
        fix = (
            "Change the validation to reject only missing or blank names, then rerun "
            "`pytest test_app.py -v`."
        )
        verification = "User creation test returns 201 and the full staging test suite passes."
    elif "db_host" in lower or "keyerror" in lower:
        confidence = 0.88
        risk = "high"
        root_cause = "The app expects `DB_HOST`, but the production environment did not provide it."
        fix = "Add the missing deployment secret/config or change the app to fail with a clear readiness error."
        verification = (
            "Deploy to a pre-production environment with `DB_HOST` set and verify `/health` "
            "before production rollout."
        )
    elif "coverage" in lower:
        confidence = 0.84
        risk = "medium"
        root_cause = "Coverage is below the configured pipeline threshold."
        fix = "Add focused tests for the uncovered branch instead of lowering the threshold."
        verification = "Coverage job passes with the configured threshold."

    automation = "report_only"
    if stage_key == "dev" and confidence >= stage["threshold"] and risk == "low":
        automation = "auto_push_and_merge"
    elif stage_key == "staging" and confidence >= stage["threshold"] and risk == "low":
        automation = "auto_push_merge_after_positive_report"

    if stage_key == "main":
        automation = "human_approval_required"

    return enrich_analysis(stage_key, {
        "stage": stage["name"],
        "mode": "fallback",
        "confidence": confidence,
        "root_cause": root_cause,
        "suggested_fix": fix,
        "risk": risk,
        "verification": verification,
        "automation_decision": automation,
        "pr_summary": f"{stage['name']}: fix CI failure. Root cause: {root_cause} Verification: {verification}",
        "pipeline_result": "fail_preserved",
    })


def extract_response_text(payload):
    if "output_text" in payload:
        return payload["output_text"]
    chunks = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks).strip()


def real_ai_analysis(stage_key, log_text):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        result = fallback_analysis(stage_key, log_text)
        result["mode"] = "fallback"
        result["note"] = "OPENAI_API_KEY is not set, so fallback analysis was used."
        return result

    stage = STAGE_CONFIG[stage_key]
    prompt = {
        "stage": stage["name"],
        "policy": stage["automation"],
        "required_json_keys": [
            "confidence",
            "root_cause",
            "suggested_fix",
            "risk",
            "verification",
            "automation_decision",
            "pr_summary",
        ],
        "ci_log": (log_text or SAMPLE_LOGS[stage_key])[-12000:],
    }
    request_body = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
        "instructions": (
            "Analyze CI/CD failures. Return only JSON with confidence as a number between 0 and 1, "
            "root_cause, suggested_fix, risk, verification, automation_decision, and pr_summary. "
            "Never approve production changes for MAIN; use human_approval_required there."
        ),
        "input": json.dumps(prompt),
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        parsed = json.loads(extract_response_text(payload))
        parsed["stage"] = stage["name"]
        parsed["mode"] = "real_ai"
        parsed["pipeline_result"] = "fail_preserved"
        if stage_key == "main":
            parsed["automation_decision"] = "human_approval_required"
        return enrich_analysis(stage_key, parsed)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        result = fallback_analysis(stage_key, log_text)
        result["note"] = f"Real AI analysis failed, fallback used: {exc}"
        return result


def analyze_ci(stage_key, log_text, mode):
    if stage_key not in STAGE_CONFIG:
        raise ValueError("Unknown stage")
    if mode == "real_ai":
        return real_ai_analysis(stage_key, log_text)
    return fallback_analysis(stage_key, log_text)


def github_request(path):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise RuntimeError("Set GITHUB_TOKEN and GITHUB_REPOSITORY to fetch GitHub Actions logs.")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-cicd-demo",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()


def fetch_workflow_runs(stage_key, status=None, per_page=1):
    if stage_key not in STAGE_CONFIG:
        raise ValueError("Unknown stage")
    workflow = f"{stage_key}-pipeline.yml"
    branch = STAGE_CONFIG[stage_key]["branch"]
    query = f"branch={branch}&per_page={per_page}"
    if status:
        query = f"status={status}&{query}"
    runs_raw = github_request(f"/actions/workflows/{workflow}/runs?{query}")
    return json.loads(runs_raw.decode("utf-8")).get("workflow_runs", [])


def fetch_run_log(run_id):
    logs_raw = github_request(f"/actions/runs/{run_id}/logs")
    with zipfile.ZipFile(BytesIO(logs_raw)) as archive:
        parts = []
        for name in archive.namelist():
            if name.endswith(".txt"):
                parts.append(archive.read(name).decode("utf-8", errors="replace"))
    return "\n\n".join(parts)[-20000:]


def summarize_run(run):
    conclusion = run.get("conclusion")
    status = run.get("status")
    if status != "completed":
        state = status or "unknown"
    elif conclusion == "success":
        state = "passed"
    elif conclusion in {"failure", "cancelled", "timed_out"}:
        state = "failed"
    else:
        state = conclusion or "completed"
    return {
        "id": run.get("id"),
        "name": run.get("name"),
        "state": state,
        "status": status,
        "conclusion": conclusion,
        "branch": run.get("head_branch"),
        "sha": (run.get("head_sha") or "")[:8],
        "event": run.get("event"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "html_url": run.get("html_url"),
        "display_title": run.get("display_title") or run.get("head_commit", {}).get("message", ""),
    }


def fetch_latest_build(stage_key, mode="fallback", include_analysis=True):
    stage = STAGE_CONFIG[stage_key]
    try:
        runs = fetch_workflow_runs(stage_key, per_page=1)
    except RuntimeError as exc:
        return {
            "stage": stage | {"key": stage_key},
            "available": False,
            "state": "not_configured",
            "message": str(exc),
            "analysis": None,
            "log": "",
        }
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "stage": stage | {"key": stage_key},
            "available": False,
            "state": "error",
            "message": f"Could not fetch GitHub Actions run: {exc}",
            "analysis": None,
            "log": "",
        }

    if not runs:
        return {
            "stage": stage | {"key": stage_key},
            "available": True,
            "state": "no_runs",
            "message": f"No runs found for {stage['branch']} branch.",
            "analysis": None,
            "log": "",
        }

    run_summary = summarize_run(runs[0])
    build = {
        "stage": stage | {"key": stage_key},
        "available": True,
        "state": run_summary["state"],
        "message": "",
        "run": run_summary,
        "analysis": None,
        "log": "",
    }
    if include_analysis and run_summary["state"] == "failed":
        try:
            build["log"] = fetch_run_log(run_summary["id"])
            build["analysis"] = analyze_ci(stage_key, build["log"], mode)
        except (RuntimeError, urllib.error.URLError, zipfile.BadZipFile) as exc:
            build["message"] = f"Run failed, but logs could not be fetched: {exc}"
            build["analysis"] = analyze_ci(stage_key, SAMPLE_LOGS[stage_key], "fallback")
    return build


def fetch_all_latest_builds(mode="fallback", include_analysis=True):
    return [
        fetch_latest_build(stage_key, mode=mode, include_analysis=include_analysis)
        for stage_key in ("dev", "staging", "main")
    ]


def fetch_latest_failed_log(stage_key):
    runs = fetch_workflow_runs(stage_key, status="failure", per_page=1)
    if not runs:
        raise RuntimeError(f"No failed runs found for {stage_key}-pipeline.yml.")
    run = runs[0]
    return {
        "run_id": run["id"],
        "html_url": run["html_url"],
        "log": fetch_run_log(run["id"]),
    }
