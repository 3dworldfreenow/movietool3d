"""🎤 Speak instead of typing: a microphone button on every idea / description / change-request box of the web pages.

Uses the browser's own speech recognition (Chrome, Edge, Safari - phone or PC; not Firefox). The browser only allows
the microphone on https:// pages or on http://localhost - see README "Voice input".
"""

VOICE = r"""
<style>
.vwrap{position:relative;display:block;width:100%;min-width:0}
.vwrap>input.hasmic,.vwrap>textarea.hasmic{width:100%;padding-right:84px!important}
.vwrap>input,.vwrap>textarea{width:100%}
.vmic,.vlang{position:absolute;top:6px;display:inline-flex;align-items:center;justify-content:center;height:34px;min-height:34px!important;
 border-radius:99px!important;border:1px solid var(--line,#ddd);background:var(--card,#fff);color:var(--ink,#111);cursor:pointer;z-index:2;
 line-height:1;padding:0!important}
.vmic{right:6px;width:34px;font-size:16px!important}
.vlang{right:44px;min-width:30px;padding:0 6px!important;font:700 11px system-ui,sans-serif!important;color:var(--mute,#666)!important}
.vwrap>input~.vmic,.vwrap>input~.vlang{top:50%;transform:translateY(-50%)}
.vmic:hover,.vlang:hover{border-color:var(--acc,#4f46e5)}
.vmic.rec{background:#dc2626;border-color:#dc2626;color:#fff;animation:vpulse 1.2s infinite}
@keyframes vpulse{0%{box-shadow:0 0 0 0 rgba(220,38,38,.5)}70%{box-shadow:0 0 0 9px rgba(220,38,38,0)}100%{box-shadow:0 0 0 0 rgba(220,38,38,0)}}
</style>
<script>
(()=>{
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 const WANT=/(^|_)(idea|desc|style|request|what)(_|$)|^pr_|^idea$|^style$/i;         // where people describe things
 const SKIP=/code|json|prompt|answer|key|name|seed|model|temp|fbtext|story$/i;
 const LANGS=[['en-IN','EN'],['hi-IN','हि']];
 let lang=(()=>{try{return localStorage.getItem('voiceLang')}catch(e){return null}})()||((navigator.language||'').startsWith('hi')?'hi-IN':'en-IN');
 let cur=null;                                                          // the one listening now
 const tag=()=>(LANGS.find(l=>l[0]===lang)||LANGS[0])[1];
 function stop(){if(cur){try{cur.rec.stop();}catch(e){}}}
 function start(el,btn){
  if(!SR||!window.isSecureContext){recordFile(el,btn);return;}     // http:// (or Firefox): record with the phone, server writes it
  if(cur){const same=cur.el===el;stop();if(same)return;}
  const rec=new SR();rec.lang=lang;rec.interimResults=true;rec.continuous=true;
  const base=el.value&&!/\s$/.test(el.value)?el.value+' ':el.value;let done='';
  cur={rec,el,btn};btn.classList.add('rec');btn.title='Listening… tap to stop';
  rec.onresult=e=>{let tmp='';for(let i=e.resultIndex;i<e.results.length;i++){const t=e.results[i][0].transcript;
    if(e.results[i].isFinal)done+=t+' ';else tmp+=t;}
   el.value=base+done+tmp;el.dispatchEvent(new Event('input',{bubbles:true}));};
  rec.onerror=e=>{if(e.error==='not-allowed'||e.error==='service-not-allowed')alert('Microphone blocked. Allow it for this site (the lock / camera icon in the address bar)'+(window.isSecureContext?'':' - and use https'));
   else if(e.error==='network')alert('Voice needs the internet (the browser sends the sound to its speech service).');};
  rec.onend=()=>{btn.classList.remove('rec');btn.title='Speak ('+lang+')';el.value=el.value.replace(/\s+$/,' ');
   el.dispatchEvent(new Event('change',{bubbles:true}));if(cur&&cur.rec===rec)cur=null;};
  try{rec.start();}catch(e){btn.classList.remove('rec');cur=null;}}
 // ---- http:// pages: the browser blocks live listening, but a phone can still RECORD with its own recorder app
 //      (a normal file upload); the server turns the recording into text (Gemini) and it goes into the box
 const phone=matchMedia('(pointer:coarse)').matches;
 function recordFile(el,btn){
  if(!phone&&!sessionStorage.getItem('vhint')){try{sessionStorage.setItem('vhint','1');}catch(e){}
   if(!confirm('This page is http://, so the browser blocks live listening.\n\nOK = choose a voice recording (on a phone the recorder opens).\n\nOn a PC it is easier to use the system dictation: Windows: press Win+H in the box · Mac: press Fn twice.'))return;}
  const f=document.createElement('input');f.type='file';f.accept='audio/*';f.setAttribute('capture','');f.style.display='none';
  document.body.appendChild(f);
  f.onchange=async()=>{const file=f.files[0];f.remove();if(!file)return;
   btn.classList.add('rec');btn.textContent='⏳';btn.title='Writing what you said…';
   const fd=new FormData();fd.append('audio',file);fd.append('lang',lang);
   try{const r=await (await fetch('/api/voice/transcribe',{method:'POST',body:fd})).json();
    if(r.ok&&r.text){const base=el.value&&!/\s$/.test(el.value)?el.value+' ':el.value;el.value=base+r.text.trim()+' ';
     el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}
    else alert(r.error||'Could not understand the recording.');}
   catch(e){alert('Could not send the recording: '+e);}
   btn.classList.remove('rec');btn.textContent='🎤';btn.title='Speak ('+lang+')';};
  f.click();}
 function add(el){
  if(el.dataset.voice||el.readOnly||el.disabled)return;
  const id=el.id||'';if(!WANT.test(id)||SKIP.test(id))return;
  if(el.tagName==='INPUT'&&!['text','search',''].includes(el.type))return;
  el.dataset.voice='1';el.classList.add('hasmic');
  let w=el.parentNode;if(!(w.classList&&w.classList.contains('vwrap'))){w=document.createElement('span');w.className='vwrap';el.parentNode.insertBefore(w,el);w.appendChild(el);}
  const l=document.createElement('button');l.type='button';l.className='vlang';l.title='Voice language - tap to change';l.textContent=tag();
  const b=document.createElement('button');b.type='button';b.className='vmic';b.title='Speak ('+lang+')';b.setAttribute('aria-label','Speak');
  b.textContent='🎤';w.appendChild(l);w.appendChild(b);
  l.onclick=e=>{e.preventDefault();const i=LANGS.findIndex(x=>x[0]===lang);lang=LANGS[(i+1)%LANGS.length][0];
   try{localStorage.setItem('voiceLang',lang);}catch(x){}
   document.querySelectorAll('.vlang').forEach(v=>v.textContent=tag());document.querySelectorAll('.vmic').forEach(v=>v.title='Speak ('+lang+')');};
  b.onclick=e=>{e.preventDefault();start(el,b);};}
 function scan(){document.querySelectorAll('textarea[id],input[id]').forEach(add);}
 let t=null;new MutationObserver(()=>{clearTimeout(t);t=setTimeout(scan,120);}).observe(document.body,{childList:true,subtree:true});
 scan();
})();
</script>
"""


