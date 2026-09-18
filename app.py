"""FollowUp AI: a dependency-light patient reminder and agent learning lab.

Run with: python app.py
Optional integrations use GROQ_API_KEY and TAVILY_API_KEY environment variables.
"""

import datetime as dt
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PORT = int(os.getenv("PORT", "8000"))
DB_PATH = os.getenv("FOLLOWUP_DB", "followup.sqlite3")


CURRICULUM = [
    ("01", "AI Agent Foundations", "Environment setup, first agent, OpenAI traces, and safe API configuration."),
    ("02", "Persistent Agent Memory", "SQLite sessions, multi-turn state, and memory-aware patient conversations."),
    ("03", "Tools and Real-time Search", "Code Interpreter concepts, Tavily search, and FunctionTool design."),
    ("04", "Agent Teams", "Managers, handoffs, guardrails, specialist agents, AutoGen, LangGraph, and CrewAI."),
    ("05", "Predictive Analytics", "EDA, preprocessing, regression, random forest, XGBoost, R2, MAE, and MSE."),
    ("06", "MCP and External Tools", "Expose Gradio tools, discover manifests, and execute MCP services over HTTP."),
    ("07", "n8n Automation", "AI summaries, structured JSON, Gmail, Sheets, Calendar, and end-to-end workflows."),
]


