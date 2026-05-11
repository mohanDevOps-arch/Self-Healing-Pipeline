import os
from datetime import datetime, timezone

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

from ci_ai import (
    SAMPLE_LOGS,
    STAGE_CONFIG,
    analyze_ci,
    fetch_all_latest_builds,
    fetch_latest_build,
    fetch_latest_failed_log,
    stage_list,
)


def load_local_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            item = line.strip()
            if not item or item.startswith("#") or "=" not in item:
                continue
            key, value = item.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_local_env()
dashboard_app = Flask(__name__)

DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Self-Healing Pipeline Agent</title>
  <style>
    :root {
      --bg:#f4f7fb; --panel:#fff; --ink:#111827; --muted:#64748b; --line:#d8e1ed;
      --green:#0f8a5f; --green-bg:#e7f6ef; --blue:#245bdb; --blue-bg:#eaf1ff;
      --amber:#a65f00; --amber-bg:#fff4df; --red:#b42318; --red-bg:#fff0ed;
      --dark:#111827;
    }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    .shell { width:min(1240px, calc(100% - 32px)); margin:0 auto; padding:28px 0 52px; }
    .topbar { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:24px; }
    .brand { display:flex; align-items:center; gap:12px; font-weight:850; }
    .mark { display:grid; place-items:center; width:40px; height:40px; border-radius:8px; background:var(--dark); color:white; font-size:14px; }
    .pill { display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:999px; padding:8px 12px; background:#fff; color:var(--muted); font-size:13px; }
    .hero { display:grid; grid-template-columns:1.2fr .8fr; gap:18px; align-items:stretch; margin-bottom:20px; }
    h1 { margin:0; font-size:clamp(34px,5vw,62px); line-height:1; letter-spacing:0; }
    .lead { max-width:760px; color:var(--muted); font-size:18px; line-height:1.58; margin:18px 0 0; }
    .panel, .card { border:1px solid var(--line); background:var(--panel); border-radius:8px; box-shadow:0 16px 44px rgba(17,24,39,.07); }
    .panel { padding:18px; }
    .nav { display:flex; flex-wrap:wrap; gap:10px; margin-top:22px; }
    a.btn, button { display:inline-flex; align-items:center; justify-content:center; min-height:40px; border-radius:8px; border:1px solid var(--dark); background:var(--dark); color:#fff; padding:0 14px; font-weight:750; text-decoration:none; cursor:pointer; }
    a.btn.secondary { background:#fff; color:var(--dark); border-color:var(--line); }
    .metric-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
    .metric { border:1px solid var(--line); border-radius:8px; padding:14px; background:#fbfdff; }
    .metric strong { display:block; font-size:24px; }
    .metric span { display:block; color:var(--muted); font-size:12px; font-weight:800; text-transform:uppercase; margin-top:4px; }
    .section-title { margin:28px 0 14px; font-size:24px; }
    .build-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
    .card { padding:18px; }
    .card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:12px; }
    .card h3 { margin:0; font-size:22px; }
    .tag { display:inline-flex; border-radius:999px; padding:6px 10px; font-size:12px; font-weight:800; white-space:nowrap; }
    .green { color:var(--green); background:var(--green-bg); }
    .blue { color:var(--blue); background:var(--blue-bg); }
    .amber { color:var(--amber); background:var(--amber-bg); }
    .red { color:var(--red); background:var(--red-bg); }
    .muted { color:var(--muted); background:#eef2f7; }
    .field { border-top:1px solid var(--line); padding-top:12px; margin-top:12px; }
    .field span { display:block; color:var(--muted); font-size:12px; font-weight:800; text-transform:uppercase; margin-bottom:5px; }
    .field p { margin:0; line-height:1.5; color:#263449; overflow-wrap:anywhere; }
    .detail { display:grid; grid-template-columns:.78fr 1.22fr; gap:16px; align-items:start; margin-top:18px; }
    .result { display:grid; gap:12px; }
    .result-card { border:1px solid var(--line); border-radius:8px; padding:14px; background:#fbfdff; }
    .result-card h4 { margin:0 0 6px; font-size:13px; color:var(--muted); text-transform:uppercase; }
    .result-card p { margin:0; line-height:1.55; overflow-wrap:anywhere; }
    label { display:block; color:var(--muted); font-size:12px; font-weight:800; text-transform:uppercase; margin:14px 0 6px; }
    textarea, select { width:100%; border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink); padding:12px; font:inherit; }
    textarea { min-height:220px; resize:vertical; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:13px; }
    .small { color:var(--muted); font-size:13px; }
    @media (max-width:960px) { .hero,.build-grid,.detail,.metric-grid { grid-template-columns:1fr; } .topbar { align-items:flex-start; flex-direction:column; } }
  </style>
</head>
<body>
<main class="shell">
  <nav class="topbar">
    <div class="brand"><div class="mark">AI</div><span>Self-Healing Pipeline Agent</span></div>
    <span class="pill">{{ repo_label }}</span>
  </nav>

  <section class="hero">
    <div>
      <h1>{{ title }}</h1>
      <p class="lead">{{ subtitle }}</p>
      <div class="nav">
        <a class="btn {% if active %}secondary{% endif %}" href="/">Overview</a>
        {% for item in stages %}
        <a class="btn {% if item.key != active %}secondary{% endif %}" href="/{{ item.key }}">{{ item.name }}</a>
        {% endfor %}
      </div>
    </div>
    <aside class="panel">
      <div class="metric-grid">
        <div class="metric"><strong>{{ counts.passed }}</strong><span>Healthy</span></div>
        <div class="metric"><strong>{{ counts.failed }}</strong><span>Needs Agent</span></div>
        <div class="metric"><strong>{{ counts.running }}</strong><span>Watching</span></div>
      </div>
      <div class="field">
        <span>Agent loop</span>
        <p>Observe GitHub Actions, detect failures, diagnose logs with OpenAI, decide repair scope, and create safe repair PRs for DEV/STAGING.</p>
      </div>
    </aside>
  </section>

  {% if not active %}
  <h2 class="section-title">Self-Healing Status</h2>
  <section class="build-grid">
    {% for build in builds %}
    <article class="card">
      <div class="card-head">
        <div>
          <span class="tag {{ build.stage.accent }}">{{ build.stage.branch }}</span>
          <h3>{{ build.stage.name }}</h3>
        </div>
        <span class="tag {{ state_class(build.state) }}">{{ state_label(build.state) }}</span>
      </div>
      {% if build.run %}
      <div class="field"><span>Workflow</span><p>{{ build.run.name }}</p></div>
      <div class="field"><span>Commit</span><p>{{ build.run.display_title or "No title" }}{% if build.run.sha %} · {{ build.run.sha }}{% endif %}</p></div>
      <div class="field"><span>Updated</span><p>{{ build.run.updated_at or "Unknown" }}</p></div>
      <div class="field"><span>Agent status</span><p>{{ agent_status(build) }}</p></div>
      <div class="nav"><a class="btn secondary" href="/{{ build.stage.key }}">Open details</a><a class="btn secondary" href="{{ build.run.html_url }}" target="_blank">GitHub run</a></div>
      {% else %}
      <div class="field"><span>Status</span><p>{{ build.message }}</p></div>
      <div class="field"><span>Agent status</span><p>{{ agent_status(build) }}</p></div>
      <div class="nav"><a class="btn secondary" href="/{{ build.stage.key }}">Open details</a></div>
      {% endif %}
      {% if build.analysis %}
      <div class="field"><span>Agent state</span><p>{{ build.analysis.agent_state }}</p></div>
      <div class="field"><span>Agent action</span><p>{{ build.analysis.agent_action }}</p></div>
      <div class="field"><span>Root cause</span><p>{{ build.analysis.root_cause }}</p></div>
      {% endif %}
    </article>
    {% endfor %}
  </section>
  {% else %}
  <h2 class="section-title">{{ stage.name }} Agent Details</h2>
  <section class="detail">
    <article class="card">
      <div class="card-head">
        <div>
          <span class="tag {{ stage.accent }}">{{ stage.branch }}</span>
          <h3>{{ stage.name }}</h3>
        </div>
        <span class="tag {{ state_class(build.state) }}">{{ state_label(build.state) }}</span>
      </div>
      {% if build.run %}
      <div class="field"><span>Run</span><p><a href="{{ build.run.html_url }}" target="_blank">{{ build.run.name }}</a></p></div>
      <div class="field"><span>Trigger</span><p>{{ build.run.event }} on {{ build.run.branch }}</p></div>
      <div class="field"><span>Commit</span><p>{{ build.run.display_title or "No title" }}{% if build.run.sha %} · {{ build.run.sha }}{% endif %}</p></div>
      <div class="field"><span>Started / Updated</span><p>{{ build.run.created_at or "Unknown" }} / {{ build.run.updated_at or "Unknown" }}</p></div>
      {% else %}
      <div class="field"><span>Status</span><p>{{ build.message }}</p></div>
      {% endif %}
      <div class="field"><span>Self-healing policy</span><p>{{ stage.automation }}</p></div>
      <div class="field"><span>Human gate</span><p>{{ stage.approval }}</p></div>
    </article>

    <div class="result">
      {% if build.analysis %}
      <div class="result-card"><h4>Agent State</h4><p>{{ build.analysis.agent_state }}</p></div>
      <div class="result-card"><h4>Agent Scope</h4><p>{{ build.analysis.agent_scope }}</p></div>
      <div class="result-card"><h4>Action Taken</h4><p>{{ build.analysis.agent_action }}</p></div>
      <div class="result-card"><h4>Root Cause</h4><p>{{ build.analysis.root_cause }}</p></div>
      <div class="result-card"><h4>Suggested Fix</h4><p>{{ build.analysis.suggested_fix }}</p></div>
      <div class="result-card"><h4>Risk</h4><p><span class="tag {{ risk_class(build.analysis.risk) }}">{{ build.analysis.risk }}</span> Confidence: {{ "%.0f"|format(build.analysis.confidence * 100) }}%</p></div>
      <div class="result-card"><h4>Verification</h4><p>{{ build.analysis.verification }}</p></div>
      <div class="result-card"><h4>Healing Decision</h4><p>{{ build.analysis.automation_decision }}</p></div>
      <div class="result-card"><h4>PR-ready Summary</h4><p>{{ build.analysis.pr_summary }}</p></div>
      {% if build.analysis.note %}<div class="result-card"><h4>Note</h4><p>{{ build.analysis.note }}</p></div>{% endif %}
      {% elif build.state in ["passed", "in_progress", "queued", "requested"] %}
      <div class="result-card"><h4>Agent State</h4><p>Healthy. No self-healing action needed for the latest {{ stage.name }} run.</p></div>
      {% else %}
      <div class="result-card"><h4>GitHub Connection</h4><p>{{ build.message or "No failed build log is available yet." }}</p></div>
      {% endif %}

      <article class="card">
        <h3>Offline Agent Simulation</h3>
        <p class="small">Use only when GitHub credentials are unavailable. The real self-healing path is the GitHub Actions failure -> AI analyzer -> repair PR flow.</p>
        <form method="post" action="/analyze">
          <input type="hidden" name="stage" value="{{ active }}">
          <label for="mode">Mode</label>
          <select id="mode" name="mode">
            <option value="fallback">Fallback mode</option>
            <option value="real_ai">Real AI with OPENAI_API_KEY</option>
          </select>
          <label for="source">Source</label>
          <select id="source" name="source">
            <option value="paste">Paste CI log for offline simulation</option>
            <option value="sample">Use sample {{ stage.name }} failure</option>
            <option value="github">Fetch latest failed GitHub Actions run</option>
          </select>
          <label for="log">CI log</label>
          <textarea id="log" name="log" placeholder="Paste failed CI log here...">{{ sample }}</textarea>
          <button type="submit">Simulate agent decision</button>
        </form>
      </article>
    </div>
  </section>
  {% endif %}
</main>
</body>
</html>
"""


def state_class(state):
    if state == "passed":
        return "green"
    if state == "failed":
        return "red"
    if state in {"in_progress", "queued", "requested", "waiting"}:
        return "blue"
    if state in {"not_configured", "no_runs"}:
        return "muted"
    return "amber"


def state_label(state):
    labels = {
        "passed": "Passed",
        "failed": "Failed",
        "in_progress": "Running",
        "queued": "Queued",
        "requested": "Requested",
        "not_configured": "Needs GitHub env",
        "no_runs": "No runs",
    }
    return labels.get(state, str(state).replace("_", " ").title())


def risk_class(risk):
    if risk == "low":
        return "green"
    if risk == "high":
        return "red"
    return "amber"


def agent_status(build):
    if build.get("analysis"):
        return build["analysis"].get("agent_action", "Agent analyzed the failed build.")
    if build["state"] == "passed":
        return "Monitoring only. Build is healthy, so no healing action is required."
    if build["state"] in {"in_progress", "queued", "requested", "waiting"}:
        return "Watching active run. Agent will analyze if the pipeline fails."
    if build["state"] == "not_configured":
        return "Waiting for GitHub credentials before live monitoring can start."
    if build["state"] == "no_runs":
        return "Waiting for the first workflow run on this branch."
    return "Waiting for a failed build log before deciding an action."


def build_counts(builds):
    return {
        "passed": sum(1 for build in builds if build["state"] == "passed"),
        "failed": sum(1 for build in builds if build["state"] == "failed"),
        "running": sum(
            1 for build in builds if build["state"] in {"in_progress", "queued", "requested", "waiting"}
        ),
    }


def repo_label():
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return f"GitHub Actions · {repo}"
    return "Set GITHUB_TOKEN and GITHUB_REPOSITORY to show live builds"


def render_dashboard(active=None, analysis=None, sample=""):
    mode = request.args.get("mode", "real_ai")
    if active:
        build = fetch_latest_build(active, mode=mode, include_analysis=True)
        if analysis:
            build["analysis"] = analysis
            build["state"] = "failed"
            build["message"] = "Offline agent simulation result is shown."
        builds = fetch_all_latest_builds(mode=mode, include_analysis=False)
    else:
        build = None
        builds = fetch_all_latest_builds(mode=mode, include_analysis=True)

    return render_template_string(
        DASHBOARD_TEMPLATE,
        title="Self-healing CI/CD agent for DEV, STAGING, and MAIN.",
        subtitle=(
            "The agent watches GitHub Actions, detects failed builds, reads logs, diagnoses root cause, "
            "decides whether repair is safe, and creates repair PRs where policy allows."
        ),
        stages=stage_list(),
        builds=builds,
        build=build,
        counts=build_counts(builds),
        active=active,
        stage=STAGE_CONFIG.get(active) if active else None,
        sample=sample or (SAMPLE_LOGS.get(active, "") if active else ""),
        analysis=analysis,
        repo_label=repo_label(),
        state_class=state_class,
        state_label=state_label,
        risk_class=risk_class,
        agent_status=agent_status,
    )


@dashboard_app.route("/")
def dashboard():
    return render_dashboard()


@dashboard_app.route("/<stage_key>")
def stage_dashboard(stage_key):
    if stage_key not in STAGE_CONFIG:
        return redirect(url_for("dashboard"))
    return render_dashboard(active=stage_key)


@dashboard_app.route("/analyze", methods=["POST"])
def analyze_form():
    stage_key = request.form.get("stage", "dev")
    mode = request.form.get("mode", "fallback")
    source = request.form.get("source", "paste")
    log_text = request.form.get("log", "")
    note = None

    if source == "sample":
        log_text = SAMPLE_LOGS.get(stage_key, "")
    elif source == "github":
        try:
            fetched = fetch_latest_failed_log(stage_key)
            log_text = fetched["log"]
            note = f"Fetched failed run {fetched['run_id']}: {fetched['html_url']}"
        except RuntimeError as exc:
            log_text = SAMPLE_LOGS.get(stage_key, "")
            note = str(exc)

    analysis = analyze_ci(stage_key, log_text, mode)
    if note:
        analysis["note"] = note
    return render_dashboard(active=stage_key, analysis=analysis, sample=log_text)


@dashboard_app.route("/api/analyze", methods=["POST"])
def analyze_api():
    data = request.get_json(silent=True) or {}
    return jsonify(
        analyze_ci(
            data.get("stage", "dev"),
            data.get("log", ""),
            data.get("mode", "fallback"),
        )
    ), 200


@dashboard_app.route("/api/builds", methods=["GET"])
def builds_api():
    mode = request.args.get("mode", "real_ai")
    return jsonify(fetch_all_latest_builds(mode=mode, include_analysis=True)), 200


@dashboard_app.route("/api/builds/<stage_key>", methods=["GET"])
def build_api(stage_key):
    mode = request.args.get("mode", "real_ai")
    return jsonify(fetch_latest_build(stage_key, mode=mode, include_analysis=True)), 200


@dashboard_app.route("/api/latest-failed/<stage_key>", methods=["GET"])
def latest_failed_api(stage_key):
    return jsonify(fetch_latest_failed_log(stage_key)), 200


@dashboard_app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "service": "ai-cicd-dashboard",
            "agent": "self-healing-ci-agent",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ), 200


@dashboard_app.route("/pipeline", methods=["GET"])
def pipeline_summary():
    return jsonify(
        {
            "message": "Self-healing CI agent is available.",
            "pipeline_result_policy": "AI analysis runs after failure, but the failed job remains failed.",
            "stages": stage_list(),
        }
    ), 200


@dashboard_app.route("/pipeline/<stage_key>", methods=["GET"])
def pipeline_stage(stage_key):
    if stage_key not in STAGE_CONFIG:
        return jsonify({"error": "Pipeline stage not found"}), 404
    return jsonify(STAGE_CONFIG[stage_key] | {"key": stage_key}), 200


if __name__ == "__main__":
    dashboard_app.run(debug=True, port=int(os.environ.get("DASHBOARD_PORT", "5050")))
