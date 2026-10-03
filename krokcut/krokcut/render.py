"""Rendu vidéo avec ffmpeg.

1. Chaque plan est rendu à part (choix du POV, zooms, PiP/écran partagé, son).
2. Les plans sont collés sans réencodage.
3. Une passe finale ajoute personnages, textes, bruitages, musique (avec ducking)
   et normalise le volume pour YouTube.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import RenderSettings
from .ffmpeg_utils import concat_listing, decoder_args, filter_script_args, probe, run_ffmpeg
from .timeline import Clip, Overlay, TextItem, Timeline

Progress = Callable[[float, str], None]


@dataclass
class Size:
    width: int
    height: int
    fps: float


def output_size(tl: Timeline, quality: str, settings: RenderSettings) -> Size:
    if quality == "preview":
        h = settings.preview_height
        w = int(round(h * tl.width / tl.height / 2) * 2)
        return Size(w, h, tl.fps)
    return Size(tl.width, tl.height, tl.fps)


def _num(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def video_codec_args(settings: RenderSettings, quality: str, intermediate: bool) -> list[str]:
    codec = settings.video_codec
    if quality == "preview":
        crf, preset = 23, "veryfast"
    else:
        crf = max(10, settings.crf - 4) if intermediate else settings.crf
        preset = "veryfast" if intermediate else settings.preset
    if "nvenc" in codec:
        return ["-c:v", codec, "-preset", "p5", "-rc", "vbr", "-cq", str(crf), "-b:v", "0"]
    if "videotoolbox" in codec:
        return ["-c:v", codec, "-q:v", str(max(40, 100 - crf * 2))]
    if codec in ("libx264", "libx265"):
        return ["-c:v", codec, "-preset", preset, "-crf", str(crf)]
    return ["-c:v", codec]


# ----------------------------------------------------------------- un plan
def zoom_filter(clip: Clip, size: Size) -> str:
    if not clip.zooms:
        return ""
    W, H = size.width, size.height
    terms, shake_x, shake_y = [], [], []
    for z in clip.zooms:
        t0, t1, s = _num(z.t0), _num(z.t1), _num(z.scale - 1)
        if z.kind == "slow":
            span = _num(max(0.01, z.t1 - z.t0))
            terms.append(f"{s}*between(t,{t0},{t1})*(t-{t0})/{span}")
        else:
            terms.append(f"{s}*between(t,{t0},{t1})")
        if z.kind == "shake":
            amp = _num(W * 0.012)
            shake_x.append(f"{amp}*sin(2*PI*t*13)*between(t,{t0},{t1})")
            shake_y.append(f"{amp}*cos(2*PI*t*11)*between(t,{t0},{t1})")
    zexpr = "1+" + "+".join(terms)
    x = f"(iw-{W})*{_num(clip.zooms[0].cx)}" + "".join("+" + s for s in shake_x)
    y = f"(ih-{H})*{_num(clip.zooms[0].cy)}" + "".join("+" + s for s in shake_y)
    return (
        f",scale=w='trunc({W}*({zexpr})/2)*2':h='trunc({H}*({zexpr})/2)*2':eval=frame:flags=bicubic"
        f",crop={W}:{H}:x='{x}':y='{y}'"
    )


def clip_command(clip: Clip, tl: Timeline, size: Size, out: Path, codec: list[str]) -> list[str]:
    W, H, fps = size.width, size.height, size.fps
    dur = clip.frames / fps
    srcs = tl.sources

    video_keys = ["A", "B"] if clip.pov == "both" else [clip.pov]
    pip_key = None
    if tl.layout == "pip" and clip.pov in ("A", "B"):
        other = "B" if clip.pov == "A" else "A"
        if srcs[other].covers(clip.src_in, clip.src_out):
            pip_key = other
    mode = tl.audio_mode
    if mode == "follow":
        audio_keys = video_keys
    elif mode == "mix":
        audio_keys = [k for k in ("A", "B") if srcs[k].covers(clip.src_in, clip.src_out)] or video_keys
    else:
        audio_keys = [mode] if srcs[mode].covers(clip.src_in, clip.src_out) else video_keys

    needed: list[str] = []
    for k in video_keys + ([pip_key] if pip_key else []) + audio_keys:
        if k not in needed:
            needed.append(k)

    args: list[str] = []
    index = {}
    for i, key in enumerate(needed):
        src = srcs[key]
        ss = max(0.0, src.to_source_time(clip.src_in))
        args += ["-ss", _num(ss), "-t", _num(dur * src.rate + 0.5), "-i", src.path]
        index[key] = i

    def fit(key: str) -> str:
        return (
            f"[{index[key]}:v]setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={_num(fps)}"
        )

    graph = []
    if clip.pov == "both":
        half = W // 2 // 2 * 2
        for side, key in (("l", "A"), ("r", "B")):
            graph.append(
                f"[{index[key]}:v]setpts=PTS-STARTPTS,scale={half}:{H}:force_original_aspect_ratio=increase,"
                f"crop={half}:{H},setsar=1,fps={_num(fps)}[{side}]"
            )
        graph.append(f"[l][r]hstack=inputs=2,pad={W}:{H}:(ow-iw)/2:0{zoom_filter(clip, size)}[base]")
    else:
        graph.append(fit(clip.pov) + zoom_filter(clip, size) + "[base]")
    last = "base"
    if pip_key:
        pw = int(W * 0.3) // 2 * 2
        m = int(W * 0.02)
        graph.append(
            f"[{index[pip_key]}:v]setpts=PTS-STARTPTS,scale={pw}:-2,setsar=1,fps={_num(fps)},"
            f"pad=iw+8:ih+8:4:4:white[pip]"
        )
        # En haut à droite : le bas de l'écran reste libre pour les personnages
        graph.append(f"[{last}][pip]overlay=W-w-{m}:{m}[withpip]")
        last = "withpip"
    vfx = "tpad=stop_mode=clone:stop_duration=2,format=yuv420p"
    if clip.fade_in:
        vfx += f",fade=t=in:st=0:d={_num(clip.fade_in)}"
    if clip.fade_out:
        vfx += f",fade=t=out:st={_num(dur - clip.fade_out)}:d={_num(clip.fade_out)}"
    graph.append(f"[{last}]{vfx}[v]")

    audio_labels = []
    for key in audio_keys:
        src = srcs[key]
        if not src.info.get("has_audio"):
            continue
        label = f"a{key}"
        graph.append(
            f"[{index[key]}:a:{src.audio_track if src.audio_track < int(src.info.get('audio_streams', 1)) else 0}]"
            f"asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[{label}]"
        )
        audio_labels.append(label)
    afx = f"apad,atrim=duration={_num(dur)}"
    if clip.fade_in:
        afx += f",afade=t=in:st=0:d={_num(clip.fade_in)}"
    if clip.fade_out:
        afx += f",afade=t=out:st={_num(dur - clip.fade_out)}:d={_num(clip.fade_out)}"
    if not audio_labels:
        args += ["-f", "lavfi", "-t", _num(dur), "-i", "anullsrc=r=48000:cl=stereo"]
        graph.append(f"[{len(needed)}:a]{afx}[a]")
    elif len(audio_labels) == 1:
        graph.append(f"[{audio_labels[0]}]{afx}[a]")
    else:
        joined = "".join(f"[{l}]" for l in audio_labels)
        graph.append(f"{joined}amix=inputs={len(audio_labels)}:normalize=0:duration=longest,{afx}[a]")

    return args + [
        "-filter_complex", ";".join(graph),
        "-map", "[v]", "-map", "[a]",
        "-frames:v", str(clip.frames),
        *codec,
        "-pix_fmt", "yuv420p", "-r", _num(fps), "-g", str(int(round(fps * 2))),
        "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
        str(out),
    ]


def _clip_key(clip: Clip, tl: Timeline, size: Size, codec: list[str]) -> str:
    srcs = {k: [s.path, s.offset, s.rate, s.audio_track] for k, s in tl.sources.items()}
    payload = json.dumps(
        [clip.model_dump(exclude={"id", "start_f", "segment", "moment_id"}), size.__dict__, tl.layout, tl.audio_mode, srcs, codec],
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def render_clips(tl: Timeline, work: Path, size: Size, settings: RenderSettings, quality: str, on_progress: Progress | None = None) -> Path:
    clips_dir = work / f"plans_{quality}"
    clips_dir.mkdir(parents=True, exist_ok=True)
    codec = video_codec_args(settings, quality, intermediate=True)
    jobs = []
    for clip in tl.clips:
        out = clips_dir / f"{_clip_key(clip, tl, size, codec)}.mkv"
        jobs.append((clip, out))
    todo = [(c, o) for c, o in jobs if not o.exists()]
    done = len(jobs) - len(todo)

    def work_one(job):
        clip, out = job
        tmp = out.with_name(out.stem + ".part.mkv")
        run_ffmpeg(clip_command(clip, tl, size, tmp, codec))
        tmp.replace(out)

    with ThreadPoolExecutor(max_workers=max(1, settings.workers)) as pool:
        for _ in pool.map(work_one, todo):
            done += 1
            if on_progress:
                on_progress(0.75 * done / max(1, len(jobs)), f"Plans rendus : {done}/{len(jobs)}")

    listing = clips_dir / "liste.txt"
    concat_listing([o for _, o in jobs], listing)
    main = work / f"assemblage_{quality}.mkv"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(main)])
    return main


# --------------------------------------------------------- passe finale
FONT_CANDIDATES = {
    "Windows": ["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    "Darwin": ["/System/Library/Fonts/Supplemental/Impact.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "Linux": [
        "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ],
}


def find_font(settings: RenderSettings) -> Path | None:
    if settings.font_file and Path(settings.font_file).exists():
        return Path(settings.font_file)
    for candidate in FONT_CANDIDATES.get(platform.system(), []):
        if Path(candidate).exists():
            return Path(candidate)
    return None


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
ANIMATED_EXT = {".gif", ".apng"}


def overlay_input(o: Overlay, fps: float) -> list[str]:
    ext = Path(o.path).suffix.lower()
    if ext in IMAGE_EXT:
        return ["-loop", "1", "-framerate", _num(fps), "-t", _num(o.duration), "-i", o.path]
    if ext in ANIMATED_EXT:
        return ["-ignore_loop", "0", "-t", _num(o.duration), "-i", o.path]
    return decoder_args(probe(o.path)) + ["-t", _num(o.duration), "-i", o.path]


def overlay_xy(o: Overlay, W: int, H: int) -> tuple[str, str]:
    m = int(W * 0.03)
    standing = o.kind == "character"  # un perso « posé » en bas de l'écran
    bottom = "H-h" if standing else f"H-h-{m}"
    return {
        "bottom_left": (str(m), bottom),
        "bottom_right": (f"W-w-{m}", bottom),
        "top_left": (str(m), str(m)),
        "top_right": (f"W-w-{m}", str(m)),
        "left": (str(m), "(H-h)/2"),
        "right": (f"W-w-{m}", "(H-h)/2"),
        "center": ("(W-w)/2", "(H-h)/2"),
    }.get(o.position, (f"W-w-{m}", bottom))


def text_filter(t: TextItem, k: int, W: int, H: int, font: str | None) -> str:
    text = t.text.upper() if t.style in ("impact", "meme") else t.text
    base = {"impact": 0.11, "caption": 0.06, "meme": 0.08}[t.style]
    fs = int(min(H * base, W * 0.9 / max(1, 0.58 * len(text))))
    y = {"impact": "(h-text_h)/2", "caption": "h*0.80", "meme": "h*0.06"}[t.style]
    color = {"impact": "0xFFE600", "caption": "white", "meme": "white"}[t.style]
    font_arg = "fontfile=font.ttf:" if font else ""
    return (
        f"drawtext={font_arg}textfile=texte_{k:03d}.txt:fontsize={fs}:fontcolor={color}:"
        f"borderw={max(2, fs // 12)}:bordercolor=black:shadowx=3:shadowy=3:shadowcolor=black@0.6:"
        f"x=(w-text_w)/2:y={y}:enable='between(t,{_num(t.start)},{_num(t.start + t.duration)})'"
    )


def compose(
    tl: Timeline,
    main: Path,
    out: Path,
    work: Path,
    size: Size,
    settings: RenderSettings,
    quality: str,
    on_progress: Progress | None = None,
    sfx_volume_db: float = -6.0,
    voice_polish: bool = True,
    denoise: bool = False,
) -> Path:
    W, H, fps = size.width, size.height, size.fps
    duration = tl.duration
    compose_dir = work / f"composition_{quality}"
    if compose_dir.exists():
        shutil.rmtree(compose_dir)
    compose_dir.mkdir(parents=True)

    font = find_font(settings)
    if font and tl.texts:
        shutil.copy(font, compose_dir / "font.ttf")

    args: list[str] = ["-i", str(main.resolve())]
    n_inputs = 1
    graph: list[str] = []
    v = "0:v"
    audio_parts: list[str] = []

    for k, o in enumerate(o for o in tl.overlays if o.start < duration):
        args += overlay_input(o, fps)
        idx = n_inputs
        n_inputs += 1
        d = min(o.duration, duration - o.start)
        chain = f"[{idx}:v]setpts=PTS-STARTPTS"
        if o.key == "green":
            chain += ",colorkey=0x00FF00:0.30:0.08"
        if o.position == "center" and o.kind == "video":
            chain += f",scale={W}:{H}:force_original_aspect_ratio=decrease"
        else:
            chain += f",scale=-2:{int(H * o.scale) // 2 * 2}"
            if o.key == "none":
                chain += ",pad=iw+12:ih+12:6:6:white"
        chain += (
            f",format=yuva420p,fade=t=in:st=0:d=0.12:alpha=1,"
            f"fade=t=out:st={_num(max(0.0, d - 0.15))}:d=0.15:alpha=1,"
            f"setpts=PTS+{_num(o.start)}/TB[ov{k}]"
        )
        graph.append(chain)
        x, y = overlay_xy(o, W, H)
        graph.append(
            f"[{v}][ov{k}]overlay=x={x}:y={y}:eof_action=pass:"
            f"enable='between(t,{_num(o.start)},{_num(o.start + d)})'[vo{k}]"
        )
        v = f"vo{k}"
        if o.with_audio:
            graph.append(
                f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"volume={_num(sfx_volume_db)}dB,adelay={int(o.start * 1000)}:all=1[oa{k}]"
            )
            audio_parts.append(f"oa{k}")

    for k, t in enumerate(tl.texts):
        (compose_dir / f"texte_{k:03d}.txt").write_text(t.text.upper() if t.style != "caption" else t.text, "utf-8")
        graph.append(f"[{v}]{text_filter(t, k, W, H, str(font) if font else None)}[vt{k}]")
        v = f"vt{k}"
    graph.append(f"[{v}]format=yuv420p[vout]")

    for k, s in enumerate(x for x in tl.sfx if x.start < duration):
        args += ["-i", s.path]
        graph.append(
            f"[{n_inputs}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={_num(s.volume_db)}dB,adelay={int(s.start * 1000)}:all=1[sfx{k}]"
        )
        audio_parts.append(f"sfx{k}")
        n_inputs += 1

    music_labels = []
    for k, m in enumerate(tl.music):
        length = min(m.end, duration) - m.start
        if length <= 1:
            continue
        args += ["-stream_loop", "-1", "-t", _num(length), "-i", m.path]
        fade_out = min(2.0, length / 4)
        graph.append(
            f"[{n_inputs}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=duration={_num(length)},afade=t=in:d={_num(min(1.5, length / 4))},"
            f"afade=t=out:st={_num(length - fade_out)}:d={_num(fade_out)},volume={_num(m.volume_db)}dB,"
            f"adelay={int(m.start * 1000)}:all=1[mus{k}]"
        )
        music_labels.append(f"mus{k}")
        n_inputs += 1

    voice = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    if denoise:
        voice += ",afftdn=nf=-25"
    if voice_polish:
        # coupe les grondements et resserre la dynamique : des voix plus présentes et régulières
        voice += ",highpass=f=70,acompressor=threshold=0.089:ratio=3:attack=10:release=250:makeup=2"
    graph.append(f"[0:a]{voice}[dlg0]")
    if music_labels:
        graph.append("[dlg0]asplit=2[dlg][sc]")
        joined = "".join(f"[{l}]" for l in music_labels)
        if len(music_labels) > 1:
            graph.append(f"{joined}amix=inputs={len(music_labels)}:normalize=0[musall]")
        else:
            graph.append(f"{joined}anull[musall]")
        # La musique baisse automatiquement quand quelqu'un parle
        graph.append("[musall][sc]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=400[mduck]")
        audio_parts.append("mduck")
        dialogue = "dlg"
    else:
        dialogue = "dlg0"
    if audio_parts:
        joined = f"[{dialogue}]" + "".join(f"[{l}]" for l in audio_parts)
        graph.append(f"{joined}amix=inputs={len(audio_parts) + 1}:normalize=0:duration=first:dropout_transition=0[mixed]")
        dialogue = "mixed"
    graph.append(
        f"[{dialogue}]loudnorm=I={_num(settings.loudness_lufs)}:TP=-1.5:LRA=11,aresample=48000,"
        f"atrim=duration={_num(duration)}[aout]"
    )

    script = compose_dir / "filtres.txt"
    script.write_text(";\n".join(graph), "utf-8")
    tmp = out.with_name(out.stem + ".part" + out.suffix)
    run_ffmpeg(
        args
        + filter_script_args(script.resolve())
        + ["-map", "[vout]", "-map", "[aout]"]
        + video_codec_args(settings, quality, intermediate=False)
        + ["-pix_fmt", "yuv420p", "-r", _num(fps), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp.resolve())],
        duration=duration,
        on_progress=(lambda p: on_progress(0.75 + 0.25 * p, "Effets, sons et musique")) if on_progress else None,
        cwd=compose_dir,
    )
    tmp.replace(out)
    return out


def render(
    tl: Timeline,
    work: Path,
    out: Path,
    settings: RenderSettings,
    quality: str = "preview",
    on_progress: Progress | None = None,
    sfx_volume_db: float = -6.0,
    voice_polish: bool = True,
    denoise: bool = False,
) -> Path:
    if not tl.clips:
        raise ValueError("La timeline est vide : rien à rendre.")
    size = output_size(tl, quality, settings)
    main = render_clips(tl, work, size, settings, quality, on_progress)
    return compose(tl, main, out, work, size, settings, quality, on_progress, sfx_volume_db, voice_polish, denoise)
