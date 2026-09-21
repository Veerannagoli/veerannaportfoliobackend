import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from html import escape

import resend
from flask import Flask, jsonify, request


# =========================================================
# CONFIGURATION
# =========================================================

BASE = Path(__file__).resolve().parent

DB = Path(
    os.getenv(
        "DATABASE_PATH",
        str(BASE / "portfolio.db")
    )
)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-in-render"
)


# =========================================================
# DATABASE
# =========================================================

def connect():
    """
    Create a SQLite database connection.
    """
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """
    Create required database tables if they don't exist.
    """

    connection = connect()

    # Statistics table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            views INTEGER NOT NULL DEFAULT 0,
            enquiries INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    # Insert default statistics row
    connection.execute(
        """
        INSERT OR IGNORE INTO stats(id, views, enquiries)
        VALUES(1, 0, 0)
        """
    )

    # Enquiries table
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            subject TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


# Initialize database when application starts
init_db()


# =========================================================
# RESEND EMAIL
# =========================================================

def send_enquiry_email(name, email, phone, subject, message):
    """
    Send portfolio enquiry using Resend API.
    """

    api_key = os.getenv("RESEND_API_KEY", "").strip()

    mail_to = os.getenv(
        "MAIL_TO",
        "veerannachowdarygoli46@gmail.com"
    ).strip()

    mail_from = os.getenv(
        "MAIL_FROM",
        "onboarding@resend.dev"
    ).strip()

    # Validate configuration
    if not api_key:
        return False, "RESEND_API_KEY is not configured"

    if not mail_to:
        return False, "MAIL_TO is not configured"

    if not mail_from:
        return False, "MAIL_FROM is not configured"

    # Configure Resend
    resend.api_key = api_key

    # Safe values
    safe_name = escape(name)
    safe_email = escape(email)
    safe_phone = escape(phone or "-")
    safe_subject = escape(subject or "New enquiry")
    safe_message = escape(message).replace("\n", "<br>")

    # HTML email
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Portfolio Enquiry</title>
    </head>

    <body style="
        margin: 0;
        padding: 30px;
        background: #f6f1e7;
        font-family: Arial, Helvetica, sans-serif;
        color: #172033;
    ">

        <div style="
            max-width: 650px;
            margin: auto;
            background: #ffffff;
            border-radius: 12px;
            padding: 30px;
            border: 1px solid #e5dfd3;
        ">

            <h2 style="
                margin-top: 0;
                color: #172033;
            ">
                New Portfolio Enquiry
            </h2>

            <p>
                Someone has submitted an enquiry through your portfolio website.
            </p>

            <hr style="
                border: none;
                border-top: 1px solid #e5dfd3;
                margin: 25px 0;
            ">

            <p>
                <strong>Name:</strong><br>
                {safe_name}
            </p>

            <p>
                <strong>Email:</strong><br>
                {safe_email}
            </p>

            <p>
                <strong>Phone:</strong><br>
                {safe_phone}
            </p>

            <p>
                <strong>Subject:</strong><br>
                {safe_subject}
            </p>

            <p>
                <strong>Message:</strong>
            </p>

            <div style="
                background: #f8f6f1;
                border-radius: 8px;
                padding: 18px;
                line-height: 1.6;
            ">
                {safe_message}
            </div>

            <hr style="
                border: none;
                border-top: 1px solid #e5dfd3;
                margin: 25px 0;
            ">

            <p style="
                font-size: 13px;
                color: #777777;
            ">
                This email was generated automatically by the
                Veeranna Chowdary Portfolio website.
            </p>

        </div>

    </body>
    </html>
    """

    # Plain-text fallback
    text_content = f"""
New Portfolio Enquiry

Name: {name}
Email: {email}
Phone: {phone or "-"}
Subject: {subject or "New enquiry"}

Message:
{message}

