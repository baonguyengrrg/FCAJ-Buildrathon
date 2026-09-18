from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import sqlite3
import os
from datetime import datetime

# =======================================================
# 1. KHỞI TẠO DATABASE
# =======================================================
DB_DIR = "/app/data"
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "lab_stats.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member TEXT,
            service TEXT,
            method TEXT,
            path TEXT,
            created_at DATETIME
        )
        """)
        conn.commit()

init_db()

def log_audit(member: str, service: str, method: str, path: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO audit_logs (member, service, method, path, created_at) VALUES (?, ?, ?, ?, ?)",
                (member, service, method, path, datetime.now())
            )
            conn.commit()
    except Exception as e:
        print(f"[DB ERROR] {e}")

def generate_dashboard_html() -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT member, COUNT(*) FROM audit_logs GROUP BY member ORDER BY COUNT(*) DESC")
        members = cur.fetchall()

        cur.execute("SELECT service, COUNT(*) FROM audit_logs GROUP BY service ORDER BY COUNT(*) DESC")
        services = cur.fetchall()

        cur.execute("SELECT member, service, method, created_at FROM audit_logs ORDER BY id DESC LIMIT 10")
        recent = cur.fetchall()

    m_rows = "".join([f"<tr><td><b>{m[0]}</b></td><td>{m[1]} calls</td></tr>" for m in members])
    s_rows = "".join([f"<tr><td><b>{s[0]}</b></td><td>{s[1]} calls</td></tr>" for s in services])
    r_rows = "".join([f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3][:19]}</td></tr>" for r in recent])

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Floci Team Lab Dashboard</title>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 32px; margin: 0; }}
        h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 24px; }}
        .grid {{ display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 24px; }}
        .card {{ background: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; min-width: 300px; flex: 1; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }}
        th {{ color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
        tr:last-child td {{ border-bottom: none; }}
      </style>
    </head>
    <body>
      <h1>Team Lab</h1>
      <div class="grid">
        <div class="card">
          <h3>Member</h3>
          <table><tr><th>Member Key</th><th>Lượt gọi</th></tr>{m_rows or "<tr><td colspan=2>Chưa có dữ liệu</td></tr>"}</table>
        </div>
        <div class="card">
          <h3>Service</h3>
          <table><tr><th>Service</th><th>Lượt gọi</th></tr>{s_rows or "<tr><td colspan=2>Chưa có dữ liệu</td></tr>"}</table>
        </div>
      </div>
      <div class="card">
        <h3>Activity Stats</h3>
        <table><tr><th>Member</th><th>Service</th><th>Action</th><th>Thời gian</th></tr>{r_rows or "<tr><td colspan=4>Chưa có hoạt động</td></tr>"}</table>
      </div>
    </body>
    </html>
    """

# =======================================================
# 2. CHẶN VÀ TRẢ VỀ DASHBOARD QUA MIDDLEWARE
# =======================================================
class DashboardInterceptMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Chặn ngay lập tức nếu URL là /dashboard (xử lý cả GET lẫn HEAD từ curl -I)
        if request.url.path.strip("/") == "dashboard":
            if request.method == "HEAD":
                return Response(status_code=200, media_type="text/html")
            return HTMLResponse(content=generate_dashboard_html(), status_code=200)
        return await call_next(request)

app = FastAPI(title="Floci Shared Lab Hub")
app.add_middleware(DashboardInterceptMiddleware)
FLOCI_URL = "http://floci:4566"

# =======================================================
# 3. PROXY MỌI REQUEST AWS VÀO FLOCI
# =======================================================
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"])
async def proxy_aws_traffic(request: Request, path: str):
    auth_header = request.headers.get("authorization", "")
    member = "anonymous"
    if "Credential=" in auth_header:
        member = auth_header.split("Credential=")[1].split("/")[0]

    target = request.headers.get("x-amz-target", "")
    query_str = str(request.query_params)
    service = "S3"
    if "DynamoDB" in target or "dynamodb" in path:
        service = "DynamoDB"
    elif "AmazonSQS" in target or "queue" in path or "Action=SendMessage" in query_str:
        service = "SQS"
    elif "AmazonSNS" in target or "TopicArn" in query_str:
        service = "SNS"

    log_audit(member, service, request.method, path)

    async with httpx.AsyncClient() as client:
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)

        resp = await client.request(
            method=request.method,
            url=f"{FLOCI_URL}/{path}",
            headers=headers,
            content=body,
            params=request.query_params,
            timeout=60.0
        )
        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))