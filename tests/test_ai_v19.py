from pathlib import Path
import json, tempfile, sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from cpap.ai_store import AIStore
from cpap.ai_payload import build_safe_payload, analysis_prompts
from cpap.patient_store import PatientStore
from cpap.resmed import ResMedDataset

html=(root/'web'/'index.html').read_text(encoding='utf-8')
js=(root/'web'/'app-core.js').read_text(encoding='utf-8')
css=(root/'web'/'style.css').read_text(encoding='utf-8')
provider_src=(root/'cpap'/'ai_provider.py').read_text(encoding='utf-8')

assert 'data-page="ai"' in html and 'id="page-ai"' in html
assert 'Luna' in html and 'Milo' in html and 'Groq' in html
assert 'aiHistoryList' in html and 'Korábbi AI-kiértékelések' in html
assert 'settingGeminiKey' in html and 'settingGroqKey' in html
assert 'settings-inner-tabs' in html and 'data-settings-tab="ai"' in html
assert 'analysis-stream' in js and 'chat-stream' in js and 'openAIHistory' in js
assert 'milo-avatar.svg' in html and '.ai-history-card' in css
assert 'api.groq.com/openai/v1/chat/completions' in provider_src
assert 'streamGenerateContent?alt=sse' in provider_src

with tempfile.TemporaryDirectory() as td:
    base=Path(td)
    store=AIStore(base)
    cfg=store.save_provider_config({
        'gemini_api_key':'gem-secret-1234567890','groq_api_key':'gsk-secret-abcdef123456',
        'gemini_display_name':'Luna','groq_display_name':'Milo',
    })
    assert cfg['providers']['gemini']['configured'] is True
    assert cfg['providers']['groq']['configured'] is True
    assert cfg['providers']['gemini']['model']=='gemini-3.6-flash'
    assert cfg['providers']['groq']['model']=='openai/gpt-oss-120b'
    blob=(base/'private'/'ai_secrets.bin').read_bytes()
    assert b'gem-secret' not in blob and b'gsk-secret' not in blob

    patient=PatientStore(base)
    patient.save_profile({'name':'TILOS NÉV','taj':'123456788','birth_date':'1990-01-02','therapy_start_date':'2026-08-01'})
    patient.save_record('diagnosis', {'date':'2026-08-01','diagnosis_type':'OSA','ahi':54.2})
    patient.save_record('device', {'manufacturer':'ResMed','model':'AirSense 11 AutoSet','serial_number':'SERIAL-TILOS','active':True})
    ds=ResMedDataset(root/'testdata')
    payload,meta=build_safe_payload(ds,patient,'night','')
    text=json.dumps(payload,ensure_ascii=False).lower()
    assert 'tilos név' not in text and '123456788' not in text and 'serial-tilos' not in text
    assert payload['anonymous_profile']['age_years'] is not None
    assert payload['days'][0]['ahi']==0.54
    system,user=analysis_prompts('night',payload)
    assert 'live_text' in system and 'ANONIM TERÁPIÁS JSON' in user

    sig='dataset-a'
    ok,_=store.can_analyze('night',sig); assert ok
    result={'analysis_type':'night','provider':'gemini','period':{'start':'2026-08-24','end':'2026-08-24','days':1},'overall':{'title':'Teszt','summary':'Titkos válasz'}}
    saved=store.save_analysis('gemini','night',sig,result,payload,{'model':'gemini-3.6-flash','prompt_version':1})
    assert store.can_analyze('night',sig)[0] is False
    store.append_chat(saved['id'],'user','Mi történt?')
    store.append_chat(saved['id'],'assistant','Teszt válasz','gemini')
    hist=store.get_analysis(saved['id']); assert len(hist['messages'])==2
    hblob=(base/'private'/'ai_history.bin').read_bytes()
    assert b'Titkos' not in hblob and b'Mi tortent' not in hblob
    rows=store.list_history(); assert rows[0]['id']==saved['id'] and rows[0]['message_count']==2
    for _ in range(10): store.record_chat_question('gemini')
    assert store.can_chat('gemini')[0] is False

print('PASS: v1.9 live Gemini/Groq framework + safe payload + encrypted history/chat + limits + settings tabs')
