from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def rw(path,old,new):
    p=ROOT/path;text=p.read_text(encoding='utf-8')
    if old not in text: raise RuntimeError(f'missing marker: {path}: {old[:80]}')
    p.write_text(text.replace(old,new,1),encoding='utf-8')

# CPAP overlay: keep the primary CPAP axis untouched and show compact secondary
# O2/HR scale labels at the right edge without adding aggressive extra axes.
rw('web/o2ring.js',
   "function drawOverlayCanvas(c,key,mode){",
   "function drawOverlayScaleLabels(ctx,w,h,p,mode,hrLo,hrHi){ctx.save();ctx.font='9px system-ui';ctx.textAlign='right';if(mode==='spo2'||mode==='both'){ctx.fillStyle=COLORS.spo2;ctx.fillText('O₂ 100%',w-5,p.t+8);ctx.fillText('O₂ 75%',w-5,p.t+(h-p.t-p.b)-2)}if(mode==='hr'||mode==='both'){ctx.fillStyle=COLORS.hr;ctx.fillText(`HR ${hrHi}`,w-5,p.t+(mode==='both'?20:8));ctx.fillText(`HR ${hrLo}`,w-5,p.t+(h-p.t-p.b)-(mode==='both'?14:2))}ctx.restore()}\nfunction drawOverlayCanvas(c,key,mode){")
rw('web/o2ring.js',
   "let ht=null;try{ht=num(state.hoverTime);",
   "drawOverlayScaleLabels(ctx,w,h,p,mode,hrLo,hrHi);let ht=null;try{ht=num(state.hoverTime);")

# Auto-match is a real toggle: first click persists immediately. Device-owned
# alarm switches still require the explicit device Apply button by design.
rw('web/frontend-v534.js',
   "id('smO2SaveAnalysis').onclick=saveAdvancedO2Settings;\n  id('smO2WriteDevice').onclick=writeO2DeviceSettings;",
   "id('smO2SaveAnalysis').onclick=saveAdvancedO2Settings;\n  id('smO2AutoMatch').onchange=saveAdvancedO2Settings;\n  id('smO2WriteDevice').onclick=writeO2DeviceSettings;")

# Explicit responsive settings layout; appended rules intentionally centralize
# the advanced O2Ring form instead of relying on incidental browser flow.
p=ROOT/'web/o2ring-v534.css';css=p.read_text(encoding='utf-8')
block="""
/* v5.3.4 O2Ring settings acceptance layout */
.sm-o2-advanced,.sm-o2-device-details{min-width:0}.sm-o2-advanced-grid,.sm-o2-device-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.sm-o2-advanced-grid>label,.sm-o2-device-grid>label{display:grid;grid-template-columns:minmax(0,1fr);gap:5px;align-content:start;padding:10px;border:1px solid rgba(91,170,209,.16);border-radius:11px;background:rgba(6,15,25,.46);min-width:0}.sm-o2-advanced-grid label>span,.sm-o2-device-grid label>span{font-size:11px;font-weight:700}.sm-o2-advanced-grid label>small{font-size:9px;color:#91a8bb;line-height:1.35}.sm-o2-advanced-grid input,.sm-o2-device-grid input,.sm-o2-device-grid select{width:100%;min-width:0;box-sizing:border-box}.sm-o2-advanced-grid .sm-o2-check,.sm-o2-device-grid .sm-o2-check{grid-template-columns:minmax(0,1fr) auto;column-gap:10px}.sm-o2-advanced-grid .sm-o2-check input,.sm-o2-device-grid .sm-o2-check input{width:auto;justify-self:end;align-self:center;grid-column:2;grid-row:1/3}.sm-o2-device-details{margin-top:10px}.sm-o2-device-details summary{cursor:pointer;font-weight:700}.sm-o2-settings-panel .settings-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
@media(max-width:700px){.sm-o2-advanced-grid,.sm-o2-device-grid{grid-template-columns:1fr}.sm-o2-advanced-grid>label,.sm-o2-device-grid>label{padding:9px}.sm-o2-settings-panel .settings-actions>button{width:100%}}
"""
if 'v5.3.4 O2Ring settings acceptance layout' not in css:
    p.write_text(css+'\n'+block,encoding='utf-8')

# Acceptance guards for the final details.
p=ROOT/'tests/test_o2ring_v534_release_contract.py';t=p.read_text(encoding='utf-8')
extra="""

def test_v534_overlay_has_compact_secondary_o2_hr_scale_labels():
    js=read('web/o2ring.js')
    assert 'function drawOverlayScaleLabels' in js
    assert "O₂ 100%" in js and "O₂ 75%" in js
    assert 'HR ${hrHi}' in js and 'HR ${hrLo}' in js


def test_v534_auto_match_toggle_saves_on_first_change_and_settings_grid_is_responsive():
    js=read('web/frontend-v534.js');css=read('web/o2ring-v534.css')
    assert "id('smO2AutoMatch').onchange=saveAdvancedO2Settings" in js
    assert '.sm-o2-advanced-grid,.sm-o2-device-grid{display:grid' in css
    assert '@media(max-width:700px)' in css


def test_v534_sleepsync_nested_import_changed_days_are_targeted():
    value={'import':{'changed_days':['20260901','20260902'],'changed_files':['DATALOG/20260902/x.edf']}}
    assert _extract_day_codes(value)=={'20260901','20260902'}
"""
if 'test_v534_overlay_has_compact_secondary_o2_hr_scale_labels' not in t:
    p.write_text(t+extra,encoding='utf-8')

print('final v5.3.4 acceptance polish applied')
