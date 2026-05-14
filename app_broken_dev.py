import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request


app = Flask(__name__)
users = {}
user_id = 1

@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "service": "user-api",
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_count": len(users),
        }
    ), 200


@app.route("/users", methods=["GET"])
def get_users()  # BROKEN: missing colon
    return jsonify(list(users.values())), 200


@app.route("/users", methods=["POST"])
def create_user():
    global user_id

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()

    if not name:
        return jsonify({"error": "Name required"}), 400

    users[user_id] = {"id": user_id, "name": name}
    user_id += 1
    return jsonify(users[user_id - 1]), 201


@app.route("/users/<int:uid>", methods=["GET"])
def get_user(uid):
    if uid not in users:
        return jsonify({"error": "Not found"}), 404
    return jsonify(users[uid]), 200


@app.route("/users/<int:uid>", methods=["DELETE"])
def delete_user(uid):
    if uid not in users:
        return jsonify({"error": "Not found"}), 404
    return jsonify(users.pop(uid)), 200


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "5000")))
