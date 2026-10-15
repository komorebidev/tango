import base64
import json
import os
import re
import threading
from pathlib import Path
from urllib.parse import quote

import requests
from azure.core import MatchConditions
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient
from flask import Flask, jsonify, render_template, request

from cloudflare_ai import run_ai

app = Flask(__name__)
app.json.ensure_ascii = False

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "db.json"
VISITS_FILE = BASE_DIR / "visits.json"
VISITS_BLOB_NAME = "visits.json"

visits_lock = threading.Lock()
vocabulary_lock = threading.Lock()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
# Your repository's vocabulary file is at the repository root.
# Set GITHUB_DB_PATH=db.json in the environment to use it.
GITHUB_DB_PATH = os.getenv("GITHUB_DB_PATH", "tangoapp/db.json")
GITHUB_CONFIGURED = bool(GITHUB_TOKEN and GITHUB_REPOSITORY)

JISHO_API_URL = "https://jisho.org/api/v1/search/words"

AZURE_STORAGE_ACCOUNT_URL = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

# Use managed identity on Azure. If the storage settings are absent,
# use the local visits.json file for local development.
storage_credential = (
    DefaultAzureCredential()
    if AZURE_STORAGE_ACCOUNT_URL and AZURE_STORAGE_CONTAINER_NAME
    else None
)


def get_visit_count():
    # Local development: use visits.json on disk.
    if storage_credential is None:
        with visits_lock:
            try:
                if VISITS_FILE.exists():
                    data = json.loads(
                        VISITS_FILE.read_text(encoding="utf-8")
                    )
                    count = int(data.get("count", 0))
                else:
                    count = 0
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                count = 0

            count += 1

            try:
                VISITS_FILE.write_text(
                    json.dumps(
                        {"count": count},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except OSError:
                app.logger.exception("Could not update local visits.json")

            return count

    # Azure: use visits.json in the private Blob Storage container.
    blob = BlobClient(
        account_url=AZURE_STORAGE_ACCOUNT_URL,
        container_name=AZURE_STORAGE_CONTAINER_NAME,
        blob_name=VISITS_BLOB_NAME,
        credential=storage_credential,
    )

    # Create the initial counter if it does not exist.
    # If another request creates it first, continue with the existing blob.
    try:
        blob.upload_blob(
            json.dumps({"count": 0}),
            overwrite=False,
            content_type="application/json",
        )
    except ResourceExistsError:
        pass
    except Exception:
        # A concurrent creation or transient failure may require a retry.
        # The subsequent read determines whether the blob is available.
        app.logger.debug(
            "Initial visits.json creation did not complete; "
            "attempting to read the existing blob.",
            exc_info=True,
        )

    # Conditional updates prevent concurrent requests from silently
    # overwriting each other's increments.
    max_attempts = 10

    try:
        for attempt in range(max_attempts):
            try:
                # Read the content and the ETag from the same response.
                downloader = blob.download_blob()
                data = json.loads(downloader.readall())
                etag = downloader.properties.etag

                if not isinstance(data, dict):
                    raise ValueError(
                        "visits.json must contain a JSON object."
                    )

                count = int(data.get("count", 0)) + 1

                updated_data = json.dumps(
                    {"count": count},
                    ensure_ascii=False,
                    indent=2,
                )

                # Only write if the blob still has the ETag we read.
                blob.upload_blob(
                    updated_data,
                    overwrite=True,
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                    content_type="application/json",
                )

                return count

            except ResourceModifiedError:
                # Another request updated the blob. Read the latest value
                # and try again.
                app.logger.debug(
                    "visits.json changed concurrently; retry %s of %s.",
                    attempt + 1,
                    max_attempts,
                )
                continue

            except ResourceNotFoundError:
                # The blob may have disappeared between operations.
                # Recreate it and retry.
                try:
                    blob.upload_blob(
                        json.dumps({"count": 0}),
                        overwrite=False,
                        content_type="application/json",
                    )
                except ResourceExistsError:
                    pass
                continue

        raise RuntimeError(
            "Could not update visits.json after repeated concurrent changes."
        )

    finally:
        blob.close()


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url():
    repo = (GITHUB_REPOSITORY or "").strip().strip("/")
    path = quote(GITHUB_DB_PATH.strip("/"), safe="/")
    return f"https://api.github.com/repos/{repo}/contents/{path}"


def read_vocabulary():
    if not GITHUB_CONFIGURED:
        if not DB_FILE.exists():
            return []
        with DB_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("Vocabulary database must be a JSON array.")
        return data

    response = requests.get(
        github_file_url(),
        headers=github_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=20,
    )
    response.raise_for_status()
    file_info = response.json()
    content = base64.b64decode(file_info["content"]).decode("utf-8")
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError("GitHub vocabulary database must be a JSON array.")
    return data


def save_vocabulary(vocabulary):
    content = json.dumps(vocabulary, ensure_ascii=False, indent=2) + "\n"

    if not GITHUB_CONFIGURED:
        DB_FILE.write_text(content, encoding="utf-8")
        return "local"

    url = github_file_url()
    current_response = requests.get(
        url,
        headers=github_headers(),
        params={"ref": GITHUB_BRANCH},
        timeout=20,
    )
    current_response.raise_for_status()
    current_file = current_response.json()

    payload = {
        "message": "Add vocabulary entry",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": GITHUB_BRANCH,
        "sha": current_file["sha"],
    }
    save_response = requests.put(
        url,
        headers=github_headers(),
        json=payload,
        timeout=30,
    )
    save_response.raise_for_status()
    return "github"


def extract_ai_json(ai_result):
    try:
        raw_output = ai_result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            "The AI response did not contain message content."
        ) from exc

    cleaned = raw_output.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # If the model adds prose around the JSON, extract the first JSON object.
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]

    try:
        entry = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "The AI response was not valid JSON. Check the Raw AI output."
        ) from exc

    if not isinstance(entry, dict):
        raise ValueError("The AI response must be a JSON object.")

    return entry, raw_output


