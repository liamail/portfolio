#!/usr/bin/env python3
"""Check every visual the site uses before it ships.

Run from the site folder:  python3 tools/check-media.py [index.html]

Flags, for each media src in the page:
  - a missing file;
  - declared w/h that don't match the file's proportions (would leave a gap or crop);
  - a flat strip along any edge thicker than the frame's built-in trim (about 3px),
    in the still and in three frames of the video. Hairlines up to 3px are trimmed
    automatically by the .device overscale in the CSS, so they are not reported.

Strips that are real content (a board's own padding, the area under a phone's home
indicator) are listed in REVIEWED with the reason, so they stop being reported.
"""
import io, os, re, subprocess, sys
import numpy as np
from PIL import Image

TRIM = 3        # px the CSS overscale already hides on each edge
REVIEWED = {    # src: reason the edge band is real content
    'ai-mobile': 'phone UI below the home indicator',
    'beat-sync': 'phone UI below the home indicator',
    'mobile-ia': 'phone UI below the home indicator',
    'mobile-overlay': 'phone UI below the home indicator',
    'mobile-rearrange': 'phone UI below the home indicator',
    'timeline-mobile': 'phone UI below the home indicator',
    'timeline-resize': 'phone UI below the home indicator',
    'tl-overview': 'phone UI below the home indicator',
    'tl-switch-mobile': 'phone UI below the home indicator',
    'tl-existing-mobile': 'phone UI below the home indicator',
    'transcript-captions': 'phone UI below the home indicator',
    'transcript-flow': 'phone UI below the home indicator',
    'audio-adjust': 'editor bottom bar',
    'cv-beatsync': 'white editor UI along the bottom (left strip cropped Nov 2026)',
    'cv-dragdrop': 'white editor UI along the bottom',
    'fig-bs-notch': 'white board area on the right',
    'fig-muteall-board': 'black board padding',
}

def frames(path):
    if path.endswith('.jpg'):
        yield np.asarray(Image.open(path).convert('RGB')).astype(float)
        return
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                              '-of', 'csv=p=0', path], capture_output=True, text=True).stdout or 1)
    for t in (0.0, d * 0.5, max(0, d - 0.2)):
        out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', path, '-frames:v', '1',
                              '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
        if out:
            yield np.asarray(Image.open(io.BytesIO(out)).convert('RGB')).astype(float)

def band(a, side):
    n_max = min(60, a.shape[0] if side in ('top', 'bottom') else a.shape[1])
    get = {'top': lambda i: a[i], 'bottom': lambda i: a[-1 - i],
           'left': lambda i: a[:, i], 'right': lambda i: a[:, -1 - i]}[side]
    first = get(0); m0 = first.mean(0)
    if first.std(0).max() > 10:
        return 0
    n = 0
    while n < n_max:
        line = get(n)
        if line.std(0).max() > 10 or np.abs(line.mean(0) - m0).max() > 14:
            break
        n += 1
    if n >= n_max or np.abs(get(n).mean(0) - m0).max() < 18:
        return 0
    return n

def main():
    page = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    root = os.path.dirname(os.path.abspath(page))
    html = open(page).read()
    issues = 0
    seen = set()
    for m in re.finditer(r'src: "([^"]+)",( img: true,)? w: (\d+), h: (\d+)', html):
        src, img, w, h = m.group(1), bool(m.group(2)), int(m.group(3)), int(m.group(4))
        if src in seen:
            continue
        seen.add(src)
        still = os.path.join(root, 'media', src + '.jpg')
        video = os.path.join(root, 'media', src + '.mp4')
        if not os.path.exists(still) or (not img and not os.path.exists(video)):
            print(f'MISSING  {src}'); issues += 1; continue
        W, H = Image.open(still).size
        if abs(w / h - W / H) / (W / H) > 0.004:
            print(f'SIZE     {src}: declared {w}x{h}, file {W}x{H}'); issues += 1
        if src in REVIEWED:
            continue
        found = {}
        for path in ([still] if img else [still, video]):
            for a in frames(path):
                for side in ('top', 'bottom', 'left', 'right'):
                    n = band(a, side)
                    if n > TRIM:
                        found[side] = max(found.get(side, 0), n)
        if found:
            print(f'STRIP    {src}: ' + ', '.join(f'{s} {n}px' for s, n in found.items()))
            issues += 1
    print(f'{len(seen)} visuals checked, {issues} to fix' if issues else f'{len(seen)} visuals checked, all clean')
    sys.exit(1 if issues else 0)

main()
