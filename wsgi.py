"""WSGI 入口：gunicorn -c deploy/gunicorn.conf.py wsgi:app"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))