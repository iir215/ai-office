"""Builds backend/app/static/shop/mascot_talk.html: a self-contained preview of ways to animate the
speaking mascot (images and the Russian greeting inlined, one request). Preview only."""
import base64
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
M = os.path.join(ROOT, "backend", "app", "static", "shop", "mascot")
OUT = os.path.join(ROOT, "backend", "app", "static", "shop", "mascot_talk.html")


def uri(name: str, mime: str) -> str:
    with open(os.path.join(M, name), "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


HTML = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bonchbrik говорит: варианты</title>
<link href="https://fonts.googleapis.com/css2?family=Handjet:wght@600;700;800&display=swap" rel="stylesheet">
<style>
  :root { --mustard:#FCC904; --ink:#141414; --paper:#FFF8DC; --f:"Handjet",system-ui,sans-serif; }
  * { box-sizing: border-box; border-radius: 0; }
  body { margin:0; background:#2a2a2a; color:#fff; font-family:var(--f); font-weight:600; font-size:21px; }
  h1 { font-size:32px; font-weight:800; text-align:center; margin:22px 12px 2px; color:var(--mustard); }
  .hint { text-align:center; margin:0 12px 14px; color:#ddd; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:30px; max-width:1100px; margin:0 auto; padding:8px 16px 30px; justify-items:center; }
  .cell { width:300px; }
  .tag { display:flex; gap:10px; align-items:baseline; font-size:26px; font-weight:800; margin-bottom:2px; }
  .tag b { background:var(--mustard); color:var(--ink); padding:0 9px; }
  .dsc { color:#ccc; font-size:20px; line-height:1.15; min-height:70px; margin-bottom:10px; }
  .scr { position:relative; width:300px; height:400px; background:var(--mustard); display:grid; place-items:center; overflow:hidden; box-shadow:0 0 0 4px #000, 0 0 0 8px #555; }
  .dlg { position:relative; width:252px; background:#fff; color:var(--ink); padding:84px 12px 14px; text-align:center; margin-top:44px;
    box-shadow:0 -3px 0 0 #000,0 3px 0 0 #000,-3px 0 0 0 #000,3px 0 0 0 #000,7px 7px 0 0 #fff8; }
  .dlg h3 { margin:0 0 4px; font-size:31px; font-weight:800; line-height:1; }
  .dlg .line { height:56px; font-size:25px; line-height:1.05; color:#4A4023; font-weight:700; }
  .bust { position:absolute; left:50%; top:-60px; margin-left:-62px; width:124px; height:124px; background:var(--mustard); transform-origin:50% 100%;
    box-shadow:0 -3px 0 0 #000,0 3px 0 0 #000,-3px 0 0 0 #000,3px 0 0 0 #000,6px 6px 0 0 #0004; }
  .bust .stage { position:absolute; inset:0; overflow:hidden; }
  .bust img { position:absolute; left:0; top:0; width:100%; height:100%; object-fit:cover; object-position:50% 12%; display:block; }
  .go { margin-top:6px; border:0; background:var(--mustard); font-family:var(--f); font-weight:800; font-size:24px; padding:3px 14px; color:#141414; cursor:pointer;
    box-shadow:0 -3px 0 0 #000,0 3px 0 0 #000,-3px 0 0 0 #000,3px 0 0 0 #000,3px 6px 0 0 #000; }
  .mouth { position:absolute; pointer-events:none; }
</style></head><body>
<h1>BONCHBRIK ГОВОРИТ</h1>
<p class="hint">Нажмите «Говорит» под вариантом: маскот заговорит голосом и оживёт. Это только макеты, приложение не менялось.</p>
<div class="grid" id="grid"></div>
<script>
(function () {
  var IMG = { base: "__BUST__", laugh: "__LAUGH__", peace: "__PEACE__" }, AUDIO = "__AUDIO__";
  var WORDS = [[0, "Привет!"], [0.55, "Я Бончбрик!"], [1.65, "Что тебе"], [2.3, "приготовить?"]];
  var VARS = [
    { k: "A", t: "Пружинит под голос", d: "Голова пружинит и чуть наклоняется в такт громкости голоса, как у мультяшного персонажа. Самый лёгкий и надёжный." },
    { k: "B", t: "Рот закрыт / открыт", d: "Пока он говорит, кадры меняются: спокойная улыбка и широко открытый рот в такт речи. Выглядит живее, но поза меняется." },
    { k: "C", t: "Пиксельный рот", d: "На лицо ложится воксельный рот из чёрных квадратов: открывается и закрывается по громкости. Говорит «по-настоящему», но рот нарисован мной." },
    { k: "D", t: "Видеоролик (нейросеть)", d: "Нейросеть делает короткое видео, где маскот говорит с движением губ, бровей и рук. Самый живой, но весит 0,5–1 МБ и стоит около $0,65 за ролик. Здесь не показан." }
  ];
  var ctx = null, analyser = null, buf = null, audio = new Audio(AUDIO), active = null, raf = 0;
  function setup() {
    if (ctx) return;
    var AC = window.AudioContext || window.webkitAudioContext; ctx = new AC();
    var src = ctx.createMediaElementSource(audio); analyser = ctx.createAnalyser(); analyser.fftSize = 512;
    src.connect(analyser); analyser.connect(ctx.destination); buf = new Uint8Array(analyser.fftSize);
  }
  function level() { analyser.getByteTimeDomainData(buf); var m = 0; for (var i = 0; i < buf.length; i++) m = Math.max(m, Math.abs(buf[i] - 128)); return Math.min(1, m / 70); }
  function mk(v) {
    var c = document.createElement("div"); c.className = "cell";
    c.innerHTML = '<div class="tag"><b>' + v.k + '</b>' + v.t + '</div><div class="dsc">' + v.d + '</div>';
    var scr = document.createElement("div"); scr.className = "scr";
    scr.innerHTML = '<div class="dlg"><div class="bust"><div class="stage"><img alt="" src="' + IMG.base + '"></div></div><h3>Привет! Я Bonchbrik</h3><div class="line"></div></div>';
    c.appendChild(scr);
    if (v.k !== "D") { var b = document.createElement("button"); b.className = "go"; b.textContent = "Говорит"; b.onclick = function () { start(v, scr, b); }; c.appendChild(b); }
    else { var n = document.createElement("div"); n.className = "dsc"; n.style.minHeight = "0"; n.textContent = "Покажу пример, если выберете этот вариант."; c.appendChild(n); }
    return c;
  }
  function reset(scr) {
    var bust = scr.querySelector(".bust"); bust.style.transform = ""; scr.querySelector("img").src = IMG.base; scr.querySelector(".line").textContent = "";
    var m = scr.querySelector(".mouth"); if (m) m.remove();
  }
  function start(v, scr, btn) {
    setup(); if (ctx.state === "suspended") ctx.resume();
    if (active) { reset(active.scr); cancelAnimationFrame(raf); }
    active = { v: v, scr: scr }; audio.currentTime = 0; audio.play();
    var bust = scr.querySelector(".bust"), stage = scr.querySelector(".stage"), im = scr.querySelector("img"), line = scr.querySelector(".line"), open = false, mouth = null, t0 = performance.now();
    if (v.k === "C") {
      mouth = document.createElement("div"); mouth.className = "mouth"; stage.appendChild(mouth);
    }
    (function frame() {
      var l = level(), t = (performance.now() - t0) / 1000, ct = audio.currentTime;
      var text = ""; WORDS.forEach(function (w) { if (ct >= w[0]) text += (text ? " " : "") + w[1]; }); line.textContent = text;
      if (v.k === "A") {
        bust.style.transform = "translateY(" + (-l * 7).toFixed(1) + "px) scale(" + (1 - l * 0.05).toFixed(3) + "," + (1 + l * 0.09).toFixed(3) + ") rotate(" + (Math.sin(t * 9) * 3 * l).toFixed(2) + "deg)";
      } else if (v.k === "B") {
        if (!open && l > 0.30) open = true; else if (open && l < 0.14) open = false;
        im.src = open ? IMG.laugh : IMG.base; bust.style.transform = "translateY(" + (open ? -3 : 0) + "px)";
      } else if (v.k === "C") {
        // the smile of the thumbs-up bust sits around x 54-77%, y 52-58%: cover it, then draw a block mouth
        var h = Math.round(4 + l * 18);
        mouth.innerHTML = '<div style="position:absolute;left:52%;top:50%;width:28%;height:12%;background:#E9A97E"></div>' +
          '<div style="position:absolute;left:56%;top:' + (53 - h / 8.6) + '%;width:20%;height:' + (h / 124 * 100) + '%;background:#2a1010;box-shadow:0 0 0 2px #141414"></div>' +
          (h > 10 ? '<div style="position:absolute;left:58%;top:' + (53 - h / 8.6) + '%;width:16%;height:3%;background:#fff"></div>' : '');
      }
      if (!audio.paused && !audio.ended) raf = requestAnimationFrame(frame); else { reset(scr); active = null; }
    })();
  }
  var g = document.getElementById("grid"); VARS.forEach(function (v) { g.appendChild(mk(v)); });
})();
</script></body></html>"""


def main() -> None:
    html = (HTML.replace("__BUST__", uri("bust_welcome.jpg", "image/jpeg"))
            .replace("__LAUGH__", uri("bust_laugh.jpg", "image/jpeg"))
            .replace("__PEACE__", uri("bust_peace.jpg", "image/jpeg"))
            .replace("__AUDIO__", uri("hello_ru.mp3", "audio/mpeg")))
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"{os.path.normpath(OUT)}: {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
