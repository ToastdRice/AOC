import os, uuid, json, time, threading, requests, logging, hmac, hashlib, re
from urllib.parse import urlparse
from flask import Flask, request, Response, abort, make_response

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hopsec-api")

FAC = os.environ.get("FACILITY", "HopSec Asylumn")
API_SECRET = os.environ.get("API_SECRET", "d3vs3cr3t_2932932")
VIDEO_STATE_DIR = os.environ.get("VIDEO_STATE_DIR", "/app/state/video")
TOKEN_DIR = os.environ.get("REPL_TOKEN_DIR", "/opt/hopsec-asylumn/hopsec-asylumn/state")
TICKETS = {}
JOBS = {}

SEG_RE = re.compile(r"^[A-Za-z0-9._-]+\.(ts|m4s)$")

def _mint(payload_json: str) -> str:
    sig = hmac.new(API_SECRET.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    return payload_json + "." + sig

def _verify(token: str):
    try:
        payload, sig = token.rsplit(".", 1)
        expect = hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return None
        return json.loads(payload)
    except Exception:
        return None

def cors(resp):
    origin = request.headers.get("Origin", "")
    host = request.headers.get("Host", "")
    api_host = host.split(":")[0] if host else ""
    allowed = f"http://{api_host}:13400"
    if origin == allowed:
        resp.headers["Access-Control-Allow-Origin"] = allowed
        resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type,Range"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Expose-Headers"] = "Content-Range,Accept-Ranges"
    return resp

@app.after_request
def aresp(r):
    return cors(r)

@app.errorhandler(401)
def eh401(e):
    p = request.path
    if p.startswith("/v1/streams/") and ("/manifest" in p or "/seg/" in p):
        return make_response("not found", 404)
    return make_response("unauthorized", 401)

@app.route("/v1/auth/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS": return ("", 200)
    d = request.get_json(silent=True) or {}
    u = d.get("username"); p = d.get("password")
    if u == "guard.hopkins@hopsecasylum.com" and p == "Johnnyboy1982!":
        role = "guard"
    elif u == "admin" and p == "A$ylUmN3tw0rk!2025^Admin#777":
        role = "admin"
    else:
        return make_response({"error": "bad credentials"}, 401)
    payload = json.dumps({"sub": u, "role": role, "iat": int(time.time())})
    tok = _mint(payload)
    return make_response({"facility": FAC, "profile": {"role": role, "username": u}, "token": tok}, 200)

def parse_profile():
    ah = request.headers.get("Authorization", "")
    if not ah.startswith("Bearer "): return {}
    t = ah.split(" ", 1)[1]
    prof = _verify(t)
    return prof or {}

@app.route("/v1/cameras", methods=["GET", "OPTIONS"])
def cameras():
    if request.method == "OPTIONS": return ("", 200)
    p = parse_profile()
    if not p: return make_response({"error": "unauthorized"}, 401)
    cams = [
        {"id": "cam-lobby",   "name": "Lobby",       "desc": "Ward A entrance corridor",      "site": "HopSec Asylumn", "required_role": "guard"},
        {"id": "cam-loading", "name": "Supply Loading Dock 2",    "desc": "Service bay and cages",         "site": "HopSec Asylumn", "required_role": "guard"},
        {"id": "cam-parking", "name": "Cell Block",         "desc": "Jester Cell Block",        "site": "HopSec Asylumn", "required_role": "guard"},
        {"id": "cam-admin",   "name": "Psych Ward Exit",       "desc": "Psych Ward Exit Gate",            "site": "HopSec HQ",      "required_role": "admin"},
    ]
    return {"cameras": cams}

def merge_params():
    body = request.get_json(silent=True) or {}
    eff = dict(body)
    for k in request.args:
        eff[k] = request.args.get(k)
    return body, eff

def normalize_tier(x):
    if not x: return ""
    v = str(x).strip().lower()
    if v in ("preview", "guard"): return "guard"
    if v in ("internal", "admin"): return "admin"
    return v

@app.route("/v1/streams/request", methods=["POST", "OPTIONS"])
def streams_request():
    if request.method == "OPTIONS": return ("", 200)
    p = parse_profile()
    if not p: return make_response({"error": "unauthorized"}, 401)

    body = request.get_json(silent=True) or {}
    cam = (body.get("camera_id") or request.args.get("camera_id") or "")

    body_tier = normalize_tier(body.get("tier"))
    query_tier = normalize_tier(request.args.get("tier"))
    tier = query_tier or body_tier
    if body_tier == "admin" and query_tier != "admin" and p.get("role") != "admin":
        tier = "guard"

    et = tier
    if cam != "cam-admin" and et == "admin":
        et = "guard"

    stream = "cam-public"
    if cam == "cam-admin" and et == "admin":
        stream = "cam-admin"

    tid = str(uuid.uuid4())
    TICKETS[tid] = {"stream": stream, "tier": et, "exp": time.time() + 600}
    log.info(json.dumps({
        "event": "streams.request",
        "facility": FAC,
        "actor": p.get("sub", "?"),
        "body_tier": body_tier,
        "effective_tier": et,
        "camera": cam
    }))
    return {"effective_tier": et, "ticket_id": tid}

def get_ticket(tid):
    t = TICKETS.get(tid)
    if not t: return None
    if t["exp"] < time.time(): return None
    return t

def fetch_manifest(stream):
    url = f"http://localhost:13402/hls/{stream}/playlist.m3u8"
    r = requests.get(url, timeout=5)
    if r.status_code != 200: abort(502)
    return r.text

def rewrite_manifest(tid, txt, stream):
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip() != ""]
    headers, pairs = [], []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            if ln.startswith("#EXTINF:"):
                dur = ln
                j = i + 1
                while j < len(lines) and lines[j].startswith("#"):
                    j += 1
                if j < len(lines):
                    seg = lines[j].split("/")[-1]
                    pairs.append((dur, seg))
                    i = j + 1
                    continue
            elif ln.startswith("#EXT-X-ENDLIST"):
                i += 1
                continue
            else:
                headers.append(ln)
                i += 1
                continue
        else:
            pairs.append(("#EXTINF:2.000000,", ln.split("/")[-1]))
            i += 1
    out = []
    if not any(h.startswith("#EXTM3U") for h in headers):
        out.append("#EXTM3U")
    out.extend(headers)
    out.append('#EXT-X-START:TIME-OFFSET=0,PRECISE=YES')
    if stream == "cam-admin":
        out.append('#EXT-X-SESSION-DATA:DATA-ID="hopsec.diagnostics",VALUE="/v1/ingest/diagnostics"')
        out.append('#EXT-X-DATERANGE:ID="hopsec-diag",CLASS="hopsec-diag",START-DATE="1970-01-01T00:00:00Z",X-RTSP-EXAMPLE="rtsp://vendor-cam.test/cam-admin"')
        out.append('#EXT-X-SESSION-DATA:DATA-ID="hopsec.jobs",VALUE="/v1/ingest/jobs"')
    loops = int(os.environ.get("PUBLIC_LOOP_COUNT" if stream=="cam-public" else "ADMIN_LOOP_COUNT", "600"))
    for loop_index in range(loops):
        if loop_index > 0:
            out.append("#EXT-X-DISCONTINUITY")
        for dur, seg in pairs:
            out.append(dur)
            out.append(f"/v1/streams/{tid}/seg/{seg}?r={loop_index}")
    return "\n".join(out) + "\n"

