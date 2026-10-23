"""Builds backend/app/static/shop/mascot_talk2.html: cartoon-style talking mascot previews
(frames with different mouths + blink, driven by the voice level). Preview only; one self-contained file.

Frames come from /tmp-style generated PNGs (tk_closed/mid/wide/round/blink.png) in the folder given by
FRAMES_DIR; they are cropped, resized and saved next to the other mascot images as talk_*.jpg."""
import base64
import io
import os
import sys

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
M = os.path.join(ROOT, "backend", "app", "static", "shop", "mascot")
OUT = os.path.join(ROOT, "backend", "app", "static", "shop", "mascot_talk2.html")
FRAMES_DIR = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\User\AppData\Local\Temp\claude\rename\talk"
NAMES = ["closed", "mid", "wide", "round", "blink"]


def frame(name: str) -> str:
    im = Image.open(os.path.join(FRAMES_DIR, f"tk_{name}.png")).convert("RGB").crop((120, 80, 1010, 970)).resize((380, 380), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    with open(os.path.join(M, f"talk_{name}.jpg"), "wb") as f:
        f.write(buf.getvalue())
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def audio(lang: str) -> str:
    with open(os.path.join(M, f"hello_{lang}.mp3"), "rb") as f:
        return "data:audio/mpeg;base64," + base64.b64encode(f.read()).decode()


HTML = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bonchbrik говорит: мультяшная анимация</title>
<link href="https://fonts.googleapis.com/css2?family=Handjet:wght@600;700;800&display=swap" rel="stylesheet">
<style>
  :root { --mustard:#FCC904; --ink:#141414; --f:"Handjet",system-ui,sans-serif; }
  * { box-sizing: border-box; border-radius: 0; }
  body { margin:0; background:#2a2a2a; color:#fff; font-family:var(--f); font-weight:600; font-size:21px; }
  h1 { font-size:32px; font-weight:800; text-align:center; margin:22px 12px 2px; color:var(--mustard); }
  .hint { text-align:center; margin:0 12px 14px; color:#ddd; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:30px; max-width:1100px; margin:0 auto; padding:8px 16px 30px; justify-items:center; }
  .cell { width:300px; }
  .tag { display:flex; gap:10px; align-items:baseline; font-size:26px; font-weight:800; margin-bottom:2px; }
  .tag b { background:var(--mustard); color:var(--ink); padding:0 9px; }
  .dsc { color:#ccc; font-size:20px; line-height:1.15; min-height:92px; margin-bottom:10px; }
  .scr { position:relative; width:300px; height:420px; background:var(--mustard); display:grid; place-items:center; overflow:hidden; box-shadow:0 0 0 4px #000, 0 0 0 8px #555; }
  .dlg { position:relative; width:252px; background:#fff; color:var(--ink); padding:96px 12px 14px; text-align:center; margin-top:56px;
    box-shadow:0 -3px 0 0 #000,0 3px 0 0 #000,-3px 0 0 0 #000,3px 0 0 0 #000,7px 7px 0 0 #fff8; }
  .dlg h3 { margin:0 0 4px; font-size:31px; font-weight:800; line-height:1; }
  .dlg .line { height:56px; font-size:25px; line-height:1.05; color:#4A4023; font-weight:700; }
  .bust { position:absolute; left:50%; top:-76px; margin-left:-76px; width:152px; height:152px; background:var(--mustard); transform-origin:50% 100%;
    box-shadow:0 -3px 0 0 #000,0 3px 0 0 #000,-3px 0 0 0 #000,3px 0 0 0 #000,6px 6px 0 0 #0004; overflow:hidden; }
  .bust img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block; opacity:0; }
  .bust img.on { opacity:1; }
  .btns { display:flex; gap:8px; margin-top:6px; }
  .go { border:0; background:var(--mustard); font-family:var(--f); font-weight:800; font-size:24px; padding:3px 14px; color:#141414; cursor:pointer;
    box-shadow:0 -3px 0 0 #000,0 3px 0 0 #000,-3px 0 0 0 #000,3px 0 0 0 #000,3px 6px 0 0 #000; margin:3px; }
</style></head><body>
<h1>BONCHBRIK ГОВОРИТ</h1>
<p class="hint">Нажмите «Говорит RU» или «Говорит UZ»: у маскота двигается рот, он моргает. Это только макеты, приложение не менялось.</p>
<div class="grid" id="grid"></div>
<script>
(function () {
  var F = { closed: "__CLOSED__", mid: "__MID__", wide: "__WIDE__", round: "__ROUND__", blink: "__BLINK__" };
  var AUD = { ru: "__RU__", uz: "__UZ__" };
  var WORDS = { ru: [[0, "Привет!"], [0.5, "Я Бончбрик!"], [1.55, "Что тебе"], [2.2, "приготовить?"]], uz: [[0, "Salom!"], [0.5, "Men Bonchbrik!"], [1.5, "Nima tayyorlab"], [2.4, "beray?"]] };
  var VARS = [
    { k: "A", t: "Мультяшный рот", d: "Четыре формы рта (закрыт, чуть открыт, широко, круглое «о») меняются в такт голосу, плюс моргание. Классика мультиков." },
    { k: "B", t: "Рот + пружина", d: "То же самое, плюс голова пружинит и подпрыгивает на громких слогах, а на ударных словах чуть растягивается. Самый энергичный." },
    { k: "C", t: "Рот + мимика по фразам", d: "Рот в такт голосу, а голова играет по смыслу: кивает на «Привет!», подпрыгивает на имени, наклоняется на вопросе «Что приготовить?»." }
  ];
  var ctx = null, analyser = null, buf = null, audio = new Audio(), active = null, raf = 0, srcNode = null;
  function setup() {
    if (ctx) return;
    var AC = window.AudioContext || window.webkitAudioContext; ctx = new AC();
    srcNode = ctx.createMediaElementSource(audio); analyser = ctx.createAnalyser(); analyser.fftSize = 512;
    srcNode.connect(analyser); analyser.connect(ctx.destination); buf = new Uint8Array(analyser.fftSize);
  }
  function level() { analyser.getByteTimeDomainData(buf); var m = 0; for (var i = 0; i < buf.length; i++) m = Math.max(m, Math.abs(buf[i] - 128)); return Math.min(1, m / 70); }
  function mk(v) {
    var c = document.createElement("div"); c.className = "cell";
    c.innerHTML = '<div class="tag"><b>' + v.k + '</b>' + v.t + '</div><div class="dsc">' + v.d + '</div>';
    var scr = document.createElement("div"); scr.className = "scr";
    var imgs = ["closed", "mid", "wide", "round", "blink"].map(function (n) { return '<img data-n="' + n + '" alt="" src="' + F[n] + '"' + (n === "closed" ? ' class="on"' : '') + '>'; }).join("");
    scr.innerHTML = '<div class="dlg"><div class="bust">' + imgs + '</div><h3>Привет! Я Bonchbrik</h3><div class="line"></div></div>';
    c.appendChild(scr);
    var bw = document.createElement("div"); bw.className = "btns";
    ["ru", "uz"].forEach(function (l) { var b = document.createElement("button"); b.className = "go"; b.textContent = "Говорит " + l.toUpperCase(); b.onclick = function () { start(v, scr, l); }; bw.appendChild(b); });
    c.appendChild(bw);
    return c;
  }
  function show(scr, n) { var els = scr.querySelectorAll(".bust img"); for (var i = 0; i < els.length; i++) els[i].classList.toggle("on", els[i].getAttribute("data-n") === n); }
  function reset(scr) { scr.querySelector(".bust").style.transform = ""; show(scr, "closed"); scr.querySelector(".line").textContent = ""; }
  function start(v, scr, lang) {
    setup(); if (ctx.state === "suspended") ctx.resume();
    if (active) { reset(active); cancelAnimationFrame(raf); }
    active = scr; audio.src = AUD[lang]; audio.currentTime = 0; audio.play();
    var bust = scr.querySelector(".bust"), line = scr.querySelector(".line"), t0 = performance.now(), nextBlink = 0.8, blinkUntil = 0, alt = 0, smooth = 0, prevOpen = 0;
    (function frame() {
      var t = (performance.now() - t0) / 1000, ct = audio.currentTime, l = level();
      smooth += (l - smooth) * 0.55;
      var text = ""; WORDS[lang].forEach(function (w) { if (ct >= w[0]) text += (text ? " " : "") + w[1]; }); line.textContent = text;
      var m = "closed";
      if (smooth > 0.62) { m = (Math.floor(ct * 7) % 3 === 0) ? "round" : "wide"; } else if (smooth > 0.32) m = "wide"; else if (smooth > 0.14) m = "mid";
      if (t > nextBlink) { blinkUntil = t + 0.13; nextBlink = t + 1.6 + Math.random() * 1.8; }
      if (t < blinkUntil && m === "closed") m = "blink";
      show(scr, m);
      var tf = "";
      if (v.k === "A") tf = "translateY(" + (Math.sin(t * 7) * 1.2).toFixed(1) + "px)";
      if (v.k === "B") { var pop = Math.max(0, smooth - 0.3); tf = "translateY(" + (-pop * 16).toFixed(1) + "px) scale(" + (1 - pop * 0.06).toFixed(3) + "," + (1 + pop * 0.12).toFixed(3) + ")"; }
      if (v.k === "C") {
        var pop2 = Math.max(0, smooth - 0.3), rot = 0, lift = 0, w = WORDS[lang];
        if (ct < w[1][0]) { rot = Math.sin(ct * 14) * 3.5; lift = 4; }
        else if (ct < w[2][0]) { lift = 10 * pop2 + 2; rot = Math.sin(ct * 9) * 1.5; }
        else { rot = -5.5; lift = 3 * pop2; }
        tf = "translateY(" + (-(lift)).toFixed(1) + "px) rotate(" + rot.toFixed(2) + "deg) scale(" + (1 + pop2 * 0.03).toFixed(3) + ")";
      }
      bust.style.transform = tf;
      if (!audio.paused && !audio.ended) raf = requestAnimationFrame(frame); else { reset(scr); active = null; }
    })();
  }
  var g = document.getElementById("grid"); VARS.forEach(function (v) { g.appendChild(mk(v)); });
})();
</script></body></html>"""


def main() -> None:
    html = HTML
    for n in NAMES:
        html = html.replace(f"__{n.upper()}__", frame(n))
    html = html.replace("__RU__", audio("ru")).replace("__UZ__", audio("uz"))
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"{os.path.normpath(OUT)}: {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
