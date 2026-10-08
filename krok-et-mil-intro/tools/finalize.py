"""Rogne le logo PNG et vérifie les livrables de out/ (durées, formats, sonie, drop)."""
import json, os, subprocess
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'out')
TL = json.load(open(os.path.join(ROOT, 'timeline.json')))


def trim_logo():
    im = Image.open(os.path.join(ROOT, 'build', 'logo_raw.png')).convert('RGBA')
    a = np.array(im)[..., 3]
    ys, xs = np.where(a > 0)
    pad = 40
    box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad))
    im.crop(box).save(os.path.join(OUT, 'logo_krok_et_mil.png'), optimize=True)
    return im.crop(box).size


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name,width,height,r_frame_rate,sample_rate,channels,duration',
                        '-show_entries', 'format=duration', '-of', 'json', path], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def loudness(path):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
    lines = r.stderr.splitlines()
    out = {}
    for i, l in enumerate(lines):
        if l.strip().startswith('I:'):
            out['lufs'] = float(l.split()[1])
        if l.strip().startswith('Peak:'):
            out['true_peak_dbtp'] = float(l.split()[1])
    return out


def main():
    report = {'logo_px': trim_logo()}
    for name in ('intro_10s.mp4', 'intro_3s.mp4', 'stinger.wav'):
        p = os.path.join(OUT, name)
        info = probe(p)
        streams = [{k: v for k, v in s.items()} for s in info['streams']]
        report[name] = {'duration_s': round(float(info['format']['duration']), 3), 'streams': streams, **loudness(p)}
    beat = 60 / TL['bpm']
    report['drop_s'] = TL['sections']['u4'] * beat
    print(json.dumps(report, indent=1, ensure_ascii=False))
    with open(os.path.join(OUT, 'rapport_rendu.json'), 'w') as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    d = report['intro_10s.mp4']['duration_s']
    assert d <= 10.0 + 1e-3, f'durée {d} > 10 s'
    assert abs(report['drop_s'] - 7.5) < 1e-9


if __name__ == '__main__':
    main()