@app.route("/v1/streams/<tid>/manifest", methods=["GET","HEAD","OPTIONS"])
@app.route("/v1/streams/<tid>/manifest.m3u8", methods=["GET","HEAD","OPTIONS"])
def stream_manifest(tid):
    if request.method == "OPTIONS": return ("", 200)
    t = get_ticket(tid)
    if not t: return make_response("not found", 404)
    raw = fetch_manifest(t["stream"])
    rew = rewrite_manifest(tid, raw, t["stream"])
    log.info(json.dumps({"event":"manifest.serve","tid":tid,"stream":t["stream"]}))
    resp = make_response(rew, 200)
    resp.headers["Content-Type"] = "application/vnd.apple.mpegurl"
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/v1/streams/<tid>/seg/<path:name>", methods=["GET","HEAD","OPTIONS"])
def stream_segment(tid, name):
    if request.method == "OPTIONS": return ("", 200)
    t = get_ticket(tid)
    if not t: return make_response("not found", 404)
    if not SEG_RE.match(name): abort(400)
    origin_url = f"http://localhost:13402/hls/{t['stream']}/{name}"
    headers = {}
    rng = request.headers.get("Range")
    if rng:
        headers["Range"] = rng
    rr = requests.get(origin_url, headers=headers, stream=True, timeout=5)
    if rr.status_code not in (200, 206):
        abort(404)
    log.info(json.dumps({"event": "segment.proxy", "tid": tid, "name": name, "range": rng or ""}))
    def gen():
        for c in rr.iter_content(chunk_size=8192):
            if c: yield c
    resp = Response(gen(), status=rr.status_code)
    resp.headers["Content-Type"] = rr.headers.get("Content-Type", "video/MP2T")
    if "Content-Range" in rr.headers:
        resp.headers["Content-Range"] = rr.headers["Content-Range"]
    resp.headers["Accept-Ranges"] = rr.headers.get("Accept-Ranges", "bytes")
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/v1/ingest/probe", methods=["GET","OPTIONS"])
def ingest_probe():
    if request.method == "OPTIONS": return ("", 200)
    p = parse_profile()
    if not p: return make_response({"error":"unauthorized"},401)
    rtsp = request.args.get("rtsp_url","")
    if not rtsp: return make_response({"error":"missing rtsp_url"},400)
    describe = f"http://localhost:13403/describe?path={rtsp}"
    r = requests.get(describe, timeout=5)
    if r.status_code != 200:
        return make_response({"error":"probe_failed","status":r.status_code}, 502)
    resp = make_response(r.text, 200)
    resp.headers["Content-Type"] = "text/plain"
    return resp

