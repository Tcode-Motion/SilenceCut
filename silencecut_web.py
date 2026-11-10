#!/usr/bin/env python3
"""SilenceCut editor UI: local web app served by Python's stdlib server.
Drag and drop a video, preview it, see the silence map on a timeline,
pick a caption template, process, preview the result. 127.0.0.1 only."""
import json, os, re, subprocess, sys, threading, uuid, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys as _sys
        exc = _sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import silencecut as sc

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "silencecut_settings.json")
UPLOADS = os.path.join(HERE, "uploads")

LANGS = [("auto", "Auto detect"), ("en", "English"), ("hi", "Hindi"), ("bn", "Bengali"),
         ("es", "Spanish"), ("fr", "French"), ("de", "German"), ("it", "Italian"),
         ("pt", "Portuguese"), ("ru", "Russian"), ("ja", "Japanese"), ("ko", "Korean"),
         ("zh", "Chinese"), ("ar", "Arabic"), ("ur", "Urdu"), ("ta", "Tamil"),
         ("te", "Telugu"), ("mr", "Marathi"), ("gu", "Gujarati"), ("pa", "Punjabi"),
         ("ml", "Malayalam"), ("kn", "Kannada"), ("ne", "Nepali"), ("id", "Indonesian"),
         ("ms", "Malay"), ("th", "Thai"), ("vi", "Vietnamese"), ("tr", "Turkish"),
         ("nl", "Dutch"), ("pl", "Polish"), ("uk", "Ukrainian"), ("sv", "Swedish")]

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SilenceCut</title>
<style>
:root{--bg:#070b14;--panel:#0b1220;--card:#0e1626;--inset:#0a111d;--line:#1e2a42;--line2:#263650;--txt:#e9eef6;--mut:#8b96a8;--mut2:#5d6b82;--amber:#f5b83d;--amber2:#cf9420;--green:#3ddc74;--red:#ff6b64}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1100px 650px at 50% -8%,#12223e 0%,var(--bg) 60%);color:var(--txt);font-family:"Segoe UI",system-ui,-apple-system,sans-serif;min-height:100vh;padding:18px;font-size:14px}
.app{max-width:1180px;margin:0 auto;background:linear-gradient(180deg,#0b1220,#080d17);border:1px solid var(--line);border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,.6);overflow:hidden}
header{display:flex;align-items:center;gap:12px;padding:13px 20px;border-bottom:1px solid var(--line)}
.logo{width:36px;height:36px}
h1{font-size:24px;margin:0;font-weight:700;letter-spacing:.2px}
.pill{border:1px solid var(--amber2);color:var(--amber);background:rgba(245,184,61,.07);border-radius:999px;padding:4px 12px;font-size:12px;font-weight:700}
.right{margin-left:auto;display:flex;align-items:center;gap:16px;color:var(--mut);font-size:12.5px}
.gdot{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;margin-left:5px;box-shadow:0 0 8px var(--green)}
.settings{background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:9px;padding:7px 13px;font-size:12.5px;cursor:pointer}
.top{display:grid;grid-template-columns:1fr 316px;gap:14px;padding:15px 15px 0}
section{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:15px;display:flex;flex-direction:column;min-width:0}
.shead{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}
h2{font-size:11.5px;letter-spacing:2px;color:#c7d2e4;margin:0;text-transform:uppercase;font-weight:700}
.shead .hint{color:var(--mut2);font-size:11.5px}
label.flabel{font-size:12.5px;color:#c7d2e4;display:block;margin:13px 0 6px;font-weight:600}
input[type=text],select{width:100%;background:var(--inset);border:1px solid var(--line);border-radius:9px;color:var(--txt);padding:9px 11px;font-size:13px;outline:none;font-family:inherit}
input[type=text]:focus,select:focus{border-color:var(--amber2)}
input[type=range]{width:100%;accent-color:var(--amber);height:20px}
.val{color:var(--amber);font-weight:700}
.pathrow{display:flex;gap:8px}
.pathrow input{flex:1}
.pathrow button{background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:9px;padding:0 14px;cursor:pointer;font-size:12.5px}
.dropbar{margin-top:10px;border:1.5px dashed #2a3c5f;border-radius:9px;padding:8px;text-align:center;color:var(--amber);font-size:11.5px;letter-spacing:1.6px;font-weight:700}
.playerwrap{background:#000;border:1px solid var(--line);border-radius:11px;overflow:hidden;margin-top:10px}
video{width:100%;height:300px;display:block;background:#000;object-fit:contain}
.transport{display:flex;align-items:center;gap:12px;margin-top:10px}
.playbtn{width:38px;height:38px;border-radius:50%;border:1px solid var(--amber2);background:rgba(245,184,61,.1);color:var(--amber);font-size:15px;cursor:pointer;flex:0 0 38px}
.time{font-variant-numeric:tabular-nums;color:#c7d2e4;font-size:13px;white-space:nowrap}
#miniWave{flex:1;height:34px;background:var(--inset);border:1px solid var(--line);border-radius:7px}
.analysis{margin-top:11px;color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);padding-top:10px}
.analysis b{color:var(--txt)}
.gen{width:100%;margin-top:16px;background:linear-gradient(180deg,#ffc44d,var(--amber2));border:0;color:#171207;font-size:15.5px;font-weight:800;letter-spacing:.7px;border-radius:11px;padding:15px;cursor:pointer;box-shadow:0 12px 26px rgba(245,184,61,.25)}
.gen:hover{filter:brightness(1.06)}.gen:disabled{opacity:.55;cursor:wait}
.btnrow{display:flex;gap:8px;margin-top:9px}
.ghost{flex:1;background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:10px;font-size:12.5px;cursor:pointer;display:none}
.bar{height:5px;background:#131f38;border-radius:3px;margin-top:14px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--amber2),var(--amber));transition:width .3s}
.status{color:#c7d2e4;font-size:12px;margin-top:9px;white-space:pre-line;line-height:1.55;max-height:104px;overflow:auto;background:var(--inset);border:1px solid var(--line);border-radius:9px;padding:9px 11px;min-height:44px}
.status::-webkit-scrollbar{width:8px}.status::-webkit-scrollbar-thumb{background:#22314d;border-radius:4px}
.tlwrap{padding:0 15px 15px}
.tlpanel{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:13px 15px;margin-top:14px}
.tlhead{display:flex;justify-content:space-between;align-items:baseline}
.tlsummary{color:var(--mut);font-size:12.5px}
.tracks{position:relative;margin-top:10px}
.track{display:flex;align-items:stretch;gap:10px;margin-top:8px}
.tlabel{flex:0 0 86px;color:var(--mut);font-size:11.5px;letter-spacing:.6px;text-transform:uppercase;padding-top:4px}
.tlane{position:relative;flex:1;background:var(--inset);border:1px solid var(--line);border-radius:7px;overflow:hidden}
#laneVid{height:52px}#laneAud{height:42px}
.tlane canvas{position:absolute;inset:0;width:100%;height:100%}
.zone{position:absolute;top:0;height:100%;background:rgba(255,107,100,.4);border-left:1px solid rgba(255,107,100,.7)}
.keepz{position:absolute;top:0;height:100%;background:rgba(61,220,116,.13)}
#playhead{position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 6px rgba(255,255,255,.6);left:96px;z-index:5;pointer-events:none}
#overlay{position:fixed;inset:0;background:rgba(4,8,15,.86);display:none;align-items:center;justify-content:center;z-index:30;font-size:25px;font-weight:800;color:var(--amber);letter-spacing:1px}
#overlay.on{display:flex}
.modal{position:fixed;inset:0;background:rgba(3,6,11,.7);display:none;align-items:center;justify-content:center;z-index:40}
.modal.on{display:flex}
.mbox{background:#0c1424;border:1px solid var(--line);border-radius:14px;padding:22px;width:430px;max-width:92vw}
.mbox h3{margin:0 0 8px;font-size:17px}.mbox p{color:var(--mut);font-size:13px;line-height:1.6}
.mbox .x{margin-top:14px;background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:9px;padding:9px 16px;cursor:pointer}
@media(max-width:900px){.top{grid-template-columns:1fr}}
</style></head>
<body>
<div id="overlay">Drop the video to load it</div>
<div class="app">
<header>
<svg class="logo" viewBox="0 0 100 100"><polygon points="50,4 90,27 90,73 50,96 10,73 10,27" fill="rgba(245,184,61,.12)" stroke="#f5b83d" stroke-width="6"/><path d="M32 38 L46 50 L32 62 M54 38 L68 50 L54 62" stroke="#f5b83d" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
<h1>SilenceCut</h1><span class="pill">Silence cutter</span>
<div class="right"><span id="saveState">Settings save automatically</span><span>Offline &bull; Local Only<span class="gdot"></span></span><button class="settings" id="settingsBtn">&#9881; Settings</button></div>
</header>
<div class="top">
<section>
<div class="shead"><h2>Monitor</h2><span class="hint">MP4, MOV, MKV, WebM</span></div>
<div class="pathrow"><input type="text" id="video" placeholder="Video file path"><button id="browseBtn">Browse</button></div>
<div class="dropbar">Drag &amp; drop video anywhere</div>
<div class="playerwrap"><video id="player" preload="metadata"></video></div>
<div class="transport">
<button class="playbtn" id="playBtn">&#9654;</button>
<span class="time" id="timeLbl">00:00 / 00:00</span>
<canvas id="miniWave" width="420" height="34"></canvas>
</div>
<div class="analysis" id="analysis">Load a video. SilenceCut maps the speech and the gaps, then cuts only the gaps.</div>
</section>
<section>
<div class="shead"><h2>Inspector</h2><span class="hint">Cut &amp; export</span></div>
<label class="flabel" style="margin-top:8px">Silence threshold: <span class="val" id="thVal">-35 dB</span></label>
<input type="range" id="thresh" min="-50" max="-20" step="1" value="-35">
<label class="flabel">Shortest silence to cut: <span class="val" id="mdVal">0.55 s</span></label>
<input type="range" id="mindur" min="0.2" max="2" step="0.05" value="0.55">
<label class="flabel">Breathing room padding: <span class="val" id="padVal">120 ms</span></label>
<input type="range" id="pad" min="0" max="500" step="10" value="120">
<label class="flabel">Output folder</label>
<input type="text" id="out" value="silencecut_out">
<label class="flabel">Quality</label>
<select id="quality"><option value="fast">Fast</option><option value="balanced" selected>Balanced</option><option value="best">Best (slower)</option></select>
<button class="gen" id="go">CUT VIDEO</button>
<div class="btnrow"><button class="ghost" id="previewBtn">Preview result</button><button class="ghost" id="openbtn">Open output folder</button></div>
<div class="bar"><i id="barFill"></i></div>
<div class="status" id="status">Ready. Drop a video to start.</div>
</section>
</div>
<div class="tlwrap"><div class="tlpanel">
<div class="tlhead"><h2>Timeline</h2><span class="tlsummary" id="tlSummary">No video loaded</span></div>
<div class="tracks" id="tracks">
<div id="playhead"></div>
<div class="track"><div class="tlabel">Video</div><div class="tlane" id="laneVid"><canvas id="cvVid"></canvas></div></div>
<div class="track"><div class="tlabel">Audio</div><div class="tlane" id="laneAud"><canvas id="cvAud"></canvas></div></div>
</div>
</div></div>
</div>
<div class="modal" id="modal"><div class="mbox">
<h3>Settings</h3>
<p>SilenceCut runs fully on this computer: ffmpeg finds the silent gaps and removes only those, keeping your speech untouched. No account, no API key, nothing is uploaded. The only files it writes are your exports, the settings file, and dropped videos in the uploads folder.</p>
<p>Every control on this window saves itself automatically and is restored on the next launch.</p>
<button class="x" id="modalX">Close</button>
</div></div>
<video id="thumbVid" preload="auto" muted style="display:none"></video>
<script>
let jobId=null, lastOut='', dur=0, silences=[], keeps=[], peaks=null, outDur=0, loadSeq=0;
const $=id=>document.getElementById(id);
const player=$('player');
const fmtT=s=>{s=Math.max(0,Math.floor(s));return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');};
fetch('/api/settings').then(r=>r.json()).then(d=>applySettings(d));
function slider(id,vid,fmt){const e=$(id);const f=()=>{$(vid).textContent=fmt(parseFloat(e.value));};e.addEventListener('input',()=>{f();debDetect();saveSettings();});f();}
slider('thresh','thVal',v=>v+' dB');slider('mindur','mdVal',v=>v.toFixed(2)+' s');slider('pad','padVal',v=>v+' ms');
['quality','out'].forEach(id=>$(id).addEventListener('change',saveSettings));
$('settingsBtn').addEventListener('click',()=>$('modal').classList.add('on'));
$('modalX').addEventListener('click',()=>$('modal').classList.remove('on'));
$('modal').addEventListener('click',e=>{if(e.target===$('modal'))$('modal').classList.remove('on');});
let saveTimer=null;
function settingsObj(){return{thresh:parseFloat($('thresh').value),min_dur:parseFloat($('mindur').value),pad:parseFloat($('pad').value),quality:$('quality').value,out:$('out').value};}
function applySettings(d){
  if(!d||!Object.keys(d).length)return;
  if(d.thresh!==undefined){$('thresh').value=d.thresh;$('thVal').textContent=d.thresh+' dB';}
  if(d.min_dur!==undefined){$('mindur').value=d.min_dur;$('mdVal').textContent=(+d.min_dur).toFixed(2)+' s';}
  if(d.pad!==undefined){$('pad').value=d.pad;$('padVal').textContent=d.pad+' ms';}
  if(d.quality)$('quality').value=d.quality;
  if(d.out)$('out').value=d.out;
}
function saveSettings(){clearTimeout(saveTimer);saveTimer=setTimeout(()=>{fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settingsObj())}).then(()=>{$('saveState').textContent='All settings saved';});},500);}
function videoURL(path){return '/api/video?path='+encodeURIComponent(path)+'&v='+loadSeq;}
function loadVideo(path){
  loadSeq++;
  const seq=loadSeq;
  peaks=null;silences=[];keeps=[];dur=0;outDur=0;lastOut='';
  $('previewBtn').style.display='none';$('openbtn').style.display='none';
  $('barFill').style.width='0%';$('timeLbl').textContent='00:00 / 00:00';
  $('tlSummary').textContent='Loading...';
  drawZones();drawAudio();
  try{player.pause();}catch(e){}
  $('video').value=path;player.src=videoURL(path);player.load();
  detect(seq);buildWave(path,seq);buildThumbs(path,seq);
}
$('video').addEventListener('change',()=>{if($('video').value.trim())loadVideo($('video').value.trim());});
$('video').addEventListener('keydown',e=>{if(e.key==='Enter'&&$('video').value.trim())loadVideo($('video').value.trim());});
player.addEventListener('error',()=>{if(player.src)$('status').textContent='Could not play this file in the preview. The cut will still work if ffmpeg can read it.';});
$('browseBtn').addEventListener('click',()=>fetch('/api/pickfile').then(r=>r.json()).then(d=>{if(d.ok&&d.path)loadVideo(d.path);else if(!d.ok)$('status').textContent='Picker unavailable here. Paste the path instead.';}));
['dragenter','dragover'].forEach(ev=>document.addEventListener(ev,e=>{e.preventDefault();$('overlay').classList.add('on');}));
document.addEventListener('dragleave',e=>{if(!e.relatedTarget)$('overlay').classList.remove('on');});
document.addEventListener('drop',e=>{
  e.preventDefault();$('overlay').classList.remove('on');
  const f=e.dataTransfer.files&&e.dataTransfer.files[0];if(!f)return;
  $('status').textContent='Uploading '+f.name+' ('+(f.size/1048576).toFixed(1)+' MB) ...';
  fetch('/api/upload',{method:'POST',headers:{'X-Filename':f.name},body:f}).then(r=>r.json()).then(d=>{
    if(d.ok){loadVideo(d.path);$('status').textContent='Loaded '+f.name;}else{$('status').textContent='Upload failed: '+d.error;}
  });
});
let detTimer=null;
function debDetect(){clearTimeout(detTimer);detTimer=setTimeout(()=>detect(loadSeq),450);}
function detect(seq){
  const path=$('video').value.trim();if(!path)return;
  fetch('/api/detect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({video:path,thresh:parseFloat($('thresh').value),min_dur:parseFloat($('mindur').value),pad:parseFloat($('pad').value)/1000})})
   .then(r=>r.json()).then(d=>{
     if(seq!==loadSeq)return;
     if(!d.ok){$('analysis').textContent='Detect failed: '+d.error;return;}
     dur=d.duration;silences=d.silences;keeps=d.keeps;
     $('tlSummary').textContent='Timeline: '+fmtT(dur)+' - Silences removed: '+silences.length+' (-'+Math.round(dur-d.kept)+'s)';
     $('analysis').innerHTML='<b>Segment analysis</b> &nbsp;Duration: '+fmtT(dur)+' &bull; '+silences.length+' gaps detected &bull; <b>'+(dur-d.kept).toFixed(1)+'s to be saved</b>';
     drawZones();drawAudio();
   });
}
function drawZones(){
  const lane=$('laneVid');lane.querySelectorAll('.zone,.keepz').forEach(z=>z.remove());
  if(!dur)return;
  keeps.forEach(k=>{const z=document.createElement('div');z.className='keepz';z.style.left=(k[0]/dur*100)+'%';z.style.width=Math.max(.5,(k[1]-k[0])/dur*100)+'%';lane.appendChild(z);});
  silences.forEach(s=>{const z=document.createElement('div');z.className='zone';z.style.left=(s[0]/dur*100)+'%';z.style.width=Math.max(.5,(s[1]-s[0])/dur*100)+'%';lane.appendChild(z);});
}
function drawWave(canvas,color){
  const ctx=canvas.getContext('2d');const W=canvas.clientWidth||420,H=canvas.clientHeight||34;
  canvas.width=W;canvas.height=H;ctx.clearRect(0,0,W,H);
  if(!peaks){ctx.fillStyle='#22314d';ctx.fillRect(0,H/2-1,W,2);return;}
  ctx.fillStyle=color;const n=peaks.length;
  for(let i=0;i<n;i++){const x=i/n*W;const h=Math.max(1,peaks[i]*H*.92);ctx.fillRect(x,(H-h)/2,Math.max(1,W/n-0.5),h);}
}
function drawAudio(){
  drawWave($('miniWave'),'#3ddc74');
  const cv=$('cvAud');drawWave(cv,'#3ddc74');
  const lane=$('laneAud');lane.querySelectorAll('.zone').forEach(z=>z.remove());
  if(!dur)return;
  silences.forEach(s=>{const z=document.createElement('div');z.className='zone';z.style.left=(s[0]/dur*100)+'%';z.style.width=Math.max(.5,(s[1]-s[0])/dur*100)+'%';lane.appendChild(z);});
}
function buildWave(path,seq){
  peaks=null;drawAudio();
  fetch(videoURL(path),{cache:'no-store'}).then(r=>r.arrayBuffer()).then(async buf=>{
    if(seq!==loadSeq)return;
    try{
      const AC=window.AudioContext||window.webkitAudioContext;const ac=new AC();
      const audio=await ac.decodeAudioData(buf);const ch=audio.getChannelData(0);
      const N=240;const pk=[];const step=Math.floor(ch.length/N);
      for(let i=0;i<N;i++){let m=0;for(let j=0;j<step;j+=40){const v=Math.abs(ch[i*step+j]);if(v>m)m=v;}pk.push(m);}
      ac.close();
      if(seq!==loadSeq)return;
      peaks=pk;drawAudio();
    }catch(e){}
  }).catch(()=>{});
}
const thumbState={seq:0,times:[],idx:0,active:false};
function buildThumbs(path,seq){
  const cv=$('cvVid');const ctx=cv.getContext('2d');const W=cv.clientWidth||800,H=cv.clientHeight||52;
  cv.width=W;cv.height=H;ctx.fillStyle='#0a111d';ctx.fillRect(0,0,W,H);
  thumbState.seq=seq;thumbState.times=[];thumbState.idx=0;thumbState.active=true;
  const N=8;for(let i=0;i<N;i++)thumbState.times.push((i+0.5)/N);
  const tv=$('thumbVid');tv.src=videoURL(path);tv.load();
}
function thumbStep(){
  const tv=$('thumbVid');const st=thumbState;
  if(!st.active||st.seq!==loadSeq)return;
  if(st.idx>=st.times.length){st.active=false;drawZones();return;}
  const t=st.times[st.idx]*tv.duration;
  if(Math.abs(tv.currentTime-t)<0.02){thumbDraw();}
  else{tv.currentTime=t;}
}
function thumbDraw(){
  const tv=$('thumbVid');const st=thumbState;
  if(!st.active||st.seq!==loadSeq)return;
  const cv=$('cvVid');const ctx=cv.getContext('2d');const W=cv.width,H=cv.height;const N=st.times.length;const tw=W/N;
  try{ctx.drawImage(tv,st.idx*tw,0,tw,H);}catch(e){}
  st.idx++;thumbStep();
}
$('thumbVid').addEventListener('loadedmetadata',thumbStep);
$('thumbVid').addEventListener('seeked',thumbDraw);
player.addEventListener('timeupdate',()=>{
  const d=player.duration||dur;
  $('timeLbl').textContent=fmtT(player.currentTime)+' / '+fmtT(d||0);
  const tracks=$('tracks');if(tracks&&d){const r=tracks.getBoundingClientRect();$('playhead').style.left=(96+player.currentTime/d*(r.width-96))+'px';}
  $('playBtn').innerHTML=player.paused?'&#9654;':'&#10073;&#10073;';
});
$('playBtn').addEventListener('click',()=>{if(player.paused)player.play();else player.pause();});
player.addEventListener('click',()=>{if(player.paused)player.play();else player.pause();});
document.querySelectorAll('.tlane').forEach(lane=>lane.addEventListener('click',e=>{
  if(!dur)return;const r=lane.getBoundingClientRect();player.currentTime=(e.clientX-r.left)/r.width*dur;player.play();
}));
$('go').addEventListener('click',()=>{
  const s=settingsObj();const body={video:$('video').value.trim(),thresh:s.thresh,min_dur:s.min_dur,pad:s.pad/1000,captions:false,out:s.out,quality:s.quality};
  if(!body.video){$('status').textContent='Load a video first.';return;}
  $('go').disabled=true;$('status').textContent='Starting...';$('barFill').style.width='4%';
  fetch('/api/process',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
   .then(r=>r.json()).then(d=>{if(!d.ok){$('status').textContent='Failed: '+d.error;$('go').disabled=false;return;}jobId=d.job;poll();});
});
function poll(){
  fetch('/api/job?id='+jobId).then(r=>r.json()).then(d=>{
    $('barFill').style.width=d.pct+'%';$('status').textContent=d.logs.join('\n');
    if(d.done){$('go').disabled=false;
      if(d.result){lastOut=d.result.out;outDur=d.result.after;
        $('previewBtn').style.display='block';$('openbtn').style.display='block';
        $('tlSummary').textContent='Finished video: '+fmtT(outDur)+' (was '+fmtT(d.result.before)+')';}
      return;}
    setTimeout(poll,900);
  }).catch(()=>setTimeout(poll,1500));
}
$('previewBtn').addEventListener('click',()=>{player.src=videoURL(lastOut);player.load();player.play();});
$('openbtn').addEventListener('click',()=>fetch('/api/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:lastOut})}));
const qv=new URLSearchParams(location.search).get('video');if(qv)setTimeout(()=>loadVideo(qv),600);
const qt=new URLSearchParams(location.search).get('test');
if(qt&&qv){setTimeout(()=>loadVideo(qt),3500);setTimeout(()=>{
  loadVideo(qv);
  setTimeout(()=>{const d=document.createElement('div');d.id='testResult';
    d.textContent='dur='+dur.toFixed(2)+' silences='+silences.length+' playerDur='+(player.duration||0).toFixed(2)+' summary='+$('tlSummary').textContent;
    document.body.appendChild(d);},2500);
},8000);}
</script></body></html>"""

PICK_FILE = (
    "import tkinter as tk\n"
    "from tkinter import filedialog\n"
    "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
    "p = filedialog.askopenfilename(filetypes=[('Video', '*.mp4 *.mov *.mkv *.webm'), ('All', '*.*')])\n"
    "print(p or '')\n"
)
JOBS = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/templates":
            self._json({"templates": sc.load_templates()})
        elif u.path == "/api/langs":
            self._json({"langs": LANGS})
        elif u.path == "/api/settings":
            try:
                self._json(json.load(open(SETTINGS)))
            except Exception:
                self._json({})
        elif u.path == "/api/job":
            jid = parse_qs(u.query).get("id", [""])[0]
            self._json(JOBS.get(jid, {"done": True, "pct": 0, "logs": ["Unknown job"]}))
        elif u.path == "/api/pickfile":
            try:
                r = subprocess.run([sys.executable, "-c", PICK_FILE], capture_output=True, text=True, timeout=300)
                self._json({"ok": True, "path": r.stdout.strip()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        elif u.path == "/api/video":
            self._serve_video(parse_qs(u.query).get("path", [""])[0])
        else:
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _serve_video(self, path):
        if not path or not os.path.isfile(path):
            self.send_response(404); self.end_headers(); return
        size = os.path.getsize(path)
        rng = self.headers.get("Range", "")
        start, end = 0, size - 1
        if rng.startswith("bytes="):
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
                end = min(end, size - 1)
        if start >= size:
            self.send_response(416); self.end_headers(); return
        length = end - start + 1
        ext = os.path.splitext(path)[1].lower()
        ctype = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
                 ".mkv": "video/x-matroska", ".m4v": "video/mp4"}.get(ext, "video/mp4")
        try:
            self.send_response(206 if rng else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(262144, left))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except OSError:
                        break
                    left -= len(chunk)
        except OSError:
            pass

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/upload":
            name = os.path.basename(self.headers.get("X-Filename", "video.mp4")) or "video.mp4"
            os.makedirs(UPLOADS, exist_ok=True)
            dest = os.path.join(UPLOADS, name)
            if os.path.exists(dest):
                stem, ext = os.path.splitext(name)
                n = 2
                while os.path.exists(os.path.join(UPLOADS, f"{stem}-{n}{ext}")):
                    n += 1
                dest = os.path.join(UPLOADS, f"{stem}-{n}{ext}")
            left = int(self.headers.get("Content-Length", 0))
            try:
                with open(dest, "wb") as f:
                    while left > 0:
                        chunk = self.rfile.read(min(1048576, left))
                        if not chunk:
                            break
                        f.write(chunk)
                        left -= len(chunk)
            except OSError:
                try:
                    os.remove(dest)
                except OSError:
                    pass
                return
            self._json({"ok": True, "path": dest})
            return
        clen = int(self.headers.get("Content-Length", 0))
        if clen > 1048576:
            self._json({"ok": False, "error": "request too large"})
            return
        data = json.loads(self.rfile.read(clen) or b"{}")
        if u.path == "/api/settings":
            json.dump(data, open(SETTINGS, "w"), indent=1)
            self._json({"ok": True})
        elif u.path == "/api/detect":
            try:
                dur, w, h = sc.probe(data["video"])
                sil = sc.detect_silences(data["video"], data.get("thresh", -35), data.get("min_dur", 0.55))
                keeps = sc.keep_segments(dur, sil, data.get("pad", 0.12))
                self._json({"ok": True, "duration": dur, "silences": sil, "keeps": keeps,
                            "kept": sum(b - a for a, b in keeps), "width": w, "height": h})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        elif u.path == "/api/open":
            folder = os.path.dirname(os.path.abspath(data.get("path", ""))) or "."
            try:
                if sys.platform.startswith("win"):
                    os.startfile(folder)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
                self._json({"ok": True})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        elif u.path == "/api/process":
            video = data.get("video", "")
            if not video or not os.path.exists(video):
                self._json({"ok": False, "error": "Video file not found: " + video})
                return
            jid = uuid.uuid4().hex[:10]
            outdir = data.get("out") or "silencecut_out"
            os.makedirs(outdir, exist_ok=True)
            base = os.path.splitext(os.path.basename(video))[0]
            out = os.path.join(outdir, base + "_cut.mp4")
            job = {"done": False, "pct": 2, "logs": ["Job started."], "result": None}
            JOBS[jid] = job
            while len(JOBS) > 20:
                JOBS.pop(next(iter(JOBS)))

            def work():
                def log(msg):
                    job["logs"].append(msg)
                    job["pct"] = min(95, job["pct"] + 12)
                try:
                    r = sc.process(video, out, data.get("thresh", -35), data.get("min_dur", 0.55),
                                   data.get("pad", 0.12), data.get("captions", True),
                                   data.get("template", "amber-karaoke"), data.get("lang", "auto"),
                                   data.get("model", "base"), data.get("main_color", ""),
                                   data.get("high_color", ""), log=log,
                                   quality=data.get("quality", "balanced"))
                    r["out"] = os.path.abspath(out)
                    job["result"] = r
                    job["logs"].append(f"DONE: {r['before']:.1f}s -> {r['after']:.1f}s, saved {r['before'] - r['after']:.1f}s")
                except Exception as e:
                    job["logs"].append("FAILED: " + str(e))
                job["pct"] = 100
                job["done"] = True

            threading.Thread(target=work, daemon=True).start()
            self._json({"ok": True, "job": jid})
        else:
            self._json({"ok": False, "error": "unknown endpoint"}, 404)


def main():
    srv = None
    for port in range(8790, 8810):
        try:
            srv = QuietServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if srv is None:
        sys.exit("SilenceCut: no free local port found")
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print("SilenceCut UI running at " + url)
    try:
        import webview
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        webview.create_window("SilenceCut", url, width=1340, height=900)
        webview.start()
        return
    except Exception:
        pass
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