@app.route("/")
def index():
    return render_template("index.html", visit_count=get_visit_count())


@app.route("/add-vocabulary")
def add_vocabulary_page():
    return render_template("add_vocabulary.html")


@app.route("/api/vocabulary", methods=["GET"])
def api_vocabulary():
    try:
        return jsonify(read_vocabulary())
    except (requests.RequestException, ValueError, OSError, KeyError) as exc:
        app.logger.exception("Could not read vocabulary database")
        return jsonify({"error": str(exc)}), 502


@app.route("/api/vocabulary/generate", methods=["POST"])
def generate_vocabulary():
    data = request.get_json(silent=True) or {}
    word = str(data.get("word", "")).strip()
    if not word:
        return jsonify({"error": "Enter a Japanese word first."}), 400

    messages = [
        {
            "role": "system",
            "content": (
                "You are helping a learner create Japanese vocabulary flashcards. "
                "Return exactly one JSON object, with no Markdown or explanation, "
                "containing these string fields: word, reading, meaning, example, translation. "
                "word must be the supplied Japanese word. reading must be the complete "
                "hiragana reading of the word. meaning must be a concise English meaning. "
                "example must be one natural Japanese example sentence using the word. "
                "translation must be the English translation of that sentence. "
                "Use standard Japanese spelling and do not invent multiple alternatives."
            ),
        },
        {
            "role": "user",
            "content": f"Create a vocabulary entry for this Japanese word: {word}",
        },
    ]

    try:
        ai_result = run_ai(messages)
        entry, raw_output = extract_ai_json(ai_result)
        normalized = {
            "word": str(entry.get("word", word)).strip() or word,
            "reading": str(entry.get("reading", "")).strip(),
            "meaning": str(entry.get("meaning", "")).strip(),
            "example": str(entry.get("example", "")).strip(),
            "translation": str(entry.get("translation", "")).strip(),
        }
        return jsonify({"entry": normalized, "raw_output": raw_output})
    except Exception as exc:
        app.logger.exception("Vocabulary generation failed")
        return jsonify({"error": str(exc)}), 502


