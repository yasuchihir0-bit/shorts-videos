#!/usr/bin/env python3
"""台本JSON → 縦型ショート動画（1080x1920, 30fps, Open JTalk ナレーション）
使い方: python3 render.py script.json out.mp4
script.json: {"scenes":[{"tag":"","head":"","body":["",""],"say":""}, ...]}
  tag  … 上の小ラベル（例「1つめ」）。空なら「中学受験｜保護者のための実践ガイド」
  head … 大見出し（\\n で改行可）
  body … 補足の行（0〜3行）
  say  … 読み上げ文（読み間違えやすい語はひらがなで）
"""
import json, os, subprocess, sys, wave
import numpy as np, pyopenjtalk
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FM = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
LABEL = "中学受験｜保護者のための実践ガイド"
ENC = ["-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS)]

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
    # 上部の常設帯：元記事への誘導
    ft = font(FB, 44); msg = "全文はnote「応援隊」で公開中"; mw = d.textlength(msg, font=ft)
    d.rounded_rectangle([(W - mw) / 2 - 40, 170, (W + mw) / 2 + 40, 254], 42, fill=(232, 130, 60))
    d.text((W / 2, 212), msg, font=ft, fill="white", anchor="mm")
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

def main(src, out):
    scenes = json.load(open(src, encoding="utf-8"))["scenes"]
    tmp = os.path.splitext(out)[0] + "_parts"; os.makedirs(tmp, exist_ok=True)
    audio, files = [], []
    for i, sc in enumerate(scenes):
        x, sr = pyopenjtalk.tts(sc["say"], speed=1.12)
        x = np.concatenate([np.zeros(int(sr * 0.25)), x, np.zeros(int(sr * 0.45))])
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
    main(sys.argv[1], sys.argv[2])
