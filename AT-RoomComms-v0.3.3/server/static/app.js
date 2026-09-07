const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];let token=sessionStorage.getItem('rc_token')||'',S={d:null,view:'control',feed:null,rerender:null,unread:0,unreadDM:{},unreadRoom:{},unreadOwnRoom:false,unreadVenue:false,unreadIssues:0},ws=null,wsRetry=0;
const BASE_TITLE=document.title;
function bumpUnread(){S.unread++;renderUnread()}
function clearUnread(){if(!S.unread)return;S.unread=0;renderUnread()}
function renderUnread(){document.title=S.unread?`(${S.unread}) ${BASE_TITLE}`:BASE_TITLE;updateFaviconBadge(!!S.unread)}
function updateFaviconBadge(on){
    const fav=document.querySelector('link[rel="icon"]');if(!fav)return;
    if(!fav.dataset.base)fav.dataset.base=fav.href;
    const base=fav.dataset.base;
    if(!on){fav.href=base;return}
    const img=new Image();
    img.onload=()=>{
        const cv=document.createElement('canvas');cv.width=64;cv.height=64;
        const ctx=cv.getContext('2d');ctx.drawImage(img,0,0,64,64);
        ctx.beginPath();ctx.arc(48,16,14,0,Math.PI*2);ctx.fillStyle='#ff4d6a';ctx.fill();ctx.lineWidth=3;ctx.strokeStyle='#0B0C10';ctx.stroke();
        fav.href=cv.toDataURL('image/png');
    };
    img.src=base;
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)clearUnread()});
window.addEventListener('focus',clearUnread);
async function api(url,opt={}){const h={...(opt.headers||{})};if(!(opt.body instanceof FormData))h['Content-Type']='application/json';if(token)h.Authorization='Bearer '+token;const r=await fetch(url,{...opt,headers:h});const txt=await r.text();let data={};try{data=txt?JSON.parse(txt):{}}catch{data={detail:txt}}if(!r.ok)throw Error(data.detail||txt||`HTTP ${r.status}`);return data}
function esc(v=''){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function showOnly(id){['setup','login','operatorLogin','app'].forEach(x=>$('#'+x).classList.toggle('hidden',x!==id))}function modal(h){$('#modalCard').innerHTML=h;$('#modal').classList.remove('hidden')}function closeModal(){$('#modal').classList.add('hidden');S.threadOpen=null;S.rerender&&S.rerender()}window.closeModal=closeModal;
function showToast(html,onClick){
    let box=$('#toastBox');
    if(!box){box=document.createElement('div');box.id='toastBox';document.body.appendChild(box)}
    const el=document.createElement('div');el.className='toast';el.innerHTML=html;
    if(onClick)el.onclick=()=>{onClick();el.remove()};
    box.appendChild(el);
    setTimeout(()=>el.remove(),15000);
}
window.showToast=showToast;
function flashEmergency(){
    let el=$('#emgFlash');
    if(!el){el=document.createElement('div');el.id='emgFlash';document.body.appendChild(el)}
    el.classList.remove('active');void el.offsetWidth;el.classList.add('active');
    setTimeout(()=>el.classList.remove('active'),2200);
}
window.flashEmergency=flashEmergency;
const EMOJI=['😀','😂','😉','😍','😢','😮','😡','👍','👎','🙏','🎉','🔥','⚠️','✅','❌','❗','❓','👀','🙌','💪','🕒','📢','🎤','🎬','🎧','💡','☕','🔧','🔌','📶','🚨','🆘'];
function toggleEmoji(btn,inputId){
    const existing=$('#emojiPop');
    if(existing){const same=existing.dataset.for===inputId;existing.remove();if(same)return}
    const pop=document.createElement('div');pop.id='emojiPop';pop.className='emojiPop';pop.dataset.for=inputId;
    pop.innerHTML=EMOJI.map(e=>`<span onclick="insertEmoji('${inputId}','${e}')">${e}</span>`).join('');
    document.body.appendChild(pop);
    const r=btn.getBoundingClientRect(),pr=pop.getBoundingClientRect();
    pop.style.left=Math.min(r.left,window.innerWidth-pr.width-10)+'px';
    pop.style.top=(r.top-pr.height-8)+'px';
    setTimeout(()=>document.addEventListener('click',closeEmojiOnce),0);
}
function closeEmojiOnce(e){const pop=$('#emojiPop');if(pop&&!pop.contains(e.target)){pop.remove();document.removeEventListener('click',closeEmojiOnce)}}
function insertEmoji(inputId,e){const el=$('#'+inputId);if(!el)return;const s=el.selectionStart??el.value.length,en=el.selectionEnd??el.value.length;el.value=el.value.slice(0,s)+e+el.value.slice(en);el.focus();el.selectionStart=el.selectionEnd=s+e.length;$('#emojiPop')?.remove()}
window.toggleEmoji=toggleEmoji;window.insertEmoji=insertEmoji;
function attachBtn(fileId){return `<input type="file" id="${fileId}" hidden><button type="button" class="btn secondary" title="Attach file" onclick="$('#${fileId}').click()">＋</button>`}
function emojiBtn(inputId){return `<button type="button" class="btn secondary" title="Emoji" onclick="toggleEmoji(this,'${inputId}')">🙂</button>`}
async function uploadIfAttached(fileId,mid){const f=$('#'+fileId)?.files[0];if(!f)return null;$('#'+fileId).value='';const fd=new FormData();fd.append('file',f);return api(`/api/messages/${mid}/attachments`,{method:'POST',body:fd})}
$('#toOperatorLogin').onclick=async e=>{e.preventDefault();$('#opLoginError').textContent='';try{const o=await fetch('/api/operator/login-options').then(r=>r.json());$('#opName').innerHTML=o.operators.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('')||'<option value="">No operators set up yet</option>';S.opOptions=o;const fillRooms=()=>{const ev=o.events.find(x=>String(x.id)===$('#opEvent').value);$('#opRoom').innerHTML=(ev?.rooms||[]).map(r=>`<option value="${r.id}">${esc(r.short_name||r.name)}</option>`).join('')||'<option value="">No rooms on this event</option>'};$('#opEvent').innerHTML=o.events.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('')||'<option value="">No active events</option>';$('#opEvent').onchange=fillRooms;fillRooms();showOnly('operatorLogin')}catch(err){showOnly('operatorLogin');$('#opLoginError').textContent=err.message}};
$('#toControlLogin').onclick=e=>{e.preventDefault();showOnly('login')};
const THEME_ICONS={blue:'/static/brand/icon-blue.svg',purple:'/static/brand/icon-purple.svg',green:'/static/brand/icon-green.svg',orange:'/static/brand/icon-orange.svg'};
function applyTheme(theme){
    const t=THEME_ICONS[theme]?theme:'blue';
    document.documentElement.dataset.theme=t;
    const href=THEME_ICONS[t];
    $$('.brandIcon').forEach(img=>img.src=href);
    const fav=document.querySelector('link[rel="icon"]');if(fav){fav.href=href;fav.dataset.base=href}
}
const CLIENT_PARAMS=new URLSearchParams(location.search);
const IS_WINDOWS_CLIENT=CLIENT_PARAMS.get('client')==='windows'&&!!window.chrome?.webview;
function notifyNative(title,body,priority){
    if(!IS_WINDOWS_CLIENT)return;
    if(S.d?.me?.kind==='operator'&&S.d.me.device_role==='main')return;
    try{window.chrome.webview.postMessage({type:'notification',title,body,priority})}catch{}
}
let CLIENT_TELEMETRY=null;
function deviceRoomFields(){
    return S.d?.me?.kind==='operator'?{room_id:S.d.me.room_id,event_id:S.d.me.event_id,operator:S.d.me.display_name}:{};
}
function registerWindowsDevice(){
    const device=CLIENT_PARAMS.get('device');
    if(!device)return;
    if(IS_WINDOWS_CLIENT){
        window.chrome.webview.addEventListener('message',e=>{
            const d=e.data;
            if(d&&d.type==='telemetry')CLIENT_TELEMETRY={presenting:!!d.presenting,uptime_seconds:d.uptimeSeconds|0,diagnostics:d.diagnostics||null};
        });
    }
    const register=()=>fetch('/api/devices/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:device,role:IS_WINDOWS_CLIENT?'windows-client':'general',app_version:CLIENT_PARAMS.get('clientVersion')||'',...deviceRoomFields()})}).catch(()=>{});
    register();
    S.sendDeviceHeartbeat=()=>fetch('/api/devices/heartbeat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:device,...(CLIENT_TELEMETRY||{}),...deviceRoomFields()})}).catch(()=>{});
    setInterval(S.sendDeviceHeartbeat,60000);
}
async function start(){registerWindowsDevice();try{const s=await fetch('/api/setup/status',{cache:'no-store'}).then(r=>r.json());applyTheme(s.theme);if(s.needs_setup){token='';sessionStorage.removeItem('rc_token');showOnly('setup');return}if(token){await load();return}showOnly('login')}catch(e){showOnly('login')}}
$('#setupForm').addEventListener('submit',async e=>{e.preventDefault();$('#setupError').textContent='';const ap=$('#setupAdminPass').value,sp=$('#setupSpeakerPass').value;if(ap!==$('#setupAdminConfirm').value)return $('#setupError').textContent='Administrator passwords do not match.';if(sp!==$('#setupSpeakerConfirm').value)return $('#setupError').textContent='Speaker Preview passwords do not match.';try{const r=await api('/api/setup/complete',{method:'POST',body:JSON.stringify({venue_name:$('#setupVenue').value,control_centre_name:$('#setupControl').value,admin_display_name:$('#setupAdminName').value,admin_username:$('#setupAdminUser').value,admin_password:ap,speaker_display_name:$('#setupSpeakerName').value,speaker_username:$('#setupSpeakerUser').value,speaker_password:sp})});token=r.token;sessionStorage.setItem('rc_token',token);await load()}catch(err){$('#setupError').textContent=err.message}});
$('#loginForm').addEventListener('submit',async e=>{e.preventDefault();$('#loginError').textContent='';try{const r=await api('/api/auth/login',{method:'POST',body:JSON.stringify({username:$('#loginUser').value.trim(),password:$('#loginPass').value})});token=r.token;sessionStorage.setItem('rc_token',token);await load()}catch(err){$('#loginError').textContent=err.message}});
$('#opLoginForm').addEventListener('submit',async e=>{e.preventDefault();$('#opLoginError').textContent='';const opId=$('#opName').value,evId=$('#opEvent').value,rmId=$('#opRoom').value;if(!opId||!evId||!rmId)return $('#opLoginError').textContent='Please choose your name, event and room.';try{const r=await api('/api/operator/login',{method:'POST',body:JSON.stringify({operator_id:Number(opId),event_id:Number(evId),room_id:Number(rmId),device_role:$('#opRole').value,device_name:''})});token=r.token;sessionStorage.setItem('rc_token',token);await load()}catch(err){$('#opLoginError').textContent=err.message}});
async function load(){try{
    S.d=await api('/api/bootstrap');showOnly('app');
    const wantSpeaker=CLIENT_PARAMS.get('speaker')==='1';
    if(S.d.me.kind==='operator'){wantSpeaker?speakerPreview():await renderOperatorApp()}
    else{renderChrome();wantSpeaker?speakerPreview():control()}
    wsConnect();S.sendDeviceHeartbeat?.();return true
}catch(e){console.error(e);showOnly('login');const box=$('#loginError');if(box)box.textContent='RoomComms could not load: '+e.message;return false}}
function speakerPreview(){
    S.view='speaker';S.feed=null;S.rerender=speakerPreview;
    const isOp=S.d.me.kind==='operator';
    if(isOp){
        $('#app').classList.add('operatorMode');
        $$('.nav[data-view]').forEach(b=>b.style.display='none');
        $('.stats').style.display='none';
        $('#eventNav').innerHTML='';
        $('#venue').textContent=S.d.settings?.venue_name||'Venue';
        $('#userBox').innerHTML=`<b>${esc(S.d.me.display_name)}</b>`;
    }
    title('Speaker Preview','');
    $('#content').innerHTML='<div class="card body">Loading…</div>';
    api('/api/speaker-preview').then(d=>{
        if(S.view!=='speaker')return;
        const backBtn=isOp?`<div class="toolbar"><button class="btn secondary" onclick="renderOperatorApp()">← Back to room</button></div>`:'';
        const cards=d.events.map(e=>{
            const rooms=d.rooms.filter(r=>r.event_id===e.id);
            return `<div class="card"><div class="cardHead"><h2><span class="dot" style="background:${e.event_color}"></span>${esc(e.name)}</h2><small>${esc(e.event_status)}</small></div>${rooms.map(r=>`<div class="roomRow"><span class="dot ${r.current_status}"></span><b>${esc(r.name)}</b><span class="operator">${r.operator_name?`👤 ${esc(r.operator_name)}`:'Unassigned'}</span><span class="badge">${statusLabel(r.current_status)}</span></div>`).join('')||'<div class="body">No rooms in this event.</div>'}</div>`;
        }).join('');
        $('#content').innerHTML=`${backBtn}<div class="grid2">${cards||'<div class="card body">No active events.</div>'}</div>`;
    }).catch(()=>{$('#content').innerHTML='<div class="card body">Could not load preview.</div>'});
}
window.speakerPreview=speakerPreview;
async function refresh(){S.d=await api('/api/bootstrap');if(S.d.me.kind==='operator')await renderOperatorApp();else renderChrome()}
async function signOut(){try{await api(S.d?.me?.kind==='operator'?'/api/operator/logout':'/api/auth/logout',{method:'POST'})}catch{}wsClose();token='';sessionStorage.removeItem('rc_token');S.d=null;showOnly('login')}$('#logoutBtn').onclick=signOut;
function wsStatus(state){const dot=$('#wsDot'),label=$('#wsLabel');if(!dot)return;dot.className='wsDot '+state;label.textContent={live:'Live',connecting:'Connecting…',offline:'Reconnecting…'}[state]||''}
function wsConnect(){if(!token)return;wsClose(true);wsStatus('connecting');const proto=location.protocol==='https:'?'wss:':'ws:';ws=new WebSocket(`${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`);ws.onmessage=e=>{try{wsHandle(JSON.parse(e.data))}catch{}};ws.onclose=()=>{ws=null;wsStatus('offline');if(token){wsRetry=Math.min(wsRetry+1,6);setTimeout(wsConnect,wsRetry*1000)}};ws.onopen=()=>{wsRetry=0;wsStatus('live')}}
function wsClose(keep){if(ws){const s=ws;ws=null;s.onclose=null;s.close()}if(!keep)wsRetry=0}
function wsHandle(msg){
    if(msg.type==='force_logout'){signOut();return}
    if(msg.type==='dm_new'){
        const m=msg.message,mine=m.sender_kind===S.d.me.kind&&m.sender_id===S.d.me.id;
        const other=mine?{kind:m.to_kind,id:m.to_id}:{kind:m.sender_kind,id:m.sender_id};
        const open=S.dmWith&&S.dmWith.kind===other.kind&&S.dmWith.id===other.id;
        if(open)feedAppend(m);
        if(!mine&&!open){
            S.unreadDM[other.kind+':'+other.id]=true;
            updateDMBadge();
            if(S.view==='dm')loadDMContacts();
            notifyNative(`Message from ${m.sender}`,m.body,'normal');
        }
        if(!mine&&(!open||document.hidden))bumpUnread();
        return;
    }
    if(msg.type==='help_new'||msg.type==='help_updated'){
        upsertHelpRequest(msg.request);
        if(msg.type==='help_new'&&msg.request.scope!=='room'&&msg.request.room_id!==S.d.me.room_id){
            const tag=msg.request.scope==='venue'?'📢 Venue-wide':'📣 Event-wide';
            showToast(`${tag} — <b>${esc(msg.request.room_name||'A room')}</b> needs help — ${esc(msg.request.category)}: ${esc(msg.request.description)}`,()=>openHelpThread(msg.request.id));
            bumpUnread();
            notifyNative(`${tag} help needed`,`${msg.request.room_name||'A room'} — ${msg.request.category}: ${msg.request.description}`,'important');
        }
        return;
    }
    if(msg.type==='emergency_alert'){
        if(msg.sender_kind===S.d.me.kind&&msg.sender_id===S.d.me.id)return;
        flashEmergency();
        bumpUnread();
        const canOpen=S.d.me.kind==='account';
        const r=canOpen?S.d.rooms.find(x=>x.id===msg.room_id):null;
        showToast(`🚨 <b>EMERGENCY</b> — ${esc(msg.room_name||'Room')}${msg.event_name?` (${esc(msg.event_name)})`:''}: ${esc(msg.body)}`,r?()=>openRoom(r.event_id,r.id):null);
        notifyNative('🚨 EMERGENCY',`${msg.room_name||'Room'}${msg.event_name?` (${msg.event_name})`:''}: ${msg.body}`,'emergency');
        return;
    }
    if(msg.type==='room_updated'){
        if(S.d.rooms){
            const i=S.d.rooms.findIndex(r=>r.id===msg.room.id);
            if(i>-1)S.d.rooms[i]=msg.room;else S.d.rooms.push(msg.room);
            renderChrome();
            S.rerender&&S.rerender();
        }
        return;
    }
    if(msg.type==='device_updated'){
        if(S.d.devices){
            const i=S.d.devices.findIndex(d=>d.name===msg.device.name);
            if(i>-1)S.d.devices[i]=msg.device;else S.d.devices.push(msg.device);
            if(S.view==='devices')devicesPage();
        }
        return;
    }
    if(msg.type==='presence_updated'){
        if(S.d.presence){S.d.presence[msg.room_id]={main:msg.main,backup:msg.backup};if(['control','event','room','venue'].includes(S.view))S.rerender&&S.rerender();renderChrome()}
        return;
    }
    if(msg.type==='issue_new'||msg.type==='issue_updated'){
        if(msg.type==='issue_new'){S.unreadIssues++;updateIssuesBadge();showToast(`🐞 New issue reported by <b>${esc(msg.issue.reporter_name)}</b> — ${esc(msg.issue.category)}: ${esc(msg.issue.description)}`,()=>issuesPage());bumpUnread();notifyNative('🐞 New issue reported',`${msg.issue.reporter_name} — ${msg.issue.category}: ${msg.issue.description}`,'normal')}
        if(S.view==='issues')issuesPage();
        return;
    }
    const mineMsg=m=>m.sender_kind===S.d.me.kind&&m.sender_id===S.d.me.id;
    if((msg.type==='message_new'||msg.type==='message_updated')&&S.threadOpen&&S.threadOpen.scope===msg.message.scope&&S.threadOpen.id===msg.message.scope_id){
        refreshThread(msg.message.scope,msg.message.scope_id);
        if(document.hidden&&msg.type==='message_new'&&!mineMsg(msg.message))bumpUnread();
        return;
    }
    if(msg.type==='message_new'&&!mineMsg(msg.message)&&(msg.message.scope==='room'||msg.message.scope==='venue')){
        const openHere=S.feed&&S.feed.scope===msg.message.scope&&(msg.message.scope==='venue'||S.feed.scope_id===msg.message.scope_id);
        if(!openHere){
            if(msg.message.scope==='venue'){S.unreadVenue=true;updateVenueBadge()}
            else if(S.d.me.kind==='operator'&&msg.message.scope_id===S.d.me.room_id){S.unreadOwnRoom=true;updateRoomBadge()}
            else if(S.d.rooms){S.unreadRoom[msg.message.scope_id]=true;renderChrome()}
        }
        if(msg.message.scope==='venue')notifyNative('Venue message',`${msg.message.sender}: ${msg.message.body}`,msg.message.priority);
        else if(S.d.me.kind==='operator'&&msg.message.scope_id===S.d.me.room_id)notifyNative(`${msg.message.sender} — Your room`,msg.message.body,msg.message.priority);
        if(!openHere||document.hidden)bumpUnread();
    }
    if(!S.feed)return;
    const inFeed=(m)=>m.scope===S.feed.scope&&(S.feed.scope==='venue'||m.scope_id===S.feed.scope_id);
    if(msg.type==='message_new'&&inFeed(msg.message)){
        feedAppend(msg.message);
        if(document.hidden&&!mineMsg(msg.message)&&msg.message.scope==='event')bumpUnread();
    }
    else if(msg.type==='message_updated'&&inFeed(msg.message))feedReplace(msg.message);
    else if(msg.type==='message_deleted'&&msg.scope===S.feed.scope&&(S.feed.scope==='venue'||msg.scope_id===S.feed.scope_id))feedRemove(msg.id);
}
function roomsFor(eid){return S.d.rooms.filter(r=>r.event_id===eid)}function statusLabel(s){return({closed:'Closed',setting_up:'Setting Up',ready:'Ready',rehearsal:'Rehearsal',live:'Live',technical_issue:'Technical Issue',help_requested:'Help Requested'}[s]||s)}
function renderChrome(){const d=S.d;applyTheme(d.settings.ui_theme);$('#app').classList.remove('operatorMode');$$('.nav[data-view]').forEach(b=>{b.style.display=b.dataset.view==='room'?'none':'';b.classList.toggle('active',b.dataset.view===S.view)});$('.stats').style.display='';$('#venue').textContent=d.settings.venue_name||'Venue';$('#se').textContent=d.events.length;$('#sr').textContent=d.rooms.length;$('#so').textContent=d.operators.length;$('#userBox').innerHTML=`<b>${esc(d.me.display_name)}</b><br>${d.me.role==='admin'?'Administrator':'Speaker Preview'}`;$$('.adminOnly').forEach(x=>x.classList.toggle('hidden',d.me.role!=='admin'));$('#eventNav').innerHTML=d.events.map(e=>`<div class="eventGroup"><div class="eventName ${S.view==='event'&&S.currentEventId===e.id?'active':''}" onclick="openEvent(${e.id})">${esc(e.name)}</div>${roomsFor(e.id).map(r=>`<div class="roomNav ${S.view==='room'&&S.feed?.scope==='room'&&S.feed.scope_id===r.id?'active':''}" onclick="openRoom(${e.id},${r.id})"><span class="dot ${r.current_status}"></span>${esc(r.short_name||r.name)}${r.operator_name?` · ${esc(r.operator_name)}`:''}${presenceDot(r.id)}${roomUnreadBadge(r.id)}</div>`).join('')}</div>`).join('');updateHelpBadge();updateDMBadge();updateVenueBadge();updateIssuesBadge()}
async function renderOperatorApp(){
    const d=S.d;
    applyTheme(d.settings.ui_theme);
    $('#app').classList.add('operatorMode');
    $$('.nav[data-view]').forEach(b=>b.style.display=['dm','help','room','issues'].includes(b.dataset.view)?'':'none');
    $('.stats').style.display='none';
    $('#venue').textContent=d.settings.venue_name||'Venue';
    $('#eventNav').innerHTML='';
    $('#userBox').innerHTML=`<b>${esc(d.me.display_name)}</b><br>${d.me.device_role==='main'?'Main PC':'Backup PC'}${d.me.device_role==='main'?' · notifications off':''}`;
    title(d.room?.name||'Room',d.event?.name||'');
    S.view='operatorRoom';S.feed={scope:'room',scope_id:d.room?.id};
    S.unreadOwnRoom=false;updateRoomBadge();
    $$('.nav[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view==='room'));
    const ms=d.room?await api(`/api/messages?scope=room&scope_id=${d.room.id}`):[];
    $('#content').innerHTML=`<div id="opHelpBanner"></div><div class="card feedCard"><div class="cardHead"><div><h2>Operations Feed</h2><small>${esc(d.event?.name||'')} · ${statusLabel(d.room?.current_status||'closed')}</small></div><div class="headActions"><button class="btn danger" onclick="emergencyAlert(${d.event?.id||0},${d.room?.id||0})">🚨 Emergency</button><button class="btn danger" onclick="helpRequest(${d.event?.id||0},${d.room?.id||0})">Request Help</button></div></div><div class="feed" id="feedList">${ms.map(messageHtml).join('')||'<div class="body feedEmpty">No messages yet.</div>'}</div><div class="composer"><div style="display:flex;gap:6px">${attachBtn('file')}${emojiBtn('msgText')}</div><input class="inlineInput" id="msgText" placeholder="Type an operational message" onkeydown="if(event.key==='Enter'){event.preventDefault();sendOperatorRoom()}"><select id="msgPri" class="statusSelect priSelect"><option>normal</option><option>important</option><option>urgent</option><option>emergency</option></select><button class="btn" onclick="sendOperatorRoom()">Send</button></div></div>`;
    renderOpHelpBanner();
    updateHelpBadge();updateDMBadge();updateIssuesBadge();
    scrollFeedBottom();
}
window.renderOperatorApp=renderOperatorApp;
function renderOpHelpBanner(){
    const el=$('#opHelpBanner');if(!el)return;
    const active=(S.d.help_requests||[])[0];
    el.innerHTML=active?`<div class="card body helpBanner ${active.status==='new'?'new':''}"><b>Help requested</b> · ${esc(active.category)} <span class="badge">${esc(active.status)}</span><br><small>${esc(active.description)}</small><div style="margin-top:8px"><button class="btn small secondary" onclick="openHelpThread(${active.id})">Reply</button></div></div>`:'';
}
function updateHelpBadge(){
    const el=$('#helpBadge');if(!el)return;
    const n=(S.d.help_requests||[]).filter(h=>h.status==='new').length;
    el.textContent=n;el.classList.toggle('hidden',n===0);
}
function updateDMBadge(){
    const el=$('#dmBadge');if(!el)return;
    const n=Object.keys(S.unreadDM||{}).length;
    el.textContent=n;el.classList.toggle('hidden',n===0);
}
function updateRoomBadge(){
    const el=$('#roomBadge');if(!el)return;
    el.textContent='•';el.classList.toggle('hidden',!S.unreadOwnRoom);
}
function updateVenueBadge(){
    const el=$('#venueBadge');if(!el)return;
    el.textContent='•';el.classList.toggle('hidden',!S.unreadVenue);
}
function updateIssuesBadge(){
    const el=$('#issuesBadge');if(!el)return;
    el.textContent=S.unreadIssues;el.classList.toggle('hidden',S.unreadIssues===0);
}
function presenceDot(roomId){
    const p=(S.d.presence||{})[roomId]||{main:false,backup:false};
    const cls=p.main&&p.backup?'online-full':(p.main||p.backup)?'online-partial':'offline';
    const title=p.main&&p.backup?'Main + Backup online':p.main?'Main online':p.backup?'Backup online':'Offline';
    return `<span class="presenceDot ${cls}" title="${title}"></span>`;
}
function roomUnreadBadge(roomId){return S.unreadRoom[roomId]?'<span class="navBadge">•</span>':''}
function upsertHelpRequest(hr){
    if(!S.d.help_requests)S.d.help_requests=[];
    if(S.d.me.kind==='operator'&&hr.room_id!==S.d.me.room_id)return;
    const i=S.d.help_requests.findIndex(h=>h.id===hr.id);
    const closed=hr.status==='resolved'||hr.status==='cancelled';
    if(closed){if(i>-1)S.d.help_requests.splice(i,1)}
    else if(i>-1)S.d.help_requests[i]=hr;
    else S.d.help_requests.unshift(hr);
    updateHelpBadge();
    if(S.view==='help')helpPage();
    if(S.view==='operatorRoom')renderOpHelpBanner();
}
async function sendOperatorRoom(){const rid=S.d.room?.id;if(!rid)return;const f=$('#file').files[0],input=$('#msgText'),body=input.value.trim()||(f?'Attachment':'');if(!body)return;input.value='';const m=await api('/api/messages',{method:'POST',body:JSON.stringify({scope:'room',scope_id:rid,body,priority:$('#msgPri').value})});feedAppend(m);if(f){$('#file').value='';const fd=new FormData();fd.append('file',f);const updated=await api(`/api/messages/${m.id}/attachments`,{method:'POST',body:fd});feedReplace(updated)}}window.sendOperatorRoom=sendOperatorRoom;
function title(t,s=''){$('#title').textContent=t;$('#sub').textContent=s;if(S.d?.me?.kind==='account')renderChrome()}
function control(){S.view='control';S.feed=null;S.rerender=control;title(S.d.settings.control_centre_name||'Control Centre',`${S.d.settings.venue_name} · ${new Date().toLocaleString()}`);const cards=S.d.events.map(e=>`<div class="card"><div class="cardHead"><div><h2><span class="dot" style="background:${e.event_color}"></span>${esc(e.name)}</h2><small>${esc(e.client)} · ${esc(e.event_status)}</small></div><div><button class="btn small secondary" onclick="openEvent(${e.id})">Open</button> <button class="btn small" onclick="editEvent(${e.id})">Edit</button></div></div>${roomsFor(e.id).map(r=>`<div class="roomRow" onclick="openRoom(${e.id},${r.id})"><span class="dot ${r.current_status}"></span><b>${esc(r.name)}</b>${presenceDot(r.id)}${roomUnreadBadge(r.id)}<span class="operator">${r.operator_name?`👤 ${esc(r.operator_name)}`:'Unassigned'}</span><span class="badge">${statusLabel(r.current_status)}</span></div>`).join('')||'<div class="body">No rooms assigned.</div>'}</div>`).join('');$('#content').innerHTML=`<div class="toolbar"><button class="btn" onclick="newEvent()">+ New Event</button></div><div class="grid2">${cards||'<div class="card body">No active events. Create one to begin.</div>'}</div>`}window.control=control;
function openEvent(id){const e=S.d.events.find(x=>x.id===id);if(!e)return;S.view='event';S.feed=null;S.currentEventId=id;S.rerender=()=>openEvent(id);renderChrome();title(e.name,`${e.client} · ${e.event_status}`);$('#content').innerHTML=`<div class="toolbar"><button class="btn" onclick="editEvent(${id})">Edit Event & Rooms</button><button class="btn secondary" onclick="eventFeed(${id})">Operations Feed</button></div><div class="card"><div class="cardHead"><div><h2>${esc(e.name)}</h2><small>${esc(e.starts_at)} → ${esc(e.ends_at)}</small></div></div>${roomsFor(id).map(r=>`<div class="roomRow"><span class="dot ${r.current_status}"></span><b onclick="openRoom(${id},${r.id})">${esc(r.name)}</b>${presenceDot(r.id)}${roomUnreadBadge(r.id)}<span class="operator">${r.operator_name?`👤 ${esc(r.operator_name)}`:'No operator'}</span><button class="btn small secondary" onclick="editRoom(${r.id}, () => openEvent(${id}))">Edit</button></div>`).join('')||'<div class="body">No rooms in this event yet.</div>'}</div>`}window.openEvent=openEvent;
async function openRoom(eid,rid){const r=S.d.rooms.find(x=>x.id===rid),e=S.d.events.find(x=>x.id===eid);if(!r)return;S.view='room';S.rerender=()=>openRoom(eid,rid);title(r.name,e?.name||'Room');S.feed={scope:'room',scope_id:rid};delete S.unreadRoom[rid];renderChrome();const ms=await api(`/api/messages?scope=room&scope_id=${rid}`);$('#content').innerHTML=`<div class="grid2"><div class="card feedCard"><div class="cardHead"><div><h2>Operations Feed</h2><small>${esc(r.operator_name||'No operator assigned')}</small></div><div class="headActions"><button class="btn danger" onclick="emergencyAlert(${eid},${rid})">🚨 Emergency</button><button class="btn danger" onclick="helpRequest(${eid},${rid})">Request Help</button></div></div><div class="feed" id="feedList">${ms.map(messageHtml).join('')||'<div class="body feedEmpty">No messages yet.</div>'}</div><div class="composer"><div style="display:flex;gap:6px">${attachBtn('file')}${emojiBtn('msgText')}</div><input class="inlineInput" id="msgText" placeholder="Type an operational message" onkeydown="if(event.key==='Enter'){event.preventDefault();sendRoom(${eid},${rid})}"><select id="msgPri" class="statusSelect priSelect"><option>normal</option><option>important</option><option>urgent</option><option>emergency</option></select><button class="btn" onclick="sendRoom(${eid},${rid})">Send</button></div></div><div class="card body"><h3>Room Information</h3><p><b>Assigned operator:</b> ${esc(r.operator_name||'Unassigned')} ${presenceDot(r.id)}</p>${(S.d.devices||[]).filter(d=>d.room_id===r.id).map(d=>`<p><b>🖥️ ${esc(d.name)}</b> <small>${esc(d.role||'')}${d.presenting?' · Presenting':''} · ${fmtAgo(d.last_heartbeat)}</small></p>`).join('')}<label>Status<select id="roomStatus" class="statusSelect" onchange="changeStatus(${rid},this.value)">${['closed','setting_up','ready','rehearsal','live','technical_issue'].map(s=>`<option value="${s}" ${r.current_status===s?'selected':''}>${statusLabel(s)}</option>`).join('')}</select></label><p><button class="btn" onclick="editRoom(${rid}, () => openRoom(${eid},${rid}))">Edit Room</button></p></div></div>`;scrollFeedBottom()}window.openRoom=openRoom;
function priLabel(p){return({normal:'Normal',important:'Important',urgent:'Urgent',emergency:'Emergency'}[p]||p)}
function messageHtml(m){
    const mine=S.d.me.id&&m.sender_kind===S.d.me.kind&&m.sender_id===S.d.me.id,canModify=mine||(S.d.me.kind==='account'&&S.d.me.role==='admin');
    const canReplyPrivately=m.scope==='room'&&m.priority==='emergency'&&(S.d.me.kind==='account'||mine);
    const atts=(m.attachments||[]).map(a=>{
        const img=/^image\//.test(a.mime_type||'');
        return img?`<a class="attachment attachmentImg" href="/api/attachments/${a.id}" target="_blank"><img src="/api/attachments/${a.id}" alt="${esc(a.original_name)}" loading="lazy"></a>`
                  :`<a class="attachment" href="/api/attachments/${a.id}" target="_blank">📎 ${esc(a.original_name)}</a>`
    }).join('');
    const helpAction=m.help_request_id?`<div class="helpAction"><button class="btn small danger" onclick="openHelpThread(${m.help_request_id})">${m.body.startsWith('📢')?'View all-call':'View request'} ▸</button></div>`:'';
    return `<div class="msgRow ${mine?'own':'other'} pri-${esc(m.priority)}" data-mid="${m.id}">
<div class="bubble">
<div class="bubbleHead"><b>${esc(m.sender)}</b><span class="pill pri-${esc(m.priority)}">${priLabel(m.priority)}</span></div>
<div class="bubbleBody" id="msgBody-${m.id}">${esc(m.body)}</div>
${atts}
${helpAction}
<div class="bubbleFoot"><small>${new Date(m.created_at).toLocaleString()}${m.edited_at?' · edited':''}</small><span class="msgActions">${canReplyPrivately?`<button class="linkBtn" onclick="openEmergencyThread(${m.id})">Reply privately ▸</button>`:''}${canModify?`<button class="linkBtn" onclick="editMessage(${m.id})">Edit</button><button class="linkBtn danger" onclick="deleteMessage(${m.id})">Delete</button>`:''}</span></div>
</div></div>`}
function feedContainer(){return $('#feedList')}
function feedIsAtBottom(el){return el.scrollHeight-el.scrollTop-el.clientHeight<80}
function scrollFeedBottom(){const el=feedContainer();if(el)el.scrollTop=el.scrollHeight}
function feedAppend(m){const el=feedContainer();if(!el||el.querySelector(`[data-mid="${m.id}"]`))return;const wasBottom=feedIsAtBottom(el);el.querySelector('.feedEmpty')?.remove();el.insertAdjacentHTML('beforeend',messageHtml(m));if(wasBottom)scrollFeedBottom()}
function feedReplace(m){const el=feedContainer();if(!el)return;const row=el.querySelector(`[data-mid="${m.id}"]`);if(row)row.outerHTML=messageHtml(m);else feedAppend(m)}
function feedRemove(mid){const el=feedContainer();if(!el)return;el.querySelector(`[data-mid="${mid}"]`)?.remove();if(!el.children.length)el.innerHTML='<div class="body feedEmpty">No messages yet.</div>'}
async function editMessage(mid){const el=$(`#msgBody-${mid}`);if(!el)return;const current=el.textContent;const next=prompt('Edit message:',current);if(next===null||next.trim()===''||next.trim()===current)return;const m=await api(`/api/messages/${mid}`,{method:'PATCH',body:JSON.stringify({body:next.trim()})});feedReplace(m)}window.editMessage=editMessage;
async function deleteMessage(mid){if(!confirm('Delete this message?'))return;await api(`/api/messages/${mid}`,{method:'DELETE'});feedRemove(mid)}window.deleteMessage=deleteMessage;

function openThread(scope,scopeId,heading,notice,placeholder){
    S.threadOpen={scope,id:scopeId};
    modal(`<h2>${esc(heading)}</h2>${notice?`<p class="notice">${esc(notice)}</p>`:''}<div class="feed" id="threadFeed" style="max-height:340px"></div><div class="composer" style="grid-template-columns:auto 1fr auto"><div style="display:flex;gap:6px">${attachBtn('threadFile')}${emojiBtn('threadMsg')}</div><input class="inlineInput" id="threadMsg" placeholder="${esc(placeholder||'Reply')}" onkeydown="if(event.key==='Enter'){event.preventDefault();sendThreadReply('${scope}',${scopeId})}"><button class="btn" onclick="sendThreadReply('${scope}',${scopeId})">Send</button></div>`);
    refreshThread(scope,scopeId);
}
window.openThread=openThread;
async function refreshThread(scope,scopeId){
    try{
        const ms=await api(`/api/messages?scope=${scope}&scope_id=${scopeId}`);
        const el=$('#threadFeed');if(!el)return;
        el.innerHTML=ms.map(messageHtml).join('')||'<div class="body feedEmpty">No replies yet.</div>';
        el.scrollTop=el.scrollHeight;
    }catch(err){const el=$('#threadFeed');if(el)el.innerHTML=`<div class="body">${esc(err.message)}</div>`}
}
async function sendThreadReply(scope,scopeId){const input=$('#threadMsg');if(!input)return;const f=$('#threadFile')?.files[0],v=input.value.trim()||(f?'Attachment':'');if(!v)return;input.value='';const m=await api('/api/messages',{method:'POST',body:JSON.stringify({scope,scope_id:scopeId,body:v,priority:'normal'})});await uploadIfAttached('threadFile',m.id);await refreshThread(scope,scopeId)}
window.sendThreadReply=sendThreadReply;
function openEmergencyThread(mid){openThread('emergency_thread',mid,'Private reply','Only Control Centre and the person who raised this will see this thread — not the rest of the room.','Reply privately')}
window.openEmergencyThread=openEmergencyThread;
function openHelpThread(hid){openThread('help_thread',hid,'Help Request',null,'Reply')}
window.openHelpThread=openHelpThread;

function dmPage(){const isOp=S.d.me.kind==='operator';S.view='dm';S.feed=null;S.dmWith=null;title('Direct Messages','Person to person');$('#content').innerHTML=`${isOp?'<div class="toolbar" style="justify-content:flex-start"><button class="btn secondary" onclick="renderOperatorApp()">← Back to room</button></div>':''}<div class="grid2"><div class="card" id="dmContacts"><div class="cardHead"><h2>People</h2></div><div class="body">Loading…</div></div><div class="card feedCard" id="dmThreadCard" style="display:none"><div class="cardHead"><h2 id="dmWithName"></h2></div><div class="feed" id="feedList"></div><div class="composer" style="grid-template-columns:auto 1fr auto"><div style="display:flex;gap:6px">${attachBtn('dmFile')}${emojiBtn('dmMsg')}</div><input class="inlineInput" id="dmMsg" placeholder="Message" onkeydown="if(event.key==='Enter'){event.preventDefault();sendDM()}"><button class="btn" onclick="sendDM()">Send</button></div></div></div>`;loadDMContacts()}
window.dmPage=dmPage;
function jsStr(s){return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'")}
async function loadDMContacts(){const list=await api('/api/dm/contacts');const el=$('#dmContacts');if(!el)return;el.innerHTML=`<div class="cardHead"><h2>People</h2></div>`+(list.map(p=>`<div class="listRow" style="cursor:pointer" onclick="openDM('${p.kind}',${p.id},'${esc(jsStr(p.display_name))}')"><b>${esc(p.display_name)}</b>${S.unreadDM[p.kind+':'+p.id]?'<span class="navBadge">•</span>':''}<small>${p.kind==='operator'?'Operator':'Control Centre'}</small></div>`).join('')||'<div class="body">Nobody to message yet.</div>')}
async function openDM(kind,id,name){S.dmWith={kind,id};delete S.unreadDM[kind+':'+id];updateDMBadge();$('#dmThreadCard').style.display='';$('#dmWithName').textContent=name;const ms=await api(`/api/dm?with_kind=${kind}&with_id=${id}`);$('#feedList').innerHTML=ms.map(messageHtml).join('')||'<div class="body feedEmpty">No messages yet.</div>';scrollFeedBottom();loadDMContacts()}
window.openDM=openDM;
async function sendDM(){if(!S.dmWith)return;const input=$('#dmMsg'),f=$('#dmFile')?.files[0],v=input.value.trim()||(f?'Attachment':'');if(!v)return;input.value='';const m=await api('/api/dm',{method:'POST',body:JSON.stringify({to_kind:S.dmWith.kind,to_id:S.dmWith.id,body:v})});feedAppend(m);const updated=await uploadIfAttached('dmFile',m.id);if(updated)feedReplace(updated)}
window.sendDM=sendDM;
async function sendRoom(eid,rid){const f=$('#file').files[0],input=$('#msgText'),body=input.value.trim()||(f?'Attachment':'');if(!body)return;input.value='';const m=await api('/api/messages',{method:'POST',body:JSON.stringify({scope:'room',scope_id:rid,sender:S.d.me.display_name,body,priority:$('#msgPri').value})});feedAppend(m);if(f){$('#file').value='';const fd=new FormData();fd.append('file',f);const updated=await api(`/api/messages/${m.id}/attachments`,{method:'POST',body:fd});feedReplace(updated)}}window.sendRoom=sendRoom;
async function changeStatus(rid,status){await api(`/api/rooms/${rid}/status`,{method:'PATCH',body:JSON.stringify({status})});await refresh()}window.changeStatus=changeStatus;
async function eventFeed(eid){const e=S.d.events.find(x=>x.id===eid);S.view='eventFeed';S.feed={scope:'event',scope_id:eid};S.rerender=()=>eventFeed(eid);const ms=await api(`/api/messages?scope=event&scope_id=${eid}`);title(e.name,'Event Operations Feed');$('#content').innerHTML=`<div class="card feedCard"><div class="feed" id="feedList">${ms.map(messageHtml).join('')||'<div class="body feedEmpty">No messages yet.</div>'}</div><div class="composer"><div style="display:flex;gap:6px">${attachBtn('eventFile')}${emojiBtn('eventMsg')}</div><input class="inlineInput" id="eventMsg" placeholder="Event message" onkeydown="if(event.key==='Enter'){event.preventDefault();sendEvent(${eid})}"><select id="eventPri" class="statusSelect priSelect"><option>normal</option><option>important</option><option>urgent</option></select><button class="btn" onclick="sendEvent(${eid})">Send</button></div></div>`;scrollFeedBottom()}window.eventFeed=eventFeed;async function sendEvent(eid){const input=$('#eventMsg'),f=$('#eventFile')?.files[0],v=input.value.trim()||(f?'Attachment':'');if(!v)return;input.value='';const m=await api('/api/messages',{method:'POST',body:JSON.stringify({scope:'event',scope_id:eid,sender:S.d.me.display_name,body:v,priority:$('#eventPri').value})});feedAppend(m);const updated=await uploadIfAttached('eventFile',m.id);if(updated)feedReplace(updated)}window.sendEvent=sendEvent;
function newEvent(){eventModal(null)}function editEvent(id){eventModal(S.d.events.find(x=>x.id===id))}window.newEvent=newEvent;window.editEvent=editEvent;
function eventModal(e){const id=e?.id||0;modal(`<h2>${e?'Edit Event':'New Event'}</h2><div class="form"><label>Event name<input id="evName" value="${esc(e?.name||'')}"></label><label>Client / organisation<input id="evClient" value="${esc(e?.client||'')}"></label><div class="grid2"><label>Start<input id="evStart" type="datetime-local" value="${esc((e?.starts_at||'').slice(0,16))}"></label><label>End<input id="evEnd" type="datetime-local" value="${esc((e?.ends_at||'').slice(0,16))}"></label></div><label>Status<select id="evStatus">${['scheduled','setting_up','live','finished'].map(x=>`<option value="${x}" ${e?.event_status===x?'selected':''}>${x}</option>`).join('')}</select></label><label>Colour<input id="evColor" type="color" value="${esc(e?.event_color||'#8b5cf6')}"></label>${e?`<h3>Rooms in this event</h3><div class="checkList">${roomsFor(id).map(r=>`<div class="listRow"><span class="dot ${r.current_status}"></span><b>${esc(r.name)}</b><small>${esc(r.operator_name||'Unassigned')}</small><button class="btn small secondary" onclick="editRoom(${r.id})">Edit</button></div>`).join('')||'<div class="body">No rooms yet.</div>'}</div><button type="button" class="btn small" onclick="newRoom(${id})">+ Add Room</button>`:`<p class="notice">Save the event first, then you can add its rooms.</p>`}<div><button class="btn" id="saveEvent">Save</button> ${e?'<button class="btn danger" id="deleteEvent">Delete Event</button>':''} <button class="btn secondary" onclick="closeModal()">Cancel</button></div></div>`);$('#saveEvent').onclick=async()=>{try{const b={name:$('#evName').value.trim(),client:$('#evClient').value.trim(),starts_at:$('#evStart').value,ends_at:$('#evEnd').value,event_status:$('#evStatus').value,event_color:$('#evColor').value};if(!b.name)return alert('Event name required');let eid=id;if(e)await api(`/api/events/${id}`,{method:'PATCH',body:JSON.stringify(b)});else eid=(await api('/api/events',{method:'POST',body:JSON.stringify(b)})).id;closeModal();await refresh();editEvent(eid)}catch(err){alert(err.message)}};if(e)$('#deleteEvent').onclick=async()=>{if(confirm(`Delete ${e.name}? This also removes its rooms.`)){await api(`/api/events/${id}`,{method:'DELETE'});closeModal();await refresh();control()}}}
function manage(){S.view='manage';S.rerender=manage;title('Events & Rooms','Rooms live inside their event');$('#content').innerHTML=`<div class="card"><div class="cardHead"><h2>Active Events</h2><button class="btn small" onclick="newEvent()">+ Event</button></div>${S.d.events.map(e=>`<div class="listRow"><b>${esc(e.name)}</b><small>${roomsFor(e.id).length} rooms</small><button class="btn small secondary" onclick="editEvent(${e.id})">Edit</button></div>`).join('')||'<div class="body">No events.</div>'}</div>`}window.manage=manage;
function roomModal(r,eid,onDone){const targetEid=r?r.event_id:eid;const done=onDone||(()=>editEvent(targetEid));modal(`<h2>${r?'Edit Room':'New Room'}</h2><div class="form"><label>Room name<input id="rmName" value="${esc(r?.name||'')}"></label><label>Short name<input id="rmShort" value="${esc(r?.short_name||'')}"></label><label>Status<select id="rmStatus">${['closed','setting_up','ready','rehearsal','live','technical_issue'].map(s=>`<option value="${s}" ${r?.current_status===s?'selected':''}>${statusLabel(s)}</option>`).join('')}</select></label><label>Assigned operator<input id="rmOperator" list="operatorNames" value="${esc(r?.operator_name||'')}"></label><datalist id="operatorNames">${S.d.operators.map(o=>`<option value="${esc(o.name)}">`).join('')}</datalist><div><button class="btn" id="saveRoom">Save</button> ${r?'<button class="btn danger" id="removeRoom">Remove Room</button>':''} <button class="btn secondary" onclick="closeModal()">Cancel</button></div></div>`);$('#saveRoom').onclick=async()=>{try{const b={name:$('#rmName').value.trim(),short_name:$('#rmShort').value.trim(),current_status:$('#rmStatus').value,operator_name:$('#rmOperator').value.trim(),event_id:targetEid};if(!b.name)return alert('Room name required');if(r)await api(`/api/rooms/${r.id}`,{method:'PATCH',body:JSON.stringify(b)});else await api('/api/rooms',{method:'POST',body:JSON.stringify(b)});closeModal();await refresh();done()}catch(err){alert(err.message)}};if(r)$('#removeRoom').onclick=async()=>{if(confirm(`Remove ${r.name}?`)){await api(`/api/rooms/${r.id}`,{method:'DELETE'});closeModal();await refresh();control()}}}
function newRoom(eid,onDone){roomModal(null,eid,onDone)}function editRoom(id,onDone){roomModal(S.d.rooms.find(x=>x.id===id),null,onDone)}window.newRoom=newRoom;window.editRoom=editRoom;
function operators(){S.view='operators';S.rerender=operators;title('Operators','Simple names only — no login required');$('#content').innerHTML=`<div class="toolbar"><button class="btn" onclick="newOperator()">+ Add Name</button></div><div class="card">${S.d.operators.map(o=>`<div class="listRow"><b>${esc(o.name)}</b><button class="btn small danger" onclick="deleteOperator(${o.id})">Remove</button></div>`).join('')||'<div class="body">No names yet.</div>'}</div><p class="notice">These are people assigned to rooms. They do not have passwords or login accounts.</p>`}window.operators=operators;async function newOperator(){const n=prompt('Name:');if(!n?.trim())return;await api('/api/operators',{method:'POST',body:JSON.stringify({name:n.trim()})});await refresh();operators()}window.newOperator=newOperator;async function deleteOperator(id){await api(`/api/operators/${id}`,{method:'DELETE'});await refresh();operators()}window.deleteOperator=deleteOperator;
function settings(){if(S.d.me.role!=='admin')return;S.view='settings';S.rerender=settings;title('System Settings','Administrator only');const curTheme=S.d.settings.ui_theme||'blue';const themes=[['blue','Blue'],['purple','Purple'],['green','Green'],['orange','Orange']];$('#content').innerHTML=`<div class="card body"><div class="form"><label>Venue name<input id="setVenue" value="${esc(S.d.settings.venue_name||'')}"></label><label>Control Centre display name<input id="setControl" value="${esc(S.d.settings.control_centre_name||'')}"></label><label>Daily sign-out time (UTC, everyone logged off)<input id="setLogoff" placeholder="03:00" value="${esc(S.d.settings.daily_logoff_utc||'03:00')}"></label><label>Colour theme<div class="themeSwatches">${themes.map(([id,label])=>`<button type="button" class="themeSwatch ${id===curTheme?'active':''}" data-theme-id="${id}" title="${label}" onclick="pickTheme('${id}')"></button>`).join('')}</div></label><button class="btn" id="saveSettings">Save</button></div></div>`;$('#saveSettings').onclick=async()=>{await api('/api/settings',{method:'PATCH',body:JSON.stringify({venue_name:$('#setVenue').value,control_centre_name:$('#setControl').value,daily_logoff_utc:$('#setLogoff').value.trim(),ui_theme:S.pendingTheme||curTheme})});S.pendingTheme=null;await refresh();settings()}}window.settings=settings;
function pickTheme(id){S.pendingTheme=id;applyTheme(id);$$('.themeSwatch').forEach(b=>b.classList.toggle('active',b.dataset.themeId===id))}
window.pickTheme=pickTheme;
async function accounts(){if(S.d.me.role!=='admin')return;S.view='accounts';S.rerender=accounts;title('Login Accounts','Administrator only');const a=await api('/api/accounts');$('#content').innerHTML=`<div class="toolbar"><button class="btn" onclick="newAccount()">+ Login Account</button></div><div class="card">${a.map(x=>`<div class="listRow"><b>${esc(x.display_name)}</b><small>${esc(x.username)} · ${x.role==='admin'?'Administrator':'Speaker Preview'}</small><button class="btn small secondary" onclick="resetPassword(${x.id},'${esc(x.username)}')">Password</button>${x.id!==S.d.me.id?`<button class="btn small danger" onclick="disableAccount(${x.id})">Disable</button>`:''}</div>`).join('')}</div>`}window.accounts=accounts;function newAccount(){modal(`<h2>New Login Account</h2><div class="form"><label>Username<input id="acUser"></label><label>Display name<input id="acName"></label><label>Password<input id="acPass" type="password"></label><label>Role<select id="acRole"><option value="speaker_preview">Speaker Preview</option><option value="admin">Administrator</option></select></label><button class="btn" id="saveAccount">Create</button></div>`);$('#saveAccount').onclick=async()=>{try{await api('/api/accounts',{method:'POST',body:JSON.stringify({username:$('#acUser').value,display_name:$('#acName').value,password:$('#acPass').value,role:$('#acRole').value})});closeModal();accounts()}catch(e){alert(e.message)}}}window.newAccount=newAccount;async function resetPassword(id,u){const p=prompt(`New password for ${u}:`);if(!p)return;await api(`/api/accounts/${id}/password`,{method:'PATCH',body:JSON.stringify({password:p})});alert('Password changed.')}window.resetPassword=resetPassword;async function disableAccount(id){if(confirm('Disable this login?')){await api(`/api/accounts/${id}`,{method:'DELETE'});accounts()}}window.disableAccount=disableAccount;
async function venue(){
    S.view='venue';S.feed={scope:'venue',scope_id:null};S.rerender=venue;title('Venue Operations','Venue-wide overview and broadcast feed');
    S.unreadVenue=false;updateVenueBadge();
    const counts={};S.d.rooms.forEach(r=>counts[r.current_status]=(counts[r.current_status]||0)+1);
    const statPills=Object.keys(counts).filter(s=>s!=='closed').map(s=>`<span class="badge">${counts[s]} ${statusLabel(s)}</span>`).join(' ')||'<span class="badge">All rooms closed</span>';
    const roomGrid=S.d.rooms.map(r=>{const e=S.d.events.find(x=>x.id===r.event_id);return `<div class="roomRow" onclick="openRoom(${r.event_id},${r.id})"><span class="dot ${r.current_status}"></span><b>${esc(r.name)}</b>${presenceDot(r.id)}${roomUnreadBadge(r.id)}<span class="operator">${esc(e?.name||'')}${r.operator_name?` · ${esc(r.operator_name)}`:''}</span><span class="badge">${statusLabel(r.current_status)}</span></div>`}).join('')||'<div class="body">No rooms yet.</div>';
    const ms=await api('/api/messages?scope=venue');if(S.view!=='venue')return;
    $('#content').innerHTML=`<div class="card"><div class="cardHead"><h2>Venue Overview</h2><div>${statPills}</div></div>${roomGrid}</div><div class="card feedCard"><div class="cardHead"><h2>Broadcast Feed</h2></div><div class="feed" id="feedList">${ms.map(messageHtml).join('')||'<div class="body feedEmpty">No messages yet.</div>'}</div><div class="composer"><div style="display:flex;gap:6px">${attachBtn('venueFile')}${emojiBtn('venueMsg')}</div><input id="venueMsg" class="inlineInput" placeholder="Venue message" onkeydown="if(event.key==='Enter'){event.preventDefault();sendVenue()}"><select id="venuePri" class="statusSelect priSelect"><option>normal</option><option>important</option><option>urgent</option></select><button class="btn" onclick="sendVenue()">Send</button></div></div>`;scrollFeedBottom();
}
window.venue=venue;async function sendVenue(){const input=$('#venueMsg'),f=$('#venueFile')?.files[0],v=input.value.trim()||(f?'Attachment':'');if(!v)return;input.value='';const m=await api('/api/messages',{method:'POST',body:JSON.stringify({scope:'venue',scope_id:null,sender:S.d.me.display_name,body:v,priority:$('#venuePri').value})});feedAppend(m);const updated=await uploadIfAttached('venueFile',m.id);if(updated)feedReplace(updated)}window.sendVenue=sendVenue;
async function helpPage(){
    S.view='help';S.rerender=helpPage;title('Help Requests',S.d.me.kind==='operator'?'Requests you can see':'Every request, newest first');
    const isOp=S.d.me.kind==='operator';
    if(isOp){
        const eid=S.d.me.event_id,rid=S.d.me.room_id;
        const list=S.d.help_requests||[];
        $('#content').innerHTML=`<div class="toolbar"><button class="btn danger" onclick="emergencyAlert(${eid},${rid})">🚨 Emergency</button><button class="btn danger" onclick="helpRequest(${eid},${rid})">Request Help</button></div><div class="card">${list.map(h=>{const closed=h.status==='resolved'||h.status==='cancelled';return `<div class="helpRow ${h.status==='new'?'new':''} ${closed?'closed':''}"><div style="flex:1"><b>${h.scope==='venue'?'📢 ':h.scope==='event'?'📣 ':''}${esc(h.room_name||'Room')} · ${esc(h.category)}</b><br><small>${esc(h.description)}</small></div><span class="badge">${esc(h.status)}</span><button class="btn small secondary" onclick="openHelpThread(${h.id})">Reply</button></div>`}).join('')||'<div class="body">No help requests yet.</div>'}</div>`;
        return;
    }
    $('#content').innerHTML='<div class="card body">Loading…</div>';const acctList=await api('/api/help');if(S.view!=='help')return;$('#content').innerHTML=`<div class="card">${acctList.map(h=>{const closed=h.status==='resolved'||h.status==='cancelled';return `<div class="helpRow ${h.status==='new'?'new':''} ${closed?'closed':''}"><div style="flex:1"><b>${h.scope==='venue'?'📢 ':h.scope==='event'?'📣 ':''}${esc(h.room_name||'Room')} · ${esc(h.category)}</b><br><small>${esc(h.description)}</small></div><span class="badge">${esc(h.status)}</span><button class="btn small secondary" onclick="openHelpThread(${h.id})">Reply</button>${closed?'':`<button class="btn small secondary" onclick="helpUpdate(${h.id},'acknowledged')">Acknowledge</button><button class="btn small" onclick="helpUpdate(${h.id},'resolved')">Resolve</button>`}</div>`}).join('')||'<div class="body">No help requests yet.</div>'}</div>`}window.helpPage=helpPage;async function helpUpdate(id,status){await api(`/api/help/${id}`,{method:'PATCH',body:JSON.stringify({status})});await refresh();helpPage()}window.helpUpdate=helpUpdate;
async function issuesPage(){
    S.view='issues';S.rerender=issuesPage;title('Issues','Report a bug and track fixes');
    S.unreadIssues=0;updateIssuesBadge();
    const isManager=S.d.me.kind==='account'&&(S.d.me.role==='admin'||S.d.me.role==='speaker_preview');
    $('#content').innerHTML='<div class="card body">Loading…</div>';
    const list=await api('/api/issues');if(S.view!=='issues')return;
    $('#content').innerHTML=`<div class="toolbar"><button class="btn danger" onclick="reportIssue()">🐞 Report Issue</button></div><div class="card">${list.map(i=>{const closed=i.status==='resolved';return `<div class="helpRow ${closed?'closed':''}"><div style="flex:1"><b>${esc(i.category)}</b> <small>· ${esc(i.reporter_name)} (${i.reporter_kind==='operator'?'Operator':'Control Centre'})</small><br><small>${esc(i.description)}</small></div><span class="badge">${esc(i.status)}</span>${isManager&&!closed?`<button class="btn small" onclick="issueUpdate(${i.id},'resolved')">Resolve</button>`:''}</div>`}).join('')||'<div class="body">No issues reported yet.</div>'}</div>`
}
window.issuesPage=issuesPage;
async function issueUpdate(id,status){await api(`/api/issues/${id}`,{method:'PATCH',body:JSON.stringify({status})});issuesPage()}
window.issueUpdate=issueUpdate;
function reportIssue(){modal(`<h2>🐞 Report Issue</h2><div class="form"><label>Category<select id="issCat"><option>App bug</option><option>Display / layout</option><option>Notifications</option><option>Login / access</option><option>Performance</option><option>Other</option></select></label><label>Describe what happened<textarea id="issDesc" placeholder="What did you expect, what happened instead?"></textarea></label><button class="btn danger" id="issSend">Send Report</button></div>`);$('#issSend').onclick=async()=>{const v=$('#issDesc').value.trim();if(!v)return alert('Please describe the issue');await api('/api/issues',{method:'POST',body:JSON.stringify({category:$('#issCat').value,description:v})});closeModal();if(S.d.me.kind==='account')issuesPage()}}
window.reportIssue=reportIssue;
function fmtDuration(sec){sec=sec|0;if(sec<60)return sec+'s';const m=Math.floor(sec/60)%60,h=Math.floor(sec/3600);return h>0?`${h}h ${m}m`:`${m}m`}
function fmtAgo(iso){if(!iso)return'never';const s=(Date.now()-new Date(iso).getTime())/1000;if(s<10)return'just now';if(s<60)return Math.floor(s)+'s ago';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}
function deviceRoomLabel(d){
    if(!d.room_id)return'<span class="operator">Unassigned</span>';
    const r=S.d.rooms?.find(x=>x.id===d.room_id);
    if(!r)return'<span class="operator">Unassigned</span>';
    const e=S.d.events?.find(x=>x.id===r.event_id);
    return `<span class="operator">${esc(r.name)}${e?` · ${esc(e.name)}`:''}</span>`;
}
function devicesPage(){
    if(S.d.me.role!=='admin')return;
    S.view='devices';S.rerender=devicesPage;title('Devices','PCs running the AT RoomComms client');
    const list=(S.d.devices||[]).slice().sort((a,b)=>(b.last_heartbeat||'').localeCompare(a.last_heartbeat||''));
    $('#content').innerHTML=`<div class="card">${list.map(d=>{
        const stale=(Date.now()-new Date(d.last_heartbeat||0).getTime())>360000;
        let diag=null;try{diag=d.diagnostics?JSON.parse(d.diagnostics):null}catch{}
        return `<div class="listRow"><span class="dot ${stale?'':'ready'}"></span><b>${esc(d.name)}</b><small>${esc(d.role||'')}${d.operator?` · ${esc(d.operator)}`:''}</small>${deviceRoomLabel(d)}${d.presenting?'<span class="badge">🖥️ Presenting</span>':''}<small>v${esc(d.app_version||'?')}</small><small>Uptime ${fmtDuration(d.uptime_seconds)}</small><small>${fmtAgo(d.last_heartbeat)}</small>${diag&&Object.keys(diag).length?`<button class="btn small secondary" onclick='showDeviceDiagnostics(${JSON.stringify(d.name)})'>Diagnostics</button>`:''}</div>`;
    }).join('')||'<div class="body">No devices have reported in yet.</div>'}</div>`;
}
window.devicesPage=devicesPage;
function showDeviceDiagnostics(name){
    const d=(S.d.devices||[]).find(x=>x.name===name);
    let diag={};try{diag=d?.diagnostics?JSON.parse(d.diagnostics):{}}catch{}
    const rows=Object.entries(diag).map(([k,v])=>`<div class="listRow"><b>${esc(k)}</b><span class="operator">${esc(String(v))}</span></div>`).join('')||'<div class="body">No diagnostics reported.</div>';
    modal(`<h2>Diagnostics — ${esc(name)}</h2><div class="checkList">${rows}</div><div><button class="btn secondary" onclick="closeModal()">Close</button></div>`);
}
window.showDeviceDiagnostics=showDeviceDiagnostics;
function helpRequest(eid,rid){modal(`<h2>Request Help</h2><div class="form"><label>Category<select id="helpCat"><option>Presentation</option><option>Video</option><option>Audio</option><option>Lighting</option><option>Network</option><option>Room Setup</option><option>Speaker Support</option><option>Other</option></select></label><label>Description<textarea id="helpDesc"></textarea></label><label>Send to<select id="helpScope"><option value="room">Just this room — Control Centre only</option><option value="event">Everywhere on this event — every room in it</option><option value="venue">Everywhere in the venue — any available technician</option></select></label><button class="btn danger" id="helpSend">Send Help Request</button></div>`);$('#helpSend').onclick=async()=>{await api('/api/help',{method:'POST',body:JSON.stringify({event_id:eid,room_id:rid,requested_by:S.d.me.display_name,category:$('#helpCat').value,description:$('#helpDesc').value,priority:'important',scope:$('#helpScope').value})});closeModal();await refresh();if(S.d.me.kind!=='operator')openRoom(eid,rid)}}window.helpRequest=helpRequest;
function emergencyAlert(eid,rid){modal(`<h2>🚨 Emergency</h2><p class="notice">This alerts every room and Control Centre across the whole venue immediately — no matter what.</p><div class="form"><label>What's happening?<textarea id="emgDesc" placeholder="Briefly describe the emergency"></textarea></label><button class="btn danger" id="emgSend">Send Emergency Alert</button></div>`);$('#emgSend').onclick=async()=>{const v=$('#emgDesc').value.trim()||'Emergency — assistance needed';const m=await api('/api/messages',{method:'POST',body:JSON.stringify({scope:'room',scope_id:rid,body:v,priority:'emergency'})});closeModal();feedAppend(m)}}window.emergencyAlert=emergencyAlert;
$$('.nav[data-view]').forEach(b=>b.onclick=()=>{const v=b.dataset.view;$$('.nav').forEach(x=>x.classList.remove('active'));b.classList.add('active');({control,venue,manage,operators,help:helpPage,dm:dmPage,settings,accounts,room:renderOperatorApp,issues:issuesPage,devices:devicesPage}[v]||control)()});$('#modal').onclick=e=>{if(e.target===$('#modal'))closeModal()};start();