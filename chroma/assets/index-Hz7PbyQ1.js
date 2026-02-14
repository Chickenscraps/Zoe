(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const i of document.querySelectorAll('link[rel="modulepreload"]'))a(i);new MutationObserver(i=>{for(const s of i)if(s.type==="childList")for(const o of s.addedNodes)o.tagName==="LINK"&&o.rel==="modulepreload"&&a(o)}).observe(document,{childList:!0,subtree:!0});function r(i){const s={};return i.integrity&&(s.integrity=i.integrity),i.referrerPolicy&&(s.referrerPolicy=i.referrerPolicy),i.crossOrigin==="use-credentials"?s.credentials="include":i.crossOrigin==="anonymous"?s.credentials="omit":s.credentials="same-origin",s}function a(i){if(i.ep)return;i.ep=!0;const s=r(i);fetch(i.href,s)}})();const V=15,P=2.5,U=3,D=20;function j(e){let t;e<=2?t=2:e<=5?t=3:e<=9?t=4:e<=14?t=5:e<=20?t=6:e<=27?t=7:t=8;const s=Math.max(3,40*Math.pow(.88,e-1));return{gridSize:t,colorDiff:s}}function S(){return{level:1,score:0,timeLeft:V,gridSize:2,colorDiff:40,baseHue:0,baseSat:0,baseLit:0,targetIndex:0,isActive:!1,correctCount:0,wrongCount:0,startTime:0,fastestReaction:1/0,lastTapTime:0}}function C(e){const t=j(e.level),r=t.gridSize*t.gridSize,a=Math.random()*360,i=50+Math.random()*30,s=40+Math.random()*25,o=Math.floor(Math.random()*r);return{...e,gridSize:t.gridSize,colorDiff:t.colorDiff,baseHue:a,baseSat:i,baseLit:s,targetIndex:o,lastTapTime:Date.now()}}function z(e){return`hsl(${e.baseHue}, ${e.baseSat}%, ${e.baseLit}%)`}function x(e){const t=Math.random()>.5?1:-1,r=Math.max(10,Math.min(90,e.baseLit+e.colorDiff*t*.4)),a=e.colorDiff*.15*(Math.random()>.5?1:-1);return`hsl(${e.baseHue+a}, ${e.baseSat}%, ${r}%)`}function N(e){const r=Date.now()-e.lastTapTime,a=Math.max(0,Math.floor((3e3-r)/100)),i=e.level*10+a;return{...e,level:e.level+1,score:e.score+i,timeLeft:Math.min(D,e.timeLeft+P),correctCount:e.correctCount+1,fastestReaction:Math.min(e.fastestReaction,r)}}function G(e){return{...e,timeLeft:Math.max(0,e.timeLeft-U),wrongCount:e.wrongCount+1}}function H(e,t){return{...e,timeLeft:Math.max(0,e.timeLeft-t)}}function E(e){return e.timeLeft<=0}function A(e){return e<=3?{title:"Color Curious",emoji:"👀",description:"You see colors, but the subtle shades escape you. Keep training!",color:"#94a3b8"}:e<=6?{title:"Shade Spotter",emoji:"🔍",description:"Not bad! You can pick up most color differences. Room to grow!",color:"#4ade80"}:e<=10?{title:"Color Sharp",emoji:"🎯",description:"Impressive perception! You see what most people miss.",color:"#38bdf8"}:e<=15?{title:"Eagle Eye",emoji:"🦅",description:"Outstanding! Your color vision is sharper than 90% of players.",color:"#a855f7"}:e<=20?{title:"Chroma Master",emoji:"👑",description:"Elite-level perception. You see the invisible differences.",color:"#f472b6"}:e<=27?{title:"Pixel Perfect",emoji:"💎",description:"Near-superhuman color vision. Are you even real?",color:"#fbbf24"}:{title:"Chromatic God",emoji:"🌈",description:"Legendary. Your eyes operate on a different wavelength entirely.",color:"#f87171"}}function q(e){return e<=2?20:e<=4?35:e<=6?50:e<=8?65:e<=10?75:e<=13?85:e<=16?90:e<=20?95:e<=25?98:99}function B(e,t){const r=A(e),a=F(e);return`🎨 Chroma - Color Vision Challenge

${r.emoji} ${r.title}
Level ${e} | Score ${t}

${a}

How sharp are YOUR eyes?`}function F(e){const t=Math.min(e,10),r=10-t;return"🟪".repeat(t)+"⬛".repeat(r)}let g=null;function p(){return g||(g=new AudioContext),g}function Y(){try{const e=p(),t=e.createOscillator(),r=e.createGain();t.connect(r),r.connect(e.destination),t.type="sine",t.frequency.setValueAtTime(523,e.currentTime),t.frequency.setValueAtTime(659,e.currentTime+.08),r.gain.setValueAtTime(.15,e.currentTime),r.gain.exponentialRampToValueAtTime(.001,e.currentTime+.2),t.start(e.currentTime),t.stop(e.currentTime+.2)}catch{}}function J(){try{const e=p(),t=e.createOscillator(),r=e.createGain();t.connect(r),r.connect(e.destination),t.type="square",t.frequency.setValueAtTime(200,e.currentTime),t.frequency.setValueAtTime(150,e.currentTime+.1),r.gain.setValueAtTime(.1,e.currentTime),r.gain.exponentialRampToValueAtTime(.001,e.currentTime+.25),t.start(e.currentTime),t.stop(e.currentTime+.25)}catch{}}function Z(){try{const e=p();[523,659,784].forEach((r,a)=>{const i=e.createOscillator(),s=e.createGain();i.connect(s),s.connect(e.destination),i.type="sine",i.frequency.setValueAtTime(r,e.currentTime+a*.08),s.gain.setValueAtTime(.12,e.currentTime+a*.08),s.gain.exponentialRampToValueAtTime(.001,e.currentTime+a*.08+.15),i.start(e.currentTime+a*.08),i.stop(e.currentTime+a*.08+.15)})}catch{}}function W(){try{const e=p();[392,349,311,262].forEach((r,a)=>{const i=e.createOscillator(),s=e.createGain();i.connect(s),s.connect(e.destination),i.type="sine",i.frequency.setValueAtTime(r,e.currentTime+a*.15),s.gain.setValueAtTime(.12,e.currentTime+a*.15),s.gain.exponentialRampToValueAtTime(.001,e.currentTime+a*.15+.3),i.start(e.currentTime+a*.15),i.stop(e.currentTime+a*.15+.3)})}catch{}}const v="https://qwdkadwuyejyadwptgfd.supabase.co",m="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3ZGthZHd1eWVqeWFkd3B0Z2ZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA2MDM1MzQsImV4cCI6MjA4NjE3OTUzNH0.Lo946df4Vy_bVWjTgJtBIWo7c1PSXQw5M2r9ixCl9Q8";let l="";function y(){if(l)return l;const e=sessionStorage.getItem("chroma_session_id");return e?(l=e,l):(l=crypto.randomUUID(),sessionStorage.setItem("chroma_session_id",l),l)}function X(){const e=new URLSearchParams(window.location.search);return e.get("ref")||e.get("utm_source")||document.referrer||"direct"}function Q(){const t=new URLSearchParams(window.location.search).get("c");return t?parseInt(t,10):null}async function d(e,t){const r={session_id:y(),event:e,referrer:X(),challenge_level:Q(),level:t?.level??null,score:t?.score??null,metadata:t?.metadata??null,created_at:new Date().toISOString()};try{await fetch(`${v}/rest/v1/chroma_events`,{method:"POST",headers:{"Content-Type":"application/json",apikey:m,Authorization:`Bearer ${m}`,Prefer:"return=minimal"},body:JSON.stringify(r)})}catch{}}async function K(e,t,r){try{await fetch(`${v}/rest/v1/chroma_leaderboard`,{method:"POST",headers:{"Content-Type":"application/json",apikey:m,Authorization:`Bearer ${m}`,Prefer:"return=minimal"},body:JSON.stringify({session_id:y(),nickname:r||"Anonymous",level:e,score:t,created_at:new Date().toISOString()})})}catch{}}async function ee(e=10){try{const t=await fetch(`${v}/rest/v1/chroma_leaderboard?select=nickname,level,score&order=level.desc,score.desc&limit=${e}`,{headers:{apikey:m,Authorization:`Bearer ${m}`}});return t.ok?await t.json():[]}catch{return[]}}const c={pageView:()=>d("page_view"),gameStart:()=>d("game_start"),levelComplete:(e,t)=>d("level_complete",{level:e,score:t}),gameOver:(e,t)=>d("game_over",{level:e,score:t}),shareClick:(e,t)=>d("share_click",{level:t,metadata:{platform:e}}),challengeOpen:e=>d("challenge_open",{level:e}),playAgain:()=>d("play_again"),submitScore:K,getTopScores:ee,getSessionId:y};let n=S(),u=null,b="";const T=new URLSearchParams(window.location.search),f=T.get("c")?parseInt(T.get("c"),10):null;function te(){const e=document.getElementById("app");e.innerHTML=`
    <div class="bg-glow"></div>

    <!-- Start Screen -->
    <div id="screen-start" class="screen active">
      <h1 class="logo fade-up">Chroma</h1>
      <p class="tagline fade-up fade-up-delay-1">How sharp are your eyes?<br/>Find the different shade before time runs out.</p>
      ${f?`
        <div class="challenge-banner fade-up fade-up-delay-2">
          Someone challenged you to beat <strong>Level ${f}</strong>!
        </div>
      `:""}
      <button id="btn-start" class="btn btn-primary fade-up fade-up-delay-2">Play Now</button>
      <div class="how-to-play fade-up fade-up-delay-3">
        <strong>How to play:</strong> Tap the tile that's a<br/>different shade. Be fast — the clock is ticking!
      </div>
    </div>

    <!-- Game Screen -->
    <div id="screen-game" class="screen">
      <div class="game-header">
        <div class="game-stat">
          <span class="game-stat-label">Level</span>
          <span id="game-level" class="game-stat-value">1</span>
        </div>
        <div class="game-stat">
          <span class="game-stat-label">Score</span>
          <span id="game-score" class="game-stat-value">0</span>
        </div>
        <div class="game-stat">
          <span class="game-stat-label">Time</span>
          <span id="game-time" class="game-stat-value">15.0</span>
        </div>
      </div>
      <div class="timer-bar">
        <div id="timer-bar-fill" class="timer-bar-fill"></div>
      </div>
      <div class="grid-container">
        <div id="game-grid" class="grid"></div>
      </div>
    </div>

    <!-- Result Screen -->
    <div id="screen-result" class="screen">
      <div class="result-card" id="result-card">
        <div id="result-level" class="result-level">0</div>
        <div class="result-level-label">Level Reached</div>
        <div id="result-title" class="result-title"></div>
        <div id="result-description" class="result-description"></div>
        <div class="result-stats">
          <div class="result-stat">
            <span id="result-score" class="result-stat-value">0</span>
            <span class="result-stat-label">Score</span>
          </div>
          <div class="result-stat">
            <span id="result-correct" class="result-stat-value">0</span>
            <span class="result-stat-label">Correct</span>
          </div>
          <div class="result-stat">
            <span id="result-speed" class="result-stat-value">-</span>
            <span class="result-stat-label">Fastest</span>
          </div>
        </div>
        <div id="result-percentile" class="result-percentile"></div>
        <div class="result-actions">
          <button id="btn-share" class="btn btn-share btn-sm">Copy Result & Challenge Link</button>
          <div class="share-row">
            <button id="btn-twitter" class="btn btn-twitter btn-sm">Share on X</button>
            <button id="btn-again" class="btn btn-secondary btn-sm">Play Again</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Level Up Flash -->
    <div id="level-up-flash" class="level-up-flash">
      <span class="level-up-text" id="level-up-text"></span>
    </div>

    <!-- Copied Toast -->
    <div id="copied-toast" class="copied-toast">Copied to clipboard!</div>
  `,document.getElementById("btn-start").addEventListener("click",$),document.getElementById("btn-share").addEventListener("click",ae),document.getElementById("btn-twitter").addEventListener("click",oe),document.getElementById("btn-again").addEventListener("click",ce)}function M(e){document.querySelectorAll(".screen").forEach(t=>t.classList.remove("active")),document.getElementById(`screen-${e}`).classList.add("active")}function $(){n=S(),n.isActive=!0,n.startTime=Date.now(),n=C(n),b=x(n),M("game"),O(),h(),re(),c.gameStart(),f&&c.challengeOpen(f)}function O(){const e=document.getElementById("game-grid"),{gridSize:t,targetIndex:r}=n,a=t*t;e.style.gridTemplateColumns=`repeat(${t}, 1fr)`,e.innerHTML="";const i=z(n);for(let s=0;s<a;s++){const o=document.createElement("div");o.className="tile",o.style.backgroundColor=s===r?b:i,o.dataset.index=String(s),o.addEventListener("click",()=>ne(s,o)),e.appendChild(o)}}function ne(e,t){if(n.isActive)if(e===n.targetIndex){t.classList.add("correct"),Y();const r=n.level;n=N(n),c.levelComplete(n.level-1,n.score),n.gridSize,n.level>1&&w(n.level)>w(r)&&(se(n.level),Z()),n=C(n),b=x(n),setTimeout(()=>{O(),h()},150)}else t.classList.add("wrong"),J(),n=G(n),h(),E(n)&&k()}function w(e){return e<=2?2:e<=5?3:e<=9?4:e<=14?5:e<=20?6:e<=27?7:8}function re(){u&&clearInterval(u);const e=50;u=setInterval(()=>{n.isActive&&(n=H(n,e/1e3),_(),E(n)&&k())},e)}function ie(){u&&(clearInterval(u),u=null)}function h(){document.getElementById("game-level").textContent=String(n.level),document.getElementById("game-score").textContent=String(n.score),_()}function _(){const e=document.getElementById("game-time"),t=document.getElementById("timer-bar-fill"),a=n.timeLeft/20*100;e.textContent=n.timeLeft.toFixed(1),t.style.width=`${Math.max(0,a)}%`,t.classList.remove("low","critical"),n.timeLeft<=3?(t.classList.add("critical"),e.style.color="#f87171"):n.timeLeft<=6?(t.classList.add("low"),e.style.color="#fbbf24"):e.style.color=""}function se(e){const t=document.getElementById("level-up-flash"),r=document.getElementById("level-up-text");r.textContent=`Level ${e}`,t.classList.remove("show"),t.offsetHeight,t.classList.add("show"),setTimeout(()=>t.classList.remove("show"),700)}function k(){n.isActive=!1,ie(),W();const e=A(n.level),t=q(n.level);document.getElementById("result-level").textContent=String(n.level),document.getElementById("result-title").textContent=`${e.emoji} ${e.title}`,document.getElementById("result-title").style.color=e.color,document.getElementById("result-description").textContent=e.description,document.getElementById("result-score").textContent=String(n.score),document.getElementById("result-correct").textContent=String(n.correctCount),document.getElementById("result-speed").textContent=n.fastestReaction<1/0?`${(n.fastestReaction/1e3).toFixed(2)}s`:"-",document.getElementById("result-percentile").textContent=`Top ${100-t}% of players`,M("result"),c.gameOver(n.level,n.score),c.submitScore(n.level,n.score)}function R(){return`${window.location.origin+window.location.pathname}?c=${n.level}&ref=share`}function ae(){const e=B(n.level,n.score),t=R(),r=`${e}
${t}`;navigator.share?navigator.share({text:r}).catch(()=>{I(r)}):I(r),c.shareClick("copy",n.level)}function oe(){const e=B(n.level,n.score),t=R(),r=`https://twitter.com/intent/tweet?text=${encodeURIComponent(e)}&url=${encodeURIComponent(t)}`;window.open(r,"_blank"),c.shareClick("twitter",n.level)}function I(e){navigator.clipboard.writeText(e).then(()=>{L()}).catch(()=>{const t=document.createElement("textarea");t.value=e,t.style.position="fixed",t.style.left="-9999px",document.body.appendChild(t),t.select(),document.execCommand("copy"),document.body.removeChild(t),L()})}function L(){const e=document.getElementById("copied-toast");e.classList.add("show"),setTimeout(()=>e.classList.remove("show"),2e3)}function ce(){c.playAgain(),$()}te();c.pageView();
