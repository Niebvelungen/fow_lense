r"""Local labelling page for detected card crops.

Serves one crop at a time next to its top-5 index guesses (from a test_pipeline.py results folder).
Keys: 1-5 pick a guess, u = unknown/illegible, n = not a card, s = skip, b = back,
      d/r/t toggle the tags dice / rotated / rested, type in the search box to pick any card by
      id or name, Enter to save the typed pick.
Labels append to data/labels/crops.jsonl, one JSON object per crop:
  {"crop": "label_yt_user_720p/t00390_crop3.jpg", "card_id": "AVL-097" | "unknown" | "not_card",
   "tags": ["dice"], "video": "...", "t": 390, "box": [x, y, w, h], "top": [...]}

usage: .venv/Scripts/python tools/label_server.py results/label_yt_user_720p [results/label_yt_gp_top4_720p ...]
       then open http://localhost:8765
"""
import argparse, json, os, sys, webbrowser
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(ROOT, 'data', 'labels', 'crops.jsonl')

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Card crop labelling</title>
<style>
 body{font-family:system-ui,sans-serif;background:#1b1d22;color:#e8e8e8;margin:0;padding:16px}
 .row{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
 .crop img{width:260px;image-rendering:auto;border:2px solid #555;border-radius:6px;background:#000}
 .cand{display:flex;flex-direction:column;align-items:center;cursor:pointer;padding:6px;border-radius:8px;border:2px solid transparent}
 .cand img{width:150px;border-radius:4px}
 .cand:hover{border-color:#6cf}.cand.picked{border-color:#4f4}
 .k{display:inline-block;background:#333;border-radius:4px;padding:1px 7px;margin-right:6px;font-weight:bold}
 .meta{color:#aaa;font-size:13px;margin-top:6px}
 .tags span{display:inline-block;padding:3px 10px;border-radius:12px;background:#333;margin-right:6px;color:#999}
 .tags span.on{background:#c60;color:#fff}
 input{width:340px;padding:6px;font-size:15px;background:#111;color:#eee;border:1px solid #555;border-radius:4px}
 #results div{padding:4px 6px;cursor:pointer}#results div:hover,#results div.sel{background:#345}
 .bar{display:flex;gap:18px;align-items:center;margin-bottom:12px}
 button{background:#333;color:#eee;border:1px solid #666;border-radius:4px;padding:6px 12px;cursor:pointer}
</style></head><body>
<div class="bar"><b id="progress"></b><span id="stats"></span>
 <span><span class="k">1-5</span>pick <span class="k">u</span>unknown <span class="k">n</span>not a card <span class="k">s</span>skip <span class="k">b</span>back <span class="k">d</span>dice <span class="k">r</span>rotated <span class="k">t</span>rested <span class="k">/</span>search</span></div>
<div class="row">
 <div class="crop"><img id="crop"><div class="meta" id="meta"></div>
  <div class="tags" style="margin-top:8px"><span id="tag-dice">dice</span><span id="tag-rotated">rotated</span><span id="tag-rested">rested</span></div>
  <div style="margin-top:10px"><input id="search" placeholder="search card id or name, Enter to pick"><div id="results"></div></div>
 </div>
 <div class="row" id="cands"></div>
</div>
<script>
let items=[], idx=0, tags=new Set(), cards=[], sel=-1, done={};
const $=id=>document.getElementById(id);
async function load(){
  items=await (await fetch('/api/items')).json();
  cards=await (await fetch('/api/cards')).json();
  done=await (await fetch('/api/done')).json();
  idx=items.findIndex(it=>!done[it.crop]); if(idx<0) idx=0;
  show();
}
function show(){
  const it=items[idx]; if(!it){$('progress').textContent='no items';return;}
  tags=new Set(done[it.crop]?.tags||[]);
  $('progress').textContent=`${idx+1} / ${items.length}`;
  const n=Object.keys(done).length; $('stats').textContent=`labelled ${n}` + (done[it.crop]?`  (this one: ${done[it.crop].card_id})`:'');
  $('crop').src='/crop/'+encodeURIComponent(it.crop);
  $('meta').textContent=`${it.video} t=${it.t}s  box w=${(it.box[2]*100).toFixed(1)}%  det=${it.det}`;
  const c=$('cands'); c.innerHTML='';
  it.top.forEach((g,i)=>{const d=document.createElement('div');d.className='cand';
    d.innerHTML=`<div><span class="k">${i+1}</span>${g.score.toFixed(2)}</div><img src="/card/${encodeURIComponent(g.id)}"><div style="font-size:12px;max-width:150px;text-align:center">${g.name}<br><span style="color:#888">${g.id}</span></div>`;
    d.onclick=()=>save(g.id); c.appendChild(d);});
  for(const t of ['dice','rotated','rested']) $('tag-'+t).className=tags.has(t)?'on':'';
  $('search').value=''; $('results').innerHTML=''; sel=-1;
}
async function save(card_id){
  const it=items[idx];
  const rec={crop:it.crop,card_id,tags:[...tags],video:it.video,t:it.t,box:it.box,det:it.det,top:it.top.map(g=>({id:g.id,score:g.score}))};
  await fetch('/api/label',{method:'POST',body:JSON.stringify(rec)});
  done[it.crop]=rec; next();
}
function next(){ if(idx<items.length-1){idx++;show();} }
function toggle(t){ if(tags.has(t)) tags.delete(t); else tags.add(t); $('tag-'+t).className=tags.has(t)?'on':''; }
function search(q){
  q=q.toLowerCase().trim(); const r=$('results'); r.innerHTML=''; if(q.length<2) return;
  const hits=cards.filter(c=>c.id.toLowerCase().includes(q)||c.name.toLowerCase().includes(q)).slice(0,8);
  hits.forEach((c,i)=>{const d=document.createElement('div');d.textContent=`${c.id}  ${c.name}`;d.onclick=()=>save(c.id);r.appendChild(d);});
  sel=hits.length?0:-1; hl();
}
function hl(){ [...$('results').children].forEach((d,i)=>d.className=i===sel?'sel':''); }
document.addEventListener('keydown',e=>{
  const inSearch=document.activeElement===$('search');
  if(inSearch){
    if(e.key==='Escape'){$('search').blur();return;}
    if(e.key==='ArrowDown'){sel=Math.min(sel+1,$('results').children.length-1);hl();e.preventDefault();return;}
    if(e.key==='ArrowUp'){sel=Math.max(sel-1,0);hl();e.preventDefault();return;}
    if(e.key==='Enter'){const d=$('results').children[sel]; if(d) d.click(); e.preventDefault();}
    return;
  }
  const it=items[idx]; if(!it) return;
  if(e.key>='1'&&e.key<='5'){const g=it.top[+e.key-1]; if(g) save(g.id);}
  else if(e.key==='u') save('unknown');
  else if(e.key==='n') save('not_card');
  else if(e.key==='s') next();
  else if(e.key==='b'){ if(idx>0){idx--;show();} }
  else if(e.key==='d') toggle('dice'); else if(e.key==='r') toggle('rotated'); else if(e.key==='t') toggle('rested');
  else if(e.key==='/'){ $('search').focus(); e.preventDefault(); }
});
$('search').addEventListener('input',e=>search(e.target.value));
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    items, cards, media, results = [], [], '', {}

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/':
            return self.send(200, PAGE.encode('utf-8'), 'text/html; charset=utf-8')
        if u.path == '/api/items':
            return self.send(200, json.dumps(self.items).encode())
        if u.path == '/api/cards':
            return self.send(200, json.dumps(self.cards).encode())
        if u.path == '/api/done':
            return self.send(200, json.dumps(load_labels()).encode())
        if u.path.startswith('/crop/'):
            rel = unquote(u.path[6:])
            folder, name = rel.split('/', 1)
            path = os.path.join(self.results[folder], name)
            return self.file(path)
        if u.path.startswith('/card/'):
            cid = unquote(u.path[6:])
            img = self.card_image.get(cid)
            return self.file(os.path.join(self.media, img)) if img else self.send(404, b'')
        self.send(404, b'')

    def file(self, path):
        try:
            with open(path, 'rb') as f:
                self.send(200, f.read(), 'image/jpeg')
        except OSError:
            self.send(404, b'')

    def do_POST(self):
        if urlparse(self.path).path != '/api/label':
            return self.send(404, b'')
        n = int(self.headers.get('Content-Length', 0))
        rec = json.loads(self.rfile.read(n))
        os.makedirs(os.path.dirname(LABELS), exist_ok=True)
        with open(LABELS, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        self.send(200, b'{"ok":true}')


def load_labels():
    done = {}
    if os.path.exists(LABELS):
        for line in open(LABELS, encoding='utf-8'):
            if line.strip():
                rec = json.loads(line)
                done[rec['crop']] = rec  # last label for a crop wins
    return done


def collect_items(result_dirs):
    items, results = [], {}
    for d in result_dirs:
        d = d.rstrip('/\\')
        key = os.path.basename(d)
        results[key] = d
        video = key.replace('label_', '')
        for f in json.load(open(os.path.join(d, 'summary.json'), encoding='utf-8')):
            for i, b in enumerate(f['boxes']):
                name = f"t{int(f['t']):05d}_crop{i}.jpg"
                if os.path.exists(os.path.join(d, name)):
                    items.append({'crop': f"{key}/{name}", 'video': video, 't': f['t'], 'box': b['box'],
                                  'det': b['det'], 'top': b['top']})
    return items, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results', nargs='+', help='test_pipeline.py result folders')
    ap.add_argument('--cards', default=os.path.join(ROOT, 'extension', 'data', 'cards.json'))
    ap.add_argument('--media', default=os.path.join(ROOT, 'media', 'cards'))
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    cards = json.load(open(a.cards, encoding='utf-8'))
    Handler.cards = [{'id': c['id'], 'name': c['name']} for c in cards]
    Handler.card_image = {c['id']: c['image'] for c in cards if c.get('image')}
    Handler.media = a.media
    Handler.items, Handler.results = collect_items(a.results)
    print(f"{len(Handler.items)} crops from {len(a.results)} folders, labels -> {LABELS}")
    srv = HTTPServer(('127.0.0.1', a.port), Handler)
    url = f"http://localhost:{a.port}/"
    print("serving", url)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
