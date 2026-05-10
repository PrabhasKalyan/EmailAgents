import os
import sys
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import dashboard_stats, init_db

init_db()

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@app.get("/")
def index(request: Request):
    stats = dashboard_stats()
    return templates.TemplateResponse(request, "index.html", stats)
