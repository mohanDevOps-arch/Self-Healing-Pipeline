import argparse
import json
import re
import subprocess
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


def replace_regex_all(path, pattern, replacement):
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text)
    if count == 0:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def run_formatter(command):
    result = subprocess.run(command, check=False)
    return result.returncode == 0


def ensure_user_assignment(path):
    text = path.read_text(encoding="utf-8")
    assignment = '    users[user_id] = {"id": user_id, "name": name}'
    active_assignment = re.search(r"(?m)^\s*users\[user_id\]\s*=", text)
    if active_assignment:
        return False

    uncommented, count = re.subn(
        r"(?m)^(\s*)#\s*users\[user_id\]\s*=.*$",
        assignment,
        text,
        count=1,
    )
    if count:
        path.write_text(uncommented, encoding="utf-8")
        return True

    inserted, count = re.subn(
        r"(?m)^(\s*)user_id \+= 1$",
        f"{assignment}\n\\1user_id += 1",
        text,
        count=1,
    )
    if count:
        path.write_text(inserted, encoding="utf-8")
        return True
    return False


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
        patched = replace_regex_all(
            app_file,
            r"(?m)^\s*[-./\\]+\s*(#.*)?\n?",
            "",
        )
        patched = replace_regex_once(
            app_file,
            r"(?m)^def get_users\(\).*$",
            "def get_users():",
        ) or patched
        patched = replace_regex_once(
            app_file,
            r"(?m)^(def\s+[A-Za-z_][A-Za-z0-9_]*\([^)]*\))\s*(#.*)?$",
            lambda match: f"{match.group(1)}:{'  ' + match.group(2) if match.group(2) else ''}",
        ) or patched
        patched = replace_regex_once(
            app_file,
            r"(str\(data\.get\([\"']name[\"'],\s*[\"'][\"']\)\))strip\(",
            r"\1.strip(",
        ) or patched
        targets = [str(path) for path in (Path("app.py"), Path("test_app.py")) if path.exists()]
        if targets:
            patched = run_formatter(["python", "-m", "black", "--line-length=100", *targets]) or patched
            patched = run_formatter(["python", "-m", "isort", *targets]) or patched

    if (
        args.stage == "staging"
        and decision == "auto_push_merge_after_positive_report"
        and confidence >= 0.90
        and risk == "low"
    ):
        patched = replace_once(app_file, "if data.get('name'):", "if not data.get('name'):")
        patched = replace_once(app_file, 'if data.get("name"):', 'if not data.get("name"):') or patched
        patched = replace_once(
            app_file,
            "return jsonify(users[user_id - 1]), 200",
            "return jsonify(users[user_id - 1]), 201",
        ) or patched
        patched = replace_once(
            app_file,
            'return jsonify({"error": "Not found"}), 200',
            'return jsonify({"error": "Not found"}), 404',
        ) or patched
        patched = replace_once(
            app_file,
            "return jsonify({'error': 'Not found'}), 200",
            "return jsonify({'error': 'Not found'}), 404",
        ) or patched
        patched = ensure_user_assignment(app_file) or patched
        targets = [str(path) for path in (Path("app.py"), Path("test_app.py")) if path.exists()]
        if targets:
            patched = run_formatter(["python", "-m", "black", "--line-length=100", *targets]) or patched
            patched = run_formatter(["python", "-m", "isort", *targets]) or patched

    if not patched:
        raise SystemExit("No safe demo patch was applicable.")

    print(f"Applied safe {args.stage} AI demo patch.")


if __name__ == "__main__":
    main()
