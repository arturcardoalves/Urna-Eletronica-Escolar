from pathlib import Path
from build_assets import web_assets


def test_frozen_server_keeps_resources_and_excludes_legacy_uploads(tmp_path):
    app=tmp_path/'app'
    names=['templates/urna.html','static/js/urna.js','static/sounds/fim.mp3',
           'static/fonts/OFL.txt','static/uploads/slates/previous-election.png',
           'static/private.key','static/election.db','static/history.uepkg','static/debug.log']
    for name in names:
        path=app/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'test')
    collected=web_assets(app)
    assert {Path(src).relative_to(app).as_posix() for src,_ in collected}==set(names[:4])
    assert all(dest.startswith('app/') for _,dest in collected)
    assert (app/names[4]).exists()  # Packaging never deletes the original data.
