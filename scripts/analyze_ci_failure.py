import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci_ai import analyze_ci  # noqa: E402


def write_summary(analysis):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = [
        "## AI CI Failure Analysis",
        "",
        f"**Stage:** {analysis['stage']}",
        f"**Mode:** {analysis['mode']}",
        f"**Confidence:** {analysis['confidence']:.0%}",
        f"**Risk:** {analysis['risk']}",
        f"**Agent state:** {analysis.get('agent_state', 'analysis_only')}",
        f"**Automation decision:** {analysis['automation_decision']}",
        "",
        "### Root cause",
        analysis["root_cause"],
        "",
        "### Suggested fix",
        analysis["suggested_fix"],
        "",
        "### Agent action",
        analysis.get("agent_action", "Publish diagnosis and wait for approval."),
        "",
        "### Verification",
        analysis["verification"],
        "",
        "### PR-ready summary",
        analysis["pr_summary"],
        "",
        "> Pipeline policy: this analyzer does not hide the original CI failure.",
        "",
    ]
    text = "\n".join(lines)
    print(text)
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["dev", "staging", "main"], required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--mode", choices=["fallback", "real_ai"], default="real_ai")
    parser.add_argument("--output", default="ai-analysis.json")
    args = parser.parse_args()

    log_text = Path(args.log_file).read_text(encoding="utf-8", errors="replace")
    analysis = analyze_ci(args.stage, log_text, args.mode)
    Path(args.output).write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    write_summary(analysis)


if __name__ == "__main__":
    main()
