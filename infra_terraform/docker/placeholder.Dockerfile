# Minimal placeholder for Cloud Run (API) and Cloud Run Jobs.
# Listens on PORT, returns 200. For jobs, entrypoint can be overridden.
FROM python:3.11-alpine
RUN pip install --no-cache-dir flask
WORKDIR /app
RUN echo 'from flask import Flask; import os\napp = Flask(__name__)\n@app.route("/")\n@app.route("/<path:p>")\ndef ok(p=""): return "OK", 200\napp.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))' > server.py
EXPOSE 8080
CMD ["python", "server.py"]
