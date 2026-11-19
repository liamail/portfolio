#!/usr/bin/env python3
"""Check every visual the site uses before it ships.

Run from the site folder:  python3 tools/check-media.py [index.html]

Flags, for each media src in the page:
  - a missing file;
  - declared w/h that don't match the file's proportions (would leave a gap or crop);
  - a hairline (1 to 3px) along any edge, in the still and in four frames of the video:
    screen recordings and exports often carry one. Crop it out of the file (and its
    still) and scale back to the original size;
  - a flat strip thicker than that along any edge.

Edges that are real content (a board's own padding, the area under a phone's home
indicator) are listed in REVIEWED with the reason, once checked by eye, so they stop
being reported. Everything else gets fixed in the file, not hidden with CSS.
"""
import io, os, re, subprocess, sys
import numpy as np
from PIL import Image

REVIEWED = {    # src: reason the edge band is real content
    'ai-mobile': 'phone UI below the home indicator',
    'beat-sync': 'phone UI below the home indicator',
    'mobile-ia': 'phone UI below the home indicator',
    'mobile-overlay': 'phone UI below the home indicator',
    'mobile-rearrange': 'phone UI below the home indicator; thumbnail strip at the left edge',
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
    'fig-optin-setting': 'white page margin on the right',
    'cv-highlights': 'white editor header in some frames',
    'bs-zoom': 'light timeline area along the top',
}

def frames(path):
    if path.endswith('.jpg'):
        yield np.asarray(Image.open(path).convert('RGB')).astype(float)
        return
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                              '-of', 'csv=p=0', path], capture_output=True, text=True).stdout or 1)
    for t in (0.0, d * 0.33, d * 0.66, max(0, d - 0.2)):
        out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', path, '-frames:v', '1',
                              '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
        if out:
            yield np.asarray(Image.open(io.BytesIO(out)).convert('RGB')).astype(float)

def hairline(a, side):
    """Edge lines (up to 3px) that differ from what sits just inside them."""
    get = {'top': lambda i: a[i], 'bottom': lambda i: a[-1 - i],
           'left': lambda i: a[:, i], 'right': lambda i: a[:, -1 - i]}[side]
    def m(i):
        line = get(i); n = len(line)
        return line[int(n * .1):int(n * .9)].mean(0)
    ref = np.mean([m(i) for i in range(5, 9)], axis=0)
    k = 0
    while k < 4 and np.abs(m(k) - ref).max() > 14:
        k += 1
    return k if k <= 3 else 0   # 4 or more is a band of real content, judged by band()

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
        hair, strip = {}, {}
        for path in ([still] if img else [still, video]):
            for a in frames(path):
                for side in ('top', 'bottom', 'left', 'right'):
                    h = hairline(a, side)
                    if h:
                        hair[side] = max(hair.get(side, 0), h)
                    n = band(a, side)
                    if n > 3:
                        strip[side] = max(strip.get(side, 0), n)
        if hair:
            print(f'HAIRLINE {src}: ' + ', '.join(f'{s} {n}px' for s, n in hair.items())); issues += 1
        if strip:
            print(f'STRIP    {src}: ' + ', '.join(f'{s} {n}px' for s, n in strip.items())); issues += 1
    print(f'{len(seen)} visuals checked, {issues} to fix' if issues else f'{len(seen)} visuals checked, all clean')
    sys.exit(1 if issues else 0)

main()