@app.route("/v1/ingest/diagnostics", methods=["POST","OPTIONS"])
def ingest_diag():
    if request.method == "OPTIONS": return ("", 200)
    p = parse_profile()
    if not p: return make_response({"error":"unauthorized"},401)
    body, eff = merge_params()
    body_url = body.get("rtsp_url","")
    try:
        host = urlparse(body_url).hostname
    except:
        host = None
    if host != "vendor-cam.test":
        return make_response({"error":"invalid rtsp_url"},400)
    rtsp = body_url
    jid = str(uuid.uuid4())
    JOBS[jid] = {"rtsp_url": rtsp, "status": "pending", "token": None, "ts": time.time()}
    log.info(json.dumps({
        "event":"ingest.schedule","facility":FAC,
        "actor":p.get("sub","?"),"body_rtsp_url": body_url,
        "effective_rtsp_url": rtsp, "has_probe_sdp": bool(body.get("probe_sdp"))
    }))
    threading.Thread(target=run_job, args=(jid, body.get("probe_sdp")), daemon=True).start()
    status_url = f"/v1/ingest/jobs/{jid}"
    resp = make_response({"job_id": jid, "job_status": status_url}, 200)
    resp.headers["Location"] = status_url
    return resp

@app.route("/v1/ingest/jobs/<jid>", methods=["GET","OPTIONS"])
def job_status(jid):
    if request.method == "OPTIONS": return ("", 200)
    p = parse_profile()
    if not p: return make_response({"error":"unauthorized"},401)
    j = JOBS.get(jid)
    if not j: return make_response({"error":"not found"},404)
    resp = {"status": j["status"], "rtsp_url": j["rtsp_url"]}
    if j.get("token"):
        resp["token"] = j["token"]
        resp["console_port"] = 13404
    if j.get("error"):
        resp["error"] = j["error"]
    return resp

def start_console(token: str) -> None:
    from pathlib import Path
    d = Path(TOKEN_DIR)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"repl-{token}.token"
    with open(p, "w") as f:
        f.write(token + "\n")
    os.chmod(p, 0o664)

def parse_sdp_for_exec(sdp_text):
    try:
        for raw in sdp_text.splitlines():
            x = raw.strip()
            if not x.lower().startswith("a=x-job-metadata:"):
                continue
            payload = x.split(":", 1)[1].strip().rstrip(",;")
            meta = json.loads(payload)
            return bool(meta.get("SIM_EXEC", False))
    except Exception:
        return False
    return False

def run_job(jid, probe_sdp=None):
    try:
        os.makedirs(VIDEO_STATE_DIR, exist_ok=True)
        os.makedirs(os.path.join(VIDEO_STATE_DIR, "home", "camera_user"), exist_ok=True)
        def _ready():
            tok = uuid.uuid4().hex
            JOBS[jid]["token"] = tok
            JOBS[jid]["status"] = "ready"
            start_console(tok)
            log.info(json.dumps({"event":"ingest.shell_ready","facility":FAC,"job_id":jid}))

        if probe_sdp:
            try:
                if parse_sdp_for_exec(probe_sdp):
                    _ready()
                else:
                    JOBS[jid]["status"] = "complete"
            except Exception as e:
                JOBS[jid]["status"] = "error"
                JOBS[jid]["error"] = f"parse_sdp: {type(e).__name__}: {e}"
            return
        rtsp = JOBS[jid]["rtsp_url"]
        u = f"http://localhost:13403/describe?path={rtsp}"
        try:
            r = requests.get(u, timeout=5)
        except Exception as e:
            JOBS[jid]["status"] = "error"; JOBS[jid]["error"] = f"http_get_sdp: {type(e).__name__}: {e}"
            return
        if r.status_code != 200:
            JOBS[jid]["status"] = "error"; JOBS[jid]["error"] = f"sdp_status:{r.status_code}"
            return
        try:
            if parse_sdp_for_exec(r.text):
                _ready()
            else:
                JOBS[jid]["status"] = "complete"
        except Exception as e:
            JOBS[jid]["status"] = "error"; JOBS[jid]["error"] = f"parse_sdp: {type(e).__name__}: {e}"
    except Exception as e:
        JOBS[jid]["status"] = "error"
        JOBS[jid]["error"] = f"run_job: {type(e).__name__}: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=13401)
