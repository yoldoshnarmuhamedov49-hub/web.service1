import os, threading
from flask import Flask, render_template
from bot import run_bot

app = Flask(__name__, template_folder=".")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "your_bot").lstrip("@")

_started = False
def start_once():
    global _started
    if not _started:
        _started = True
        threading.Thread(target=run_bot, daemon=True).start()
start_once()


@app.route("/")
def index():
    return render_template("index.html", bot=BOT_USERNAME)


@app.route("/health")
def health():
    return "ok", 200