@app.route("/api/vocabulary/jisho", methods=["POST"])
def jisho_vocabulary():
    data = request.get_json(silent=True) or {}
    word = str(data.get("word", "")).strip()
    if not word:
        return jsonify({"error": "Enter a Japanese word to search Jisho."}), 400

    try:
        response = requests.get(
            JISHO_API_URL,
            params={"keyword": word},
            headers={"User-Agent": "TangoJapaneseVocabularyApp/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout:
        return jsonify(
            {"error": "Jisho took too long to respond. Please try again."}
        ), 504
    except (requests.RequestException, ValueError) as exc:
        app.logger.exception("Jisho lookup failed")
        return jsonify(
            {"error": f"Could not look up this word on Jisho: {exc}"}
        ), 502

    results = []
    for item in payload.get("data", []):
        japanese_forms = item.get("japanese", [])
        senses = item.get("senses", [])
        spellings = []
        readings = []

        for form in japanese_forms:
            spelling = form.get("word")
            reading = form.get("reading")
            if spelling and spelling not in spellings:
                spellings.append(spelling)
            if reading and reading not in readings:
                readings.append(reading)

        definitions = []
        for sense in senses:
            for definition in sense.get("english_definitions", []):
                if definition and definition not in definitions:
                    definitions.append(definition)

        if not readings and not definitions:
            continue

        slug = item.get("slug")
        results.append(
            {
                "word": "、".join(spellings),
                "reading": "、".join(readings),
                "meaning": "; ".join(definitions),
                "parts_of_speech": list(
                    dict.fromkeys(
                        part
                        for sense in senses
                        for part in sense.get("parts_of_speech", [])
                    )
                ),
                "is_common": bool(item.get("is_common")),
                "url": (
                    f"https://jisho.org/word/{quote(slug, safe='')}"
                    if slug
                    else "https://jisho.org/search/" + quote(word, safe="")
                ),
            }
        )

    return jsonify({"word": word, "results": results})


@app.route("/api/vocabulary/save", methods=["POST"])
def save_vocabulary_entry():
    data = request.get_json(silent=True) or {}
    fields = ["word", "reading", "meaning", "example", "translation"]
    entry = {field: str(data.get(field, "")).strip() for field in fields}

    missing = [field for field in fields if not entry[field]]
    if missing:
        return jsonify(
            {"error": "Please fill in all fields before saving."}
        ), 400

    try:
        with vocabulary_lock:
            vocabulary = read_vocabulary()
            existing_words = {
                str(item.get("word", "")).strip()
                for item in vocabulary
                if isinstance(item, dict)
            }
            if entry["word"] in existing_words:
                return jsonify(
                    {
                        "error": (
                            f'"{entry["word"]}" already exists '
                            "in the vocabulary database."
                        )
                    }
                ), 409

            vocabulary.append(entry)
            vocabulary.sort(
                key=lambda item: (
                    str(item.get("reading", "")),
                    str(item.get("word", "")),
                )
            )
            destination = save_vocabulary(vocabulary)

        return jsonify(
            {
                "success": True,
                "destination": destination,
                "entry": entry,
            }
        )
    except requests.RequestException as exc:
        app.logger.exception("Could not save vocabulary to GitHub")
        return jsonify(
            {"error": f"Could not save vocabulary: {exc}"}
        ), 502
    except (OSError, ValueError, KeyError) as exc:
        app.logger.exception("Could not save vocabulary")
        return jsonify(
            {"error": f"Could not save vocabulary: {exc}"}
        ), 500


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok"})


@app.route("/api/stats")
def api_stats():
    try:
        vocabulary = read_vocabulary()
        return jsonify({"count": len(vocabulary)})
    except Exception as exc:
        app.logger.exception("Could not read vocabulary stats")
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(debug=True)