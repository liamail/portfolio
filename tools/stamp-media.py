#!/usr/bin/env python3
"""Stamp every media file with a short fingerprint of its contents.

The page asks for media/<name>.mp4?v=<fingerprint>, so whenever a file changes its address changes
too and browsers fetch the new one instead of a cached copy. Unchanged files keep their address and
stay cached. Run this after adding or changing anything in media/ (alongside tools/check-media.py):

    python3 tools/stamp-media.py [index.html]
"""
import hashlib, json, os, re, sys
page = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
root = os.path.dirname(os.path.abspath(page))
media = os.path.join(root, 'media')
stamps = {}
for name in sorted(os.listdir(media)):
    stem, ext = os.path.splitext(name)
    if ext not in ('.mp4', '.jpg'): continue
    h = stamps.setdefault(stem, hashlib.sha1())
    with open(os.path.join(media, name), 'rb') as f: h.update(f.read())
mv = {k: v.hexdigest()[:8] for k, v in sorted(stamps.items())}
line = 'const MV = ' + json.dumps(mv, separators=(',', ':')) + ';  // media fingerprints, written by tools/stamp-media.py'
s = open(page).read()
s2, n = re.subn(r'^const MV = .*$', line, s, count=1, flags=re.M)
if not n: sys.exit('No "const MV = ..." line found in ' + page)
if s2 != s: open(page, 'w').write(s2)
print(len(mv), 'media stamped' + ('' if s2 != s else ' (no changes)'))
