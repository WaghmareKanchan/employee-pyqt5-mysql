"""
The page behind the invitation link: GET /setup-password?token=...
A tiny self-contained HTML page (no web front-end needed) that talks to
the public endpoints in routers/auth.py. The desktop app is for logging in
afterwards.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["setup"])

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Set your password</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;background:#f3f4f6;margin:0;padding:24px}
 .card{max-width:420px;margin:40px auto;background:#fff;border-radius:10px;padding:28px;box-shadow:0 2px 10px #0001}
 h2{margin-top:0} label{display:block;margin:14px 0 4px;font-size:14px;color:#374151}
 input{width:100%;box-sizing:border-box;padding:10px;border:1px solid #d1d5db;border-radius:6px;font-size:15px}
 button{margin-top:20px;width:100%;padding:11px;background:#2563eb;color:#fff;border:0;border-radius:6px;font-size:15px;cursor:pointer}
 button:disabled{opacity:.6} .err{color:#b91c1c;margin-top:14px;font-size:14px} .ok{color:#047857}
 .hint{font-size:12px;color:#6b7280;margin-top:6px}
</style></head><body><div class="card" id="card"><p>Checking your link&hellip;</p></div>
<script>
const token = new URLSearchParams(location.search).get("token") || "";
const card = document.getElementById("card");
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function msg(d){ if(!d) return "Something went wrong."; if(typeof d==="string") return d;
  if(Array.isArray(d)) return d.map(x=>(x.msg||"").replace("Value error, ","")).join(" "); return "Something went wrong."; }
async function init(){
  try{
    const r = await fetch("/api/auth/setup-password/check?token="+encodeURIComponent(token));
    const d = await r.json();
    if(!r.ok){ card.innerHTML = "<h2>Link problem</h2><p class='err'>"+esc(msg(d.detail))+"</p>"; return; }
    card.innerHTML = `<h2>Welcome, ${esc(d.full_name)}</h2>
      <p>Your login ID is <b>${esc(d.login_id)}</b></p>
      <label>New password</label><input type="password" id="p1" autocomplete="new-password">
      <div class="hint">At least 8 characters, with an uppercase letter, a number and a special character.</div>
      <label>Confirm password</label><input type="password" id="p2" autocomplete="new-password">
      <button id="go">Set password</button><div id="out"></div>`;
    document.getElementById("go").onclick = submit;
  }catch(e){ card.innerHTML = "<p class='err'>Could not reach the server.</p>"; }
}
async function submit(){
  const btn=document.getElementById("go"), out=document.getElementById("out"); btn.disabled=true; out.textContent="";
  try{
    const r = await fetch("/api/auth/setup-password",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({token,new_password:p1.value,confirm_password:p2.value})});
    const d = await r.json();
    if(!r.ok){ out.className="err"; out.textContent=msg(d.detail); btn.disabled=false; return; }
    card.innerHTML = "<h2 class='ok'>Password set &#10003;</h2><p>Open the Meridian Systems app and log in with <b>"+esc(d.login_id)+"</b> and your new password.</p>";
  }catch(e){ out.className="err"; out.textContent="Could not reach the server."; btn.disabled=false; }
}
init();
</script></body></html>"""


@router.get("/setup-password", response_class=HTMLResponse, include_in_schema=False)
def setup_password_page():
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store"})
