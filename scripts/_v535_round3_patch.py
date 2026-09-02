from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p): return (ROOT/p).read_text(encoding='utf-8')
def write(p,t): (ROOT/p).write_text(t,encoding='utf-8')
def rep(p,a,b):
    t=read(p); n=t.count(a)
    if n!=1: raise SystemExit(f'{p}: expected 1, got {n}: {a[:120]!r}')
    write(p,t.replace(a,b,1))

js='web/o2ring.js'
old='''<div class="o2r-hero-actions"><button id="o2rDash" type="button">← Dashboard</button><button id="o2rConnectNow" type="button">＋ Kapcsolódás</button><button id="o2rSyncNowTop" type="button">↻ Szinkron</button></div></section><div class="o2r-tabs"><button data-o2r-tab="live" class="active">Élő O₂ monitor</button><button data-o2r-tab="recordings">Felvételek</button><button data-o2r-tab="trends">Trendek</button></div>'''
new='''<div class="o2r-hero-actions"><button id="o2rDash" type="button">← Dashboard</button><button id="o2rConnectNow" type="button">＋ Kapcsolódás</button><button id="o2rSyncNowTop" type="button">↻ Szinkron</button><button data-o2r-tab="live" class="active">Élő O₂ monitor</button><button data-o2r-tab="recordings">Felvételek</button><button data-o2r-tab="trends">Trendek</button></div><div class="o2r-search-state"><span>Keresés állapota</span><strong id="o2rLiveState">–</strong><small id="o2rLiveSignal">jel –</small></div></section>'''
rep(js,old,new)
rep(js,'<article class="panel o2r-live-card state"><label>Állapot</label><strong id="o2rLiveState">–</strong><small id="o2rLiveSignal">jel –</small></article>','')

# Desktop live cards are now the three actual measurements; state is compact under Search/Connect.
rep('web/o2ring.css','.o2r-live-cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:12px}', '.o2r-live-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:12px}')
css=read('web/o2ring-v534.css')
css += '''\n/* v5.3.5 Oximetria unified toolbar + search state */\n.o2r-search-state{display:flex;align-items:center;gap:9px;margin-top:9px;padding:7px 10px;border-radius:10px;border:1px solid rgba(82,220,255,.16);background:rgba(6,15,25,.38);width:max-content;max-width:100%;font-size:10px;color:#90a9bb}.o2r-search-state span{color:#7892a6}.o2r-search-state strong{font-size:11px;color:#dff7ff}.o2r-search-state small{font-size:9px;color:#7be8ff}.o2r-hero-actions [data-o2r-tab]{margin-left:0}.o2r-hero-actions [data-o2r-tab].active{background:#203449;color:#77ceff;border-color:#4b7795}@media(max-width:700px){.o2r-search-state{width:100%;box-sizing:border-box}.o2r-hero-actions{gap:6px}.o2r-hero-actions button{flex:1 1 auto}}\n'''
write('web/o2ring-v534.css',css)

p='tests/test_v535_polish_contract.py'; t=read(p)
t += '''\n\ndef test_v535_oximetry_navigation_is_one_toolbar_and_state_is_not_a_card():\n    js=read("web/o2ring.js"); css=read("web/o2ring-v534.css")\n    page=js[js.index("function installPage"):js.index("function closeMobileO2Drawer")]\n    assert 'id="o2rSyncNowTop"' in page\n    assert page.index('id="o2rSyncNowTop"') < page.index('data-o2r-tab="live"') < page.index('data-o2r-tab="recordings"') < page.index('data-o2r-tab="trends"')\n    assert 'class="o2r-tabs"' not in page\n    assert 'class="panel o2r-live-card state"' not in page\n    assert 'class="o2r-search-state"' in page\n    assert 'id="o2rLiveState"' in page and 'id="o2rLiveSignal"' in page\n    assert '.o2r-search-state' in css\n'''
write(p,t)
print('v5.3.5 round 3 patch applied')
