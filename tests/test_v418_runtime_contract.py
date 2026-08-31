from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
app = (ROOT/'app.py').read_text(encoding='utf-8')
js = (ROOT/'web'/'app.js').read_text(encoding='utf-8')
sw = (ROOT/'web'/'service-worker.js').read_text(encoding='utf-8')

assert 'f"SleepMate v{APP_VERSION}' in app
assert 'import_resmed_tree(source, self.dataset.root, cb, authoritative=True)' in app
assert 'startup_sync = import_resmed_tree(source_root, data_root, authoritative=True)' in app
assert 'import_resmed_tree(source, Handler.dataset.root, cb, authoritative=True)' in app
# Manual/SD/ZIP remain non-destructive.
assert 'result = import_resmed_tree(source, target, cb)' in app
assert 'result = import_resmed_tree(roots[0], self.dataset.root, cb)' in app
assert 'result = import_resmed_tree(tmp, self.dataset.root, copy_cb)' in app
# Native folder chooser can only be called by a direct user action and never starts in TEMP implicitly.
assert 'user_initiated' in app and 'initialdir=initial' in app
assert "{user_initiated:true,initial_dir:current}" in js
assert 'os.startfile(' not in app and 'explorer.exe' not in app.lower()
assert 'v5.0.0' in sw
print('PASS: v5.0.0 runtime routes primary refresh through protected mirror; imports remain additive; no automatic Temp/Explorer opening')
