import os
import sqlite3
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from flask import Flask, jsonify, request

BASE = Path(__file__).resolve().parent
DB = Path(os.getenv("DATABASE_PATH", BASE / "portfolio.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-in-render")


def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = connect()
    c.execute("CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY CHECK(id=1), views INTEGER NOT NULL DEFAULT 0, enquiries INTEGER NOT NULL DEFAULT 0)")
    c.execute("INSERT OR IGNORE INTO stats(id,views,enquiries) VALUES(1,0,0)")
    c.execute("""CREATE TABLE IF NOT EXISTS enquiries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        subject TEXT,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    c.commit()
    c.close()


def send_enquiry_email(name, email, phone, subject, message):
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    mail_to = os.getenv("MAIL_TO", "veerannachowdarygoli46@gmail.com")

    if not username or not password or not mail_to:
        return False, "SMTP is not configured"

    msg = EmailMessage()
    msg["Subject"] = f"Portfolio Enquiry: {subject or 'New enquiry'}"
    msg["From"] = username
    msg["To"] = mail_to
    msg["Reply-To"] = email
    msg.set_content(
        f"New enquiry from your portfolio website.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Phone: {phone or '-'}\n"
        f"Subject: {subject or '-'}\n\n"
        f"Message:\n{message}\n"
    )

    with smtplib.SMTP(host, port, timeout=25) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
    return True, "sent"


@app.after_request
def add_cors(response):
    origin = request.headers.get("Origin", "")
    allowed = os.getenv("FRONTEND_ORIGIN", "*")
    response.headers["Access-Control-Allow-Origin"] = allowed if allowed != "*" else "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    if origin and allowed != "*":
        response.headers["Vary"] = "Origin"
    return response


@app.route("/api/<path:path>", methods=["OPTIONS"])
def api_options(path):
    return ("", 204)


@app.get("/")
def health():
    return jsonify(ok=True, service="Veeranna Chowdary Portfolio API")


@app.get("/api/health")
def api_health():
    return jsonify(ok=True, service="portfolio-api")


@app.post("/api/view")
def view():
    c = connect()
    c.execute("UPDATE stats SET views=views+1 WHERE id=1")
    c.commit()
    row = c.execute("SELECT views,enquiries FROM stats WHERE id=1").fetchone()
    c.close()
    return jsonify(dict(row))


@app.get("/api/stats")
def stats():
    c = connect()
    row = c.execute("SELECT views,enquiries FROM stats WHERE id=1").fetchone()
    c.close()
    return jsonify(dict(row))


@app.post("/api/enquiry")
def enquiry():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify(ok=False, message="Please fill in your name, email and message."), 400

    c = connect()
    c.execute(
        "INSERT INTO enquiries(name,email,phone,subject,message,created_at) VALUES(?,?,?,?,?,?)",
        (name, email, phone, subject, message, datetime.now(timezone.utc).isoformat())
    )
    c.execute("UPDATE stats SET enquiries=enquiries+1 WHERE id=1")
    c.commit()
    c.close()

    try:
        sent, reason = send_enquiry_email(name, email, phone, subject, message)
    except Exception as exc:
        sent, reason = False, str(exc)

    if sent:
        return jsonify(ok=True, message="Thank you. Your enquiry has been received and emailed successfully.")

    # The enquiry is still saved in SQLite even if SMTP is temporarily unavailable.
    print(f"SMTP email not sent: {reason}")
    return jsonify(ok=True, message="Thank you. Your enquiry has been received. Email delivery is temporarily pending."), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