--------------------------------
Sent from Veeranna Chowdary Portfolio
"""

    # Resend request
    params = {
        "from": mail_from,
        "to": [mail_to],
        "reply_to": [email],
        "subject": f"Portfolio Enquiry: {subject or 'New enquiry'}",
        "html": html_content,
        "text": text_content,
    }

    try:

        result = resend.Emails.send(params)

        print("========================================")
        print("RESEND EMAIL SENT")
        print("========================================")
        print(f"Resend response: {result}")
        print("========================================")

        return True, "sent"

    except Exception as exc:

        print("========================================")
        print("RESEND EMAIL FAILED")
        print("========================================")
        print(f"Error: {exc}")
        print("========================================")

        return False, str(exc)


# =========================================================
# CORS
# =========================================================

@app.after_request
def add_cors(response):

    origin = request.headers.get("Origin", "")

    allowed = os.getenv(
        "FRONTEND_ORIGIN",
        "*"
    )

    if allowed == "*":
        response.headers["Access-Control-Allow-Origin"] = "*"

    else:
        response.headers["Access-Control-Allow-Origin"] = allowed

    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type"
    )

    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, OPTIONS"
    )

    if origin and allowed != "*":
        response.headers["Vary"] = "Origin"

    return response


# =========================================================
# OPTIONS / CORS PREFLIGHT
# =========================================================

@app.route(
    "/api/<path:path>",
    methods=["OPTIONS"]
)
def api_options(path):

    return ("", 204)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
def health():

    return jsonify(
        ok=True,
        service="Veeranna Chowdary Portfolio API"
    )


@app.get("/api/health")
def api_health():

    return jsonify(
        ok=True,
        service="portfolio-api"
    )


# =========================================================
# RECORD WEBSITE VIEW
# =========================================================

@app.post("/api/view")
def view():

    connection = connect()

    connection.execute(
        """
        UPDATE stats
        SET views = views + 1
        WHERE id = 1
        """
    )

    connection.commit()

    row = connection.execute(
        """
        SELECT views, enquiries
        FROM stats
        WHERE id = 1
        """
    ).fetchone()

    connection.close()

    return jsonify(dict(row))


# =========================================================
# GET STATISTICS
# =========================================================

@app.get("/api/stats")
def stats():

    connection = connect()

    row = connection.execute(
        """
        SELECT views, enquiries
        FROM stats
        WHERE id = 1
        """
    ).fetchone()

    connection.close()

    return jsonify(dict(row))


# =========================================================
# PORTFOLIO ENQUIRY
# =========================================================

@app.post("/api/enquiry")
def enquiry():

    # Get JSON request
    data = request.get_json(silent=True) or {}

    # Read fields
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()

    # Basic validation
    if not name or not email or not message:

        return jsonify(
            ok=False,
            message="Please fill in your name, email and message."
        ), 400

    # =====================================================
    # SAVE ENQUIRY
    # =====================================================

    connection = connect()

    connection.execute(
        """
        INSERT INTO enquiries
        (
            name,
            email,
            phone,
            subject,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            email,
            phone,
            subject,
            message,
            datetime.now(timezone.utc).isoformat()
        )
    )

    # Increase enquiry count
    connection.execute(
        """
        UPDATE stats
        SET enquiries = enquiries + 1
        WHERE id = 1
        """
    )

    connection.commit()
    connection.close()

    # =====================================================
    # SEND EMAIL THROUGH RESEND
    # =====================================================

    try:

        sent, reason = send_enquiry_email(
            name,
            email,
            phone,
            subject,
            message
        )

    except Exception as exc:

        sent = False
        reason = str(exc)

    # =====================================================
    # SUCCESS
    # =====================================================

    if sent:

        return jsonify(
            ok=True,
            message=(
                "Thank you. Your enquiry has been "
                "received and emailed successfully."
            )
        )

    # =====================================================
    # EMAIL FAILED BUT ENQUIRY WAS SAVED
    # =====================================================

    print("========================================")
    print("EMAIL DELIVERY PENDING")
    print("========================================")
    print(f"Reason: {reason}")
    print("========================================")

    return jsonify(
        ok=True,
        message=(
            "Thank you. Your enquiry has been received. "
            "Email delivery is temporarily pending."
        )
    ), 200


# =========================================================
# LOCAL DEVELOPMENT
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv("PORT", "5000")
        ),
        debug=False
    )