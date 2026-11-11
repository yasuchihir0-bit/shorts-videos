#!/usr/bin/env python3
"""台本JSON → 縦型ショート動画（1080x1920, 30fps, VOICEVOX:青山龍星 ナレーション）
準備: sh tools/setup_voice.sh
使い方: python3 render.py script.json out.mp4
読み確認: python3 render.py --kana script.json
サムネイル: python3 render.py --thumb script.json out.jpg（script.json の "thumb"）
script.json: {"scenes":[{"tag":"","head":"","body":["",""],"say":""}, ...]}
  tag  … 上の小ラベル（例「1つめ」）。空なら「中学受験｜保護者のための実践ガイド」
  head … 大見出し（\\n で改行可）
  body … 補足の行（0〜3行）
  say  … 読み上げ文（読み間違えやすい語はひらがなで）
"""
import json, os, subprocess, sys, wave
import io
import numpy as np, pyopenjtalk
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
LABEL = "中学受験｜保護者のための実践ガイド"
ENC = ["-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS)]

VV = "/home/claude/voicevox"
SPEAKER = 13  # 青山龍星 ノーマル（説明欄に「VOICEVOX:青山龍星」のクレジットが必要）
_syn = None
def synth():
    global _syn
    if _syn is None:
        from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
        ort = Onnxruntime.load_once(filename=f"{VV}/ort/lib/libvoicevox_onnxruntime.so.1.23.2")
        _syn = Synthesizer(ort, OpenJtalk(pyopenjtalk.OPEN_JTALK_DICT_DIR.decode()))
        with VoiceModelFile.open(f"{VV}/vvm/vvms/15.vvm") as m: _syn.load_voice_model(m)
    return _syn

def query(text):
    q = synth().create_audio_query(text, SPEAKER)
    q.speed_scale = 1.08; q.pre_phoneme_length = 0.15; q.post_phoneme_length = 0.35
    return q

def tts(text):
    with wave.open(io.BytesIO(synth().synthesis(query(text), SPEAKER))) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64)
    return x, sr

def kana(text):
    return "/".join("".join(m.text for m in ap.moras) for ap in query(text).accent_phrases)

def font(p, s): return ImageFont.truetype(p, s, index=0)

def wrap(d, text, f, maxw):
    out = []
    for part in text.split("\n"):
        line = ""
        for ch in part:
            if d.textlength(line + ch, font=f) > maxw and line and ch not in "。、」）！？ー":
                out.append(line); line = ch
            else: line += ch
        out.append(line)
    return out

def draw(sc, i, n):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):  # クリーム色グラデーション
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(255 - 2*t), int(247 - 12*t), int(232 - 21*t)))
    d.ellipse([780, -160, 1300, 360], fill=(250, 222, 190))
    d.ellipse([-200, 1600, 260, 2060], fill=(226, 230, 232))
    x0, y0, cw, ch = 70, 300, W - 140, 1240
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], 40, fill="white")
    d.rectangle([x0, y0 + 60, x0 + 12, y0 + ch - 60], fill=(232, 130, 60))
    tag = sc.get("tag") or LABEL
    f = font(FB, 40); tw = d.textlength(tag, font=f)
    d.rounded_rectangle([x0 + 60, y0 + 70, x0 + 108 + tw, y0 + 146], 38, fill=(47, 93, 140))
    d.text((x0 + 84, y0 + 108), tag, font=f, fill="white", anchor="lm")
    maxw = cw - 190  # 右端はショートのボタンにかかるので空ける
    size = 100  # 見出しは \n の位置だけで改行されるまで縮める
    while True:
        fh = font(FB, size); hl = wrap(d, sc["head"], fh, maxw)
        if len(hl) == len(sc["head"].split("\n")) or size <= 60: break
        size -= 4
    bs = 54  # 箇条書きも1行に収まるまで縮める
    while True:
        fb = font(FM, bs); bl = [wrap(d, b, fb, maxw - 40) for b in sc.get("body", [])]
        if all(len(x) == 1 for x in bl) or bs <= 42: break
        bs -= 2
    hh = len(hl) * int(size * 1.35) + (50 + sum(len(x) * int(bs * 1.45) + 22 for x in bl) if bl else 0)
    top, bottom = y0 + 180, y0 + ch - 60
    if hh > bottom - top: raise SystemExit(f"scene {i+1}: 文字があふれています")
    y = top + (bottom - top - hh) // 2
    for l in hl:
        d.text((x0 + 60, y), l, font=fh, fill=(31, 42, 55)); y += int(size * 1.35)
    y += 50
    for lines in bl:
        for k, l in enumerate(lines):
            if k == 0: d.ellipse([x0 + 62, y + 26, x0 + 82, y + 46], fill=(232, 130, 60))
            d.text((x0 + 104, y), l, font=fb, fill=(55, 65, 81)); y += int(bs * 1.45)
        y += 22
    # 進行ドット
    for k in range(n):
        cx = W // 2 + (k - (n - 1) / 2) * 44
        d.ellipse([cx - 10, 1640, cx + 10, 1660], fill=(232, 130, 60) if k == i else (210, 200, 190))
    return im

