import argparse
import json
import re
from pathlib import Path


def replace_once(path, before, after):
    text = path.read_text(encoding="utf-8")
    if before not in text:
        return False
    path.write_text(text.replace(before, after, 1), encoding="utf-8")
    return True


def replace_regex_once(path, pattern, replacement):
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count == 0:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["dev", "staging"], required=True)
    parser.add_argument("--analysis", default="ai-analysis.json")
    args = parser.parse_args()

    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    confidence = float(analysis.get("confidence", 0))
    risk = analysis.get("risk")
    decision = analysis.get("automation_decision")
    app_file = Path("app.py")
    patched = False

    if args.stage == "dev" and decision == "auto_push_and_merge" and risk == "low":
        patched = replace_regex_once(
            app_file,
            r"def get_users\(\)([^\n]*)(\n)",
            r"def get_users():\1\2",
        )

    if (
        args.stage == "staging"
        and decision == "auto_push_merge_after_positive_report"
        and confidence >= 0.90
        and risk == "low"
    ):
        patched = replace_once(app_file, "if data.get('name'):", "if not data.get('name'):")
        patched = replace_once(app_file, 'if data.get("name"):', 'if not data.get("name"):') or patched

    if not patched:
        raise SystemExit("No safe demo patch was applicable.")

    print(f"Applied safe {args.stage} AI demo patch.")


if __name__ == "__main__":
    main()
