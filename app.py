import csv
import os
import re
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

CSV_PATH = "emails.csv"
CSV_HEADERS = ["timestamp", "email", "character"]

SYSTEM_PROMPT = (
    "You are a comic book expert and enthusiastic guide for new readers. "
    "You write clear, welcoming, spoiler-conscious recommendations. "
    "Your reading orders are accurate, well-sequenced, and accessible to someone "
    "who has never read a single comic before."
)

JOBS_SYSTEM_PROMPT = (
    "You are a career advisor specializing in the comic book and graphic novel industry. "
    "You have deep knowledge of roles at major publishers (Marvel, DC, Image, Dark Horse, etc.), "
    "indie studios, webcomic platforms, and adjacent fields like animation, video games, and licensing. "
    "You give practical, honest career guidance with specific role titles, required skills, and how to break in."
)

JOBS_PROMPT_TEMPLATE = """\
Suggest 5 comic industry job opportunities for someone with these skills/interests: {skills}

For each job use this exact format:

1. **[Job Title]** — [Company type or example employer]
   Skills needed: [comma-separated list of 3-5 key skills]
   How to break in: [One concrete, actionable sentence on how to get this role.]

Rules:
- Include a mix of creative, technical, and business roles where relevant to the skills given.
- Be specific — name real role titles used in the industry (e.g. "Colorist", "Licensing Coordinator", "Comic Editor").
- If the input is not skills or interests at all (e.g. gibberish), respond with exactly: INVALID_INPUT
- Do not add any preamble, closing remarks, or commentary outside the numbered list.\
"""

SKILLS_RE = re.compile(r"[<>{}`\n]")

USER_PROMPT_TEMPLATE = """\
Create a beginner-friendly reading guide for the comic character: {character}

Return exactly 5 to 8 comics in recommended reading order. For each entry use this format:

1. **[Comic Title]** ([Year])
   [One sentence explaining why this comic matters for understanding the character and why a beginner should read it.]

Rules:
- Start with the most accessible, iconic entry point — not necessarily the first chronological appearance.
- Avoid major spoilers for later entries in the list.
- Prefer standalone stories, definitive runs, or well-collected trade paperbacks over ongoing series issues.
- If the character name is not a real comic character, respond with exactly: CHARACTER_NOT_FOUND
- Do not add any preamble, closing remarks, or commentary outside the numbered list.\
"""

CHAR_RE = re.compile(r"[<>{}`\n]")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def sanitize_skills(skills: str) -> str | None:
    skills = skills.strip()
    if not skills or len(skills) > 200:
        return None
    if SKILLS_RE.search(skills):
        return None
    return skills


def sanitize_character(name: str) -> str | None:
    name = name.strip()
    if not name or len(name) > 100:
        return None
    if CHAR_RE.search(name):
        return None
    return name


def validate_email(email: str) -> str | None:
    email = email.strip().lower()
    if not email or len(email) > 254:
        return None
    if not EMAIL_RE.match(email):
        return None
    return email


def save_email_to_csv(email: str, character: str) -> None:
    file_exists = os.path.isfile(CSV_PATH) and os.path.getsize(CSV_PATH) > 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow([datetime.now(timezone.utc).isoformat(), email, character])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/reading-guide", methods=["POST"])
def reading_guide():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    character = sanitize_character(data.get("character", ""))
    if not character:
        return jsonify({"error": "Please enter a valid character name."}), 400

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(character=character)}
            ],
        )
        text = response.content[0].text.strip()
    except anthropic.AuthenticationError:
        return jsonify({"error": "API key invalid. Check your ANTHROPIC_API_KEY."}), 502
    except anthropic.APIError as e:
        return jsonify({"error": f"API error: {e.message}"}), 502

    if text == "CHARACTER_NOT_FOUND":
        return jsonify({"error": "We couldn't find that character. Try someone like Spider-Man, Batman, or Storm."}), 404

    return jsonify({"guide": text})


@app.route("/api/save-email", methods=["POST"])
def save_email():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    email = validate_email(data.get("email", ""))
    if not email:
        return jsonify({"error": "Please enter a valid email address."}), 400

    character = sanitize_character(data.get("character", "")) or "unknown"

    try:
        save_email_to_csv(email, character)
    except OSError as e:
        return jsonify({"error": f"Could not save email: {e}"}), 500

    return jsonify({"success": True})


@app.route("/api/job-opportunities", methods=["POST"])
def job_opportunities():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request."}), 400

    skills = sanitize_skills(data.get("skills", ""))
    if not skills:
        return jsonify({"error": "Please enter your skills or interests (up to 200 characters)."}), 400

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=JOBS_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": JOBS_PROMPT_TEMPLATE.format(skills=skills)}
            ],
        )
        text = response.content[0].text.strip()
    except anthropic.AuthenticationError:
        return jsonify({"error": "API key invalid. Check your ANTHROPIC_API_KEY."}), 502
    except anthropic.APIError as e:
        return jsonify({"error": f"API error: {e.message}"}), 502

    if text == "INVALID_INPUT":
        return jsonify({"error": "Please describe your skills or interests (e.g. drawing, writing, Photoshop)."}), 400

    return jsonify({"jobs": text})


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