# 📋 a copy button on every text box: the whole text goes to the clipboard (also on plain http:// pages)
COPY = r"""
<style>
.vwrap>textarea{padding-bottom:44px!important}
.vcopy{position:absolute;right:18px;bottom:8px;width:34px;height:34px;min-height:34px!important;padding:0!important;display:inline-flex;
 align-items:center;justify-content:center;border-radius:9px!important;border:1px solid var(--line,#ddd);background:var(--card,#fff);
 color:var(--ink,#111);font-size:15px!important;cursor:pointer;z-index:2;opacity:.9;line-height:1}
.vcopy:hover{border-color:var(--acc,#4f46e5);opacity:1}
.vcopy.ok{background:#15803d;border-color:#15803d;color:#fff}.vcopy.bad{background:#dc2626;border-color:#dc2626;color:#fff}
</style>
<script>
(()=>{
 // http:// pages have no navigator.clipboard: give every "Copy" button in the app the old way that still works there
 function oldCopy(text){const h=document.createElement('textarea');h.value=text;h.setAttribute('readonly','');
  h.style.cssText='position:fixed;top:0;left:0;width:1px;height:1px;opacity:0';document.body.appendChild(h);h.select();
  let ok=false;try{ok=document.execCommand('copy');}catch(e){}h.remove();return ok;}
 if(!(navigator.clipboard&&navigator.clipboard.writeText&&window.isSecureContext)){
  try{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:t=>oldCopy(String(t))?Promise.resolve():Promise.reject(new Error('copy blocked'))}});}catch(e){}}
 async function copyText(el){const t=el.value||'';
  if(navigator.clipboard&&window.isSecureContext){try{await navigator.clipboard.writeText(t);return true;}catch(e){}}
  const a=el.selectionStart,b=el.selectionEnd,top=el.scrollTop;let ok=false;           // http:// pages: the old way
  try{el.focus({preventScroll:true});el.select();ok=document.execCommand('copy');}catch(e){}
  try{el.setSelectionRange(a,b);el.scrollTop=top;}catch(e){}
  if(!ok){const h=document.createElement('textarea');h.value=t;h.style.cssText='position:fixed;top:0;left:0;opacity:0';document.body.appendChild(h);
   h.select();try{ok=document.execCommand('copy');}catch(e){}h.remove();}
  return ok;}
 function add(el){if(el.dataset.copy)return;el.dataset.copy='1';
  let w=el.parentNode;if(!(w.classList&&w.classList.contains('vwrap'))){w=document.createElement('span');w.className='vwrap';el.parentNode.insertBefore(w,el);w.appendChild(el);}
  const b=document.createElement('button');b.type='button';b.className='vcopy';b.title='Copy all the text';b.setAttribute('aria-label','Copy');b.textContent='📋';w.appendChild(b);
  b.onclick=async e=>{e.preventDefault();e.stopPropagation();
   if(!el.value){b.textContent='∅';setTimeout(()=>b.textContent='📋',900);return;}
   const ok=await copyText(el);b.textContent=ok?'✓':'✗';b.classList.add(ok?'ok':'bad');b.title=ok?'Copied':'Could not copy - select the text and copy it';
   setTimeout(()=>{b.textContent='📋';b.classList.remove('ok','bad');b.title='Copy all the text';},1500);};}
 function scan(){document.querySelectorAll('textarea').forEach(add);}
 let t=null;new MutationObserver(()=>{clearTimeout(t);t=setTimeout(scan,150);}).observe(document.body,{childList:true,subtree:true});
 scan();
})();
</script>
"""


def inject(html):
    """Add the voice buttons to a page (before </body>)."""
    from .auth import RELOGIN_JS
    i = html.rfind("</body>")
    return html if i < 0 else html[:i] + RELOGIN_JS + VOICE + COPY + html[i:]