def thumbnail(th, out):
    """縦型サムネイル 1080x1920。th = {"top": 小見出し, "main": 大見出し(\\n可), "sub": オレンジの補足}"""
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(255 - 2*t), int(247 - 12*t), int(232 - 21*t)))
    d.ellipse([700, -250, 1350, 400], fill=(250, 214, 175))
    d.ellipse([-260, 1500, 330, 2090], fill=(222, 228, 234))
    x0, y0, cw, ch = 60, 330, W - 120, 1180
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], 44, fill="white")
    d.rectangle([x0, y0 + 70, x0 + 16, y0 + ch - 70], fill=(232, 130, 60))
    f = font(FB, 46); tag = th.get("top") or "中学受験｜保護者のための実践ガイド"; tw = d.textlength(tag, font=f)
    d.rounded_rectangle([x0 + 70, y0 + 80, x0 + 130 + tw, y0 + 168], 44, fill=(47, 93, 140))
    d.text((x0 + 100, y0 + 124), tag, font=f, fill="white", anchor="lm")
    maxw = cw - 150
    size = 150
    while True:
        fh = font(FB, size); hl = wrap(d, th["main"], fh, maxw)
        if len(hl) == len(th["main"].split("\n")) or size <= 80: break
        size -= 6
    fs = font(FB, 64); sl = wrap(d, th.get("sub", ""), fs, maxw) if th.get("sub") else []
    hh = len(hl) * int(size * 1.25) + (40 + len(sl) * 88 if sl else 0)
    y = y0 + 220 + (ch - 300 - hh) // 2
    for l in hl:
        d.text((x0 + 70, y), l, font=fh, fill=(31, 42, 55)); y += int(size * 1.25)
    y += 40
    for l in sl:
        d.text((x0 + 70, y), l, font=fs, fill=(232, 130, 60)); y += 88
    if y > y0 + ch - 30: raise SystemExit("サムネイル: 文字があふれています")
    im.save(out, quality=92)

def main(src, out):
    scenes = json.load(open(src, encoding="utf-8"))["scenes"]
    tmp = os.path.splitext(out)[0] + "_parts"; os.makedirs(tmp, exist_ok=True)
    audio, files = [], []
    for i, sc in enumerate(scenes):
        x, sr = tts(sc["say"])
        audio.append(x); dur = len(x) / sr
        png = f"{tmp}/s{i}.png"; draw(sc, i, len(scenes)).save(png)
        part, t = f"{tmp}/s{i}.mp4", f"{tmp}/s{i}.tmp.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", png, "-vf",
                        f"format=yuv420p,loop=-1:1,trim=duration={dur:.3f},fade=in:st=0:d=0.25", *ENC, t], check=True)
        os.replace(t, part); files.append(part)
    a = np.concatenate(audio); a = (a / max(1, np.abs(a).max()) * 0.9 * 32767).astype(np.int16)
    with wave.open(f"{tmp}/a.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(a.tobytes())
    with open(f"{tmp}/list.txt", "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in files)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt",
                    "-i", f"{tmp}/a.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
                    "-shortest", out + ".tmp.mp4"], check=True)
    os.replace(out + ".tmp.mp4", out)
    print(f"{out}: {len(a)/sr:.1f}秒, {os.path.getsize(out)/1e6:.2f}MB")

if __name__ == "__main__":
    if sys.argv[1] == "--thumb":  # python3 render.py --thumb script.json out.jpg
        thumbnail(json.load(open(sys.argv[2], encoding="utf-8"))["thumb"], sys.argv[3])
    elif sys.argv[1] == "--kana":
        for i, sc in enumerate(json.load(open(sys.argv[2], encoding="utf-8"))["scenes"]):
            print(i + 1, kana(sc["say"]))
    else:
        main(sys.argv[1], sys.argv[2])
