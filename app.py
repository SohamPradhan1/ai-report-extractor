
# app.py
import os
import tempfile
from flask import Flask, request, jsonify, render_template_string
from extractor import extract_employee_count_from_pdf

# 10 MB default upload ceiling (adjust as needed)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Employee Count Extractor (Render MVP)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body{font-family: system-ui, Arial, sans-serif; max-width: 720px; margin: 40px auto; padding:0 16px;}
      h1{font-size: 1.4rem;}
      .card{border:1px solid #ddd; padding: 16px; border-radius: 8px;}
      .muted{color:#666;font-size:0.95rem;}
      .ok{color:#157347;}
      .err{color:#b02a37;}
      input[type=file]{margin:12px 0;}
      footer{margin-top: 20px; color:#777; font-size:0.9rem;}
      code{background:#f7f7f7; padding:2px 4px; border-radius:3px;}
    </style>
  </head>
  <body>
    <h1>Employee Count Extractor (Render MVP)</h1>
    <div class="card">
      <p class="muted">
        Upload a PDF (≤ {{max_mb}} MB). We process only the first few pages with offline OCR and
        return the likely global employee count.
      </p>
      <form method="POST" enctype="multipart/form-data">
        <input type="file" name="pdf" accept="application/pdf" required>
        <div>
          <label>Pages to scan (first N pages):</label>
          <input type="number" min="1" max="10" name="pages" value="5" style="width:64px;">
        </div>
        <button type="submit">Extract</button>
      </form>
    </div>

    {% if result %}
      <h2>Result</h2>
      {% if result.employee_count %}
        <p class="ok"><strong>Employee count:</strong> {{ result.employee_count }}</p>
        <p><strong>Source:</strong> {{ result.source }}</p>
      {% else %}
        <p class="err">Couldn’t confidently find an employee count.</p>
      {% endif %}

      {% if result.matches %}
        <details>
          <summary>Show matched lines</summary>
          <pre>{{ result.matches|tojson(indent=2) }}</pre>
        </details>
      {% endif %}
    {% endif %}

    <footer>
      <p>Tip: You can also call this as a JSON API — <code>POST /api/extract</code> with form-data <code>pdf</code> and optional <code>pages</code>.</p>
    </footer>
  </body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        if "pdf" not in request.files:
            result = {"employee_count": None, "matches": [], "source": "none"}
            return render_template_string(HTML, result=result, max_mb=MAX_UPLOAD_MB)

        f = request.files["pdf"]
        pages = request.form.get("pages", "5")
        try:
            pages = max(1, min(10, int(pages)))
        except:
            pages = 5

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            f.save(tmp.name)
            result = extract_employee_count_from_pdf(tmp.name, max_pages=pages)

    return render_template_string(HTML, result=result, max_mb=MAX_UPLOAD_MB)


@app.route("/api/extract", methods=["POST"])
def api_extract():
    if "pdf" not in request.files:
        return jsonify({"error": "missing file"}), 400
    f = request.files["pdf"]
    pages = request.form.get("pages", "5")
    try:
        pages = max(1, min(10, int(pages)))
    except:
        pages = 5

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        f.save(tmp.name)
        result = extract_employee_count_from_pdf(tmp.name, max_pages=pages)

    return jsonify(result), 200


if __name__ == "__main__":
    # Local dev
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