def database():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, patient TEXT NOT NULL, phone TEXT,
        due_date TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
        notes TEXT DEFAULT '', created_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL,
        created_at TEXT NOT NULL)""")
    connection.commit()
    return connection


def seed_data():
    connection = database()
    if connection.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 0:
        today = dt.date.today()
        connection.executemany(
            "INSERT INTO reminders(patient, phone, due_date, reason, status, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("Aarav Mehta", "+91 98765 43210", str(today), "Medication check-in", "Due today", "Ask about side effects", str(dt.datetime.now())),
                ("Maya Shah", "+91 99887 66554", str(today + dt.timedelta(days=1)), "Post-discharge follow-up", "Pending", "Review wound-care plan", str(dt.datetime.now())),
                ("Rohan Iyer", "+91 91234 56789", str(today + dt.timedelta(days=3)), "Lab results review", "Pending", "Share results with clinician", str(dt.datetime.now())),
            ],
        )
        connection.commit()
    connection.close()


def json_response(handler, payload, status=200):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def groq_answer(prompt):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    request = Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps({
            "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "messages": [{"role": "system", "content": "You are a careful patient follow-up assistant. Never diagnose. Recommend clinician escalation for urgent symptoms."}, {"role": "user", "content": prompt}],
            "temperature": 0.3,
        }).encode(),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read())["choices"][0]["message"]["content"]


def search_web(query):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []
    request = Request(
        "https://api.tavily.com/search",
        data=json.dumps({"api_key": api_key, "query": query, "max_results": 3}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read()).get("results", [])


def local_agent_answer(prompt):
    results = search_web(prompt)
    context = "\n".join(item.get("content", "") for item in results)
    try:
        answer = groq_answer("Question: " + prompt + "\n\nSearch context:\n" + context)
    except Exception as error:
        answer = "AI service unavailable: " + str(error)
    if answer:
        return answer, results, "Planner -> Search -> Analyst -> Writer"
    return ("Local demo mode: configure GROQ_API_KEY for generated responses. "
            "For patient safety, route urgent symptoms to a qualified clinician."), results, "Planner -> Memory -> Writer"


HTML = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FollowUp AI</title><style>
:root{--ink:#17221d;--muted:#65736b;--paper:#f5f4ef;--card:#fffefa;--line:#d9ded7;--green:#1e6b52;--mint:#dcefe5;--coral:#dc755a;--yellow:#f3d98b}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Georgia,serif}button,input,textarea{font:inherit}button{cursor:pointer;border:0}.shell{display:grid;grid-template-columns:245px 1fr;min-height:100vh}.side{background:#18382d;color:#f4f3eb;padding:28px 20px;display:flex;flex-direction:column}.brand{font:700 25px Georgia;margin-bottom:45px}.brand span{color:#f3d98b}.eyebrow{font:11px sans-serif;letter-spacing:1.8px;text-transform:uppercase;color:#a8c9ba}.nav button{display:block;width:100%;background:transparent;color:#d8e9df;text-align:left;padding:13px 11px;margin:4px 0;border-radius:6px}.nav button.active,.nav button:hover{background:#2c5c49;color:white}.side-foot{margin-top:auto;font:12px sans-serif;color:#a8c9ba}.main{padding:34px 5vw 60px;max-width:1400px;width:100%}.top{display:flex;justify-content:space-between;align-items:start;border-bottom:1px solid var(--line);padding-bottom:25px}.top h1{font-size:36px;font-weight:400;line-height:1.05;margin:7px 0}.date{font:12px sans-serif;color:var(--muted);text-align:right}.page{display:none}.page.active{display:block}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}.stat,.panel,.reminder{background:var(--card);border:1px solid var(--line);border-radius:7px}.stat{padding:18px}.stat b{font-size:30px;font-weight:400;display:block}.stat small{color:var(--muted);font:12px sans-serif}.grid{display:grid;grid-template-columns:1.35fr 1fr;gap:18px}.panel{padding:22px}.panel h2{font-size:21px;font-weight:400;margin:0 0 16px}.reminder{padding:16px;margin:10px 0;display:grid;grid-template-columns:1fr auto;gap:10px}.reminder strong{display:block;font-size:17px}.meta{font:12px sans-serif;color:var(--muted)}.tag{font:11px sans-serif;padding:5px 9px;border-radius:20px;background:var(--mint);color:var(--green);white-space:nowrap;height:max-content}.tag.due{background:#f8e3dc;color:#a44932}.action{background:var(--green);color:white;padding:10px 15px;border-radius:5px}.action.alt{background:transparent;color:var(--green);border:1px solid var(--green)}form{display:grid;gap:11px}label{font:12px sans-serif;color:var(--muted);display:grid;gap:5px}input,textarea{border:1px solid var(--line);padding:10px;border-radius:4px;background:#fff}.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}.hero{padding:30px 0 12px}.hero h2{font-size:42px;font-weight:400;margin:5px 0 12px;max-width:680px}.hero p{max-width:650px;color:var(--muted)}.module{padding:15px 0;border-bottom:1px solid var(--line);display:grid;grid-template-columns:48px 1fr auto;gap:12px;align-items:center}.module-num{font:700 13px sans-serif;color:var(--coral)}.module h3{margin:0;font-size:17px;font-weight:400}.module p{margin:3px 0 0;color:var(--muted);font-size:13px}.flow{display:flex;flex-wrap:wrap;gap:8px;margin:25px 0}.node{padding:12px 14px;background:var(--mint);border-radius:4px;font:13px sans-serif}.arrow{padding:12px 0;color:var(--coral)}.answer{white-space:pre-wrap;background:#f1f5ef;padding:15px;border-left:3px solid var(--green);margin-top:15px}.notice{padding:12px 15px;background:#fff5d8;border-left:3px solid var(--yellow);font:13px sans-serif;margin:15px 0}@media(max-width:800px){.shell{display:block}.side{padding:18px;min-height:0}.brand{margin-bottom:15px}.nav{display:flex;overflow:auto;gap:5px}.nav button{white-space:nowrap;width:auto}.side-foot{display:none}.main{padding:25px 18px}.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.hero h2{font-size:32px}.top h1{font-size:28px}}
</style></head><body><div class="shell"><aside class="side"><div class="brand">FollowUp <span>AI</span></div><div class="eyebrow">Care operations lab</div><nav class="nav"><button class="active" data-page="dashboard">Overview</button><button data-page="reminders">Reminders</button><button data-page="agents">Agent studio</button><button data-page="curriculum">Curriculum</button></nav><div class="side-foot">Local-first prototype<br>SQLite session storage enabled</div></aside><main class="main"><header class="top"><div><div class="eyebrow">Patient follow-up command center</div><h1 id="title">Good morning, care team.</h1></div><div class="date" id="today"></div></header><section class="page active" id="dashboard"><div class="stats" id="stats"></div><div class="grid"><div class="panel"><h2>Next conversations</h2><div id="dash-list"></div></div><div class="panel"><h2>Agent activity</h2><div class="flow"><span class="node">Planner</span><span class="arrow">→</span><span class="node">Memory</span><span class="arrow">→</span><span class="node">Search</span><span class="arrow">→</span><span class="node">Writer</span></div><p class="meta">A transparent pipeline for triage, delegation, research, and a clinician-ready response.</p><button class="action" onclick="showPage('agents')">Open agent studio</button></div></div></section><section class="page" id="reminders"><div class="hero"><div class="eyebrow">Persistent SQLite queue</div><h2>Keep every follow-up in sight.</h2><p>Create, review, and complete patient reminders without losing state between runs.</p></div><div class="grid"><div class="panel"><h2>Reminder queue</h2><div id="reminder-list"></div></div><div class="panel"><h2>New reminder</h2><form id="reminder-form"><label>Patient name<input name="patient" required placeholder="e.g. Anika Rao"></label><div class="two"><label>Phone<input name="phone" placeholder="Optional"></label><label>Due date<input name="due_date" type="date" required></label></div><label>Reason<input name="reason" required placeholder="Medication check-in"></label><label>Notes<textarea name="notes" rows="3" placeholder="Context for the care team"></textarea></label><button class="action">Add reminder</button></form></div></div></section><section class="page" id="agents"><div class="hero"><div class="eyebrow">Multi-agent research assistant</div><h2>Ask once. Route with intention.</h2><p>The demo pipeline records the interaction in SQLite, optionally searches Tavily, and asks Groq to produce a careful answer.</p></div><div class="panel"><form id="agent-form"><label>What should the care team investigate?<textarea name="prompt" rows="3" required placeholder="Draft a non-diagnostic follow-up message for a patient who missed a medication check-in."></textarea></label><button class="action">Run agent pipeline</button></form><div id="agent-result"></div></div></section><section class="page" id="curriculum"><div class="hero"><div class="eyebrow">Learning path</div><h2>From first agent to automation platform.</h2><p>A practical map of the topics in your course, grounded in this patient reminder use case.</p></div><div class="panel" id="modules"></div></section></main></div><script>
const $=s=>document.querySelector(s);const $$=s=>document.querySelectorAll(s);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function showPage(name){$$('.page').forEach(x=>x.classList.toggle('active',x.id===name));$$('.nav button').forEach(x=>x.classList.toggle('active',x.dataset.page===name));const titles={dashboard:'Good morning, care team.',reminders:'Reminder queue.',agents:'Agent studio.',curriculum:'Learning path.'};$('#title').textContent=titles[name];if(name==='dashboard'||name==='reminders')loadReminders()}$$('.nav button').forEach(x=>x.onclick=()=>showPage(x.dataset.page));
function reminder(r){return `<div class="reminder"><div><strong>${esc(r.patient)}</strong><div class="meta">${esc(r.reason)} · ${esc(r.due_date)}${r.phone?' · '+esc(r.phone):''}</div><div class="meta">${esc(r.notes||'')}</div></div><div><span class="tag ${r.status==='Due today'?'due':''}">${esc(r.status)}</span>${r.status!=='Completed'?`<br><button class="action alt" style="margin-top:10px" onclick="complete(${r.id})">Complete</button>`:''}</div></div>`}
async function loadReminders(){const data=await fetch('/api/reminders').then(r=>r.json());const today=new Date().toISOString().slice(0,10);const due=data.filter(r=>r.status!=='Completed'&&r.due_date<=today).length;$('#stats').innerHTML=`<div class="stat"><b>${data.filter(r=>r.status!=='Completed').length}</b><small>Open reminders</small></div><div class="stat"><b>${due}</b><small>Need attention</small></div><div class="stat"><b>${data.filter(r=>r.status==='Completed').length}</b><small>Completed</small></div><div class="stat"><b>7</b><small>Learning modules</small></div>`;$('#dash-list').innerHTML=data.filter(r=>r.status!=='Completed').slice(0,3).map(reminder).join('')||'<p class="meta">All caught up.</p>';$('#reminder-list').innerHTML=data.map(reminder).join('')||'<p class="meta">No reminders yet.</p>'}
async function complete(id){await fetch('/api/reminders/'+id,{method:'PATCH'});loadReminders()}$('#reminder-form').onsubmit=async e=>{e.preventDefault();await fetch('/api/reminders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});e.target.reset();loadReminders()};$('#agent-form').onsubmit=async e=>{e.preventDefault();$('#agent-result').innerHTML='<div class="notice">Planner is coordinating the specialist agents...</div>';const data=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:new FormData(e.target).get('prompt')})}).then(r=>r.json());$('#agent-result').innerHTML=`<div class="meta">${esc(data.pipeline)}${data.results.length?' · '+data.results.length+' web sources':''}</div><div class="answer">${esc(data.answer)}</div>`};
$('#modules').innerHTML=[['01','AI Agent Foundations','Environment setup, first agent, traces, and secure API keys.'],['02','Persistent Agent Memory','SQLite sessions, state management, and multi-turn queries.'],['03','Tools and Real-time Search','Code Interpreter concepts, Tavily, and FunctionTool wrappers.'],['04','Agent Teams','Managers, handoffs, guardrails, AutoGen, LangGraph, and CrewAI.'],['05','Predictive Analytics','EDA, cleaning, encoding, models, R², MAE, and MSE.'],['06','MCP and External Tools','Gradio MCP servers, manifests, clients, and remote execution.'],['07','n8n Automation','Structured outputs, Gmail, Sheets, Calendar, and workflows.']].map(x=>`<div class="module"><div class="module-num">${x[0]}</div><div><h3>${x[1]}</h3><p>${x[2]}</p></div><span class="tag">Included</span></div>`).join('');$('#today').textContent=new Date().toLocaleDateString(undefined,{weekday:'long',month:'short',day:'numeric'});loadReminders();
</script></body></html>'''


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == "/api/reminders":
            connection = database()
            reminders = [dict(row) for row in connection.execute("SELECT * FROM reminders ORDER BY due_date, id")]
            connection.close()
            return json_response(self, reminders)
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if urlparse(self.path).path == "/api/reminders":
            connection = database()
            due_date = payload.get("due_date", str(dt.date.today()))
            status = "Due today" if due_date <= str(dt.date.today()) else "Pending"
            connection.execute("INSERT INTO reminders(patient, phone, due_date, reason, status, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (payload.get("patient", ""), payload.get("phone", ""), due_date, payload.get("reason", ""), status, payload.get("notes", ""), str(dt.datetime.now())))
            connection.commit()
            connection.close()
            return json_response(self, {"ok": True}, 201)
        if urlparse(self.path).path == "/api/ask":
            prompt = payload.get("prompt", "")
            answer, results, pipeline = local_agent_answer(prompt)
            connection = database()
            connection.execute("INSERT INTO sessions(role, content, created_at) VALUES (?, ?, ?)", ("user", prompt, str(dt.datetime.now())))
            connection.execute("INSERT INTO sessions(role, content, created_at) VALUES (?, ?, ?)", ("assistant", answer, str(dt.datetime.now())))
            connection.commit()
            connection.close()
            return json_response(self, {"answer": answer, "results": results, "pipeline": pipeline})
        json_response(self, {"error": "Not found"}, 404)

    def do_PATCH(self):
        reminder_id = urlparse(self.path).path.rsplit("/", 1)[-1]
        connection = database()
        connection.execute("UPDATE reminders SET status = 'Completed' WHERE id = ?", (reminder_id,))
        connection.commit()
        connection.close()
        json_response(self, {"ok": True})

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    seed_data()
    host = os.getenv("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, PORT), AppHandler)
    print(f"FollowUp AI running at http://{host}:{PORT}")
    print("Set GROQ_API_KEY and TAVILY_API_KEY to enable live agent integrations.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()