const seedData = [
  {id:'seed-1',title:'商品发布前检查清单',category:'商品发布',source:'内部运营规范',updated:'2026-07-31',type:'rule',content:'商品发布前应依次检查类目是否准确、标题是否包含违规词、主图是否符合平台规范、销售属性是否完整、SKU价格与库存是否合理、物流模板是否可用。类目选择错误会造成属性不匹配或审核失败。提交前应保留本次发布参数，便于错误复盘。'},
  {id:'seed-2',title:'发布失败处理流程',category:'商品发布',source:'上货工具实战记录',updated:'2026-07-30',type:'case',content:'商品发布失败时，先记录平台返回的错误码和完整错误信息，不要立即反复提交。检查必填属性、销售属性、品牌、价格库存、物流模板和促销设置。若同类目多次出现相同错误，应沉淀为类目规则；只有接口真实返回多件优惠必填错误后，才将该类目标记为需要多件优惠。'},
  {id:'seed-3',title:'类目规则的有效性管理',category:'平台规则',source:'知识库维护规范',updated:'2026-07-31',type:'rule',content:'平台规则必须记录来源、采集日期和生效状态。同一规则出现新旧版本时，默认只使用状态为有效且生效日期最新的版本。无法确认有效性的内容只能作为参考，回答时必须明确提示需要人工核实。'},
  {id:'seed-4',title:'商品主图基础规范',category:'平台规则',source:'示例规则数据',updated:'2026-07-29',type:'rule',content:'商品主图应清晰展示实际商品，不得使用与商品无关的素材。图片不得出现严重遮挡、拉伸或低清晰度问题。不同类目的尺寸、留白和文字要求可能不同，发布前应以该类目当前规则为准。'},
  {id:'seed-5',title:'低价SKU风险排查',category:'店铺运营',source:'运营经验库',updated:'2026-07-28',type:'case',content:'设置SKU价格时，应检查最低价SKU是否为真实可售规格，避免用缺货、异常规格制造不合理价格区间。商品价格跨度过大时需要核对各规格成本、库存和展示名称，并在发布后检查前台价格展示是否符合预期。'},
  {id:'seed-6',title:'客服处理规则咨询的方法',category:'售后客服',source:'客服SOP',updated:'2026-07-27',type:'case',content:'遇到规则类咨询，客服应先确认商品类目、店铺类型和问题发生时间，再查询对应规则。回复时区分平台明确规定、店铺内部策略和个人经验，不得将经验描述为平台强制要求。'}
];

const bundledImports = [
  {
    id: 'alidocs-mExel2BLV59rgdDPi5zm3LdEVgk9rpMq',
    title: '投放期阶段功能解读',
    category: '店铺运营',
    source: 'https://alidocs.dingtalk.com/i/nodes/mExel2BLV59rgdDPi5zm3LdEVgk9rpMq',
    updated: '2026-07-31',
    type: 'rule',
    content: `为了帮助商家了解计划当前投放阶段、判断和调整投放，货品全站推广-控投产比投放计划会透出计划投放阶段，分为数据积累期、稳定投放期、效果调整期，并细分为商品模式和全店模式。

一、商品模式投放阶段

数据积累期：当天新建的计划，或未满足稳定投放期门槛的计划。

稳定投放期：近7天累计广告全引导成交笔数（净成交出价计划按净成交笔数）大于等于20笔，且近7天累计消耗大于等于200元；同时当前未暂停、调整ROI未高于系统推荐ROI预警值、未开启一键起量、未切换出价方式、未切换出价目标、未设置多目标出价。

效果调整期：修改出价超过平台推荐范围，或开启一键起量，或切换出价方式，或切换出价目标。

各阶段具体说明：

1. 计划新建当天处于数据积累期，建议保持持续投放，尽量避免频繁修改目标投产比，数据更新时间为当天。
2. 计划新建超过1天后，判断过去7天累计消耗和累计成交笔数是否满足稳定投放期条件；不满足仍为数据积累期，满足则进入稳定投放期，数据更新时间为前一天。
3. 如当天有暂停、调整ROI高于系统推荐ROI预警值、开启一键起量、切换出价方式或切换出价目标等操作，则切换为效果调整期，数据当天更新。
4. 进入效果调整期后，后续24小时如无上述操作，系统将重新判断计划属于数据积累期还是稳定投放期。
5. 稳定投放期内，如果过去7天成交笔数或累计消耗不再满足门槛，计划会回退到数据积累期。`
  }
];

const state={docs:loadDocs(),category:'',view:'ask',chats:loadChats(),currentChatId:''};
const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];

// v2 隔离旧版保存过的失败回答；旧数据仍留在 zhice-chats，不做删除。
const CHAT_STORAGE_KEY='zhice-chats-v2';
function loadChats(){try{const chats=JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY));return Array.isArray(chats)?chats:[]}catch{return[]}}
function saveChats(){localStorage.setItem(CHAT_STORAGE_KEY,JSON.stringify(state.chats.slice(0,30)))}
function renderChats(){$('#chatHistory').innerHTML=state.chats.map(chat=>`<div class="chat-item ${chat.id===state.currentChatId?'active':''}"><button class="chat-open" data-chat-id="${esc(chat.id)}" title="${esc(chat.title)}">${esc(chat.title)}</button><button class="chat-delete" data-chat-id="${esc(chat.id)}" title="删除对话"><i data-lucide="x"></i></button></div>`).join('');$$('.chat-open').forEach(button=>button.onclick=()=>openChat(button.dataset.chatId));$$('.chat-delete').forEach(button=>button.onclick=()=>deleteChat(button.dataset.chatId));icons()}
function bindSourceButtons(){$$('.source-button').forEach(button=>button.onclick=()=>openDocument(button.dataset.docId));$$('.copy-answer').forEach(button=>button.onclick=async()=>{try{await navigator.clipboard.writeText(button.closest('.answer-card').querySelector('.answer-text').innerText);toast('回答已复制')}catch{toast('复制失败')}});$$('.regenerate-answer').forEach(button=>button.onclick=()=>askQuestion(button.dataset.question||''))}
function openChat(id){const chat=state.chats.find(item=>item.id===id);if(!chat)return;state.currentChatId=id;$('#messages').innerHTML=chat.html||'';$('#welcome').style.display=chat.html?'none':'block';bindSourceButtons();setView('ask');renderChats();$('.conversation').scrollTop=$('.conversation').scrollHeight}
function newChat(){state.currentChatId='';$('#messages').innerHTML='';$('#welcome').style.display='block';setView('ask');renderChats();$('#question').focus()}
function deleteChat(id){state.chats=state.chats.filter(chat=>chat.id!==id);saveChats();if(state.currentChatId===id)newChat();else renderChats()}
function persistCurrentChat(title){if(!state.currentChatId){state.currentChatId=`chat-${Date.now()}`;state.chats.unshift({id:state.currentChatId,title:title.slice(0,24)||'新对话',html:'',updated:Date.now()})}const chat=state.chats.find(item=>item.id===state.currentChatId);if(!chat)return;const clone=$('#messages').cloneNode(true);clone.querySelectorAll('.answer-loading').forEach(node=>node.closest('.message')?.remove());clone.querySelectorAll('.message-image').forEach(image=>image.removeAttribute('src'));chat.html=clone.innerHTML.slice(0,400000);chat.updated=Date.now();state.chats.sort((a,b)=>b.updated-a.updated);saveChats();renderChats()}

function loadDocs(){
  let docs;
  try{const saved=JSON.parse(localStorage.getItem('zhice-docs'));docs=Array.isArray(saved)&&saved.length?saved:seedData}
  catch{docs=seedData}
  const known=new Set(docs.map(d=>d.id));
  return [...bundledImports.filter(d=>!known.has(d.id)),...docs];
}
function saveDocs(){localStorage.setItem('zhice-docs',JSON.stringify(state.docs.filter(doc=>!String(doc.id).startsWith('alidocs-'))))}
// 嵌在后台里时（/knowledge/ 或 embedded=1），服务的 /api/ 前缀在后台不存在，
// 必须改写成 nginx 转发的 /knowledge-api/。独立访问时保持原样。
function apiPath(url){const isIntegrated=window.location.pathname.startsWith('/knowledge/')||new URLSearchParams(window.location.search).get('embedded')==='1';return isIntegrated&&url.startsWith('/api/')?`/knowledge-api/${url.slice(5)}`:url}
async function loadAlidocsImports(){try{const response=await fetch(apiPath('/api/documents'),{cache:'no-store'});if(!response.ok)return;const data=await response.json();const imports=data.documents;if(!Array.isArray(imports))return;const local=state.docs.filter(doc=>!String(doc.id).startsWith('alidocs-'));state.docs=[...imports,...local];saveDocs();renderAll()}catch{}}
function esc(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function formatAnswer(value=''){
  const lines=String(value).replace(/\r/g,'').split('\n'); let html='',inList=false;
  const inline=text=>esc(text).replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
  const close=()=>{if(inList){html+='</ul>';inList=false}};
  for(const raw of lines){const line=raw.trim();if(!line){close();continue}
    const heading=line.match(/^(?:#{1,4}\s*|第[一二三四五六七八九十]+[、.]\s*|[一二三四五六七八九十]+[、.]\s*)(.+)$/);
    if(heading){close();html+=`<h4>${inline(heading[1])}</h4>`;continue}
    const bullet=line.match(/^(?:[-*•]|\d+[.)])\s+(.+)$/);
    if(bullet){if(!inList){html+='<ul>';inList=true}html+=`<li>${inline(bullet[1])}</li>`;continue}
    close();html+=`<p>${inline(line)}</p>`;
  } close(); return html||'<p>模型没有返回可显示的分析结果。</p>';
}
function tokenize(text){const clean=String(text).toLowerCase().replace(/[，。！？；：、,.!?;:\s]+/g,'');const chars=[...clean];const tokens=new Set();for(let i=0;i<chars.length;i++){tokens.add(chars[i]);if(i<chars.length-1)tokens.add(chars[i]+chars[i+1])}String(text).toLowerCase().split(/[\s，。！？；：、,.!?;:]+/).filter(x=>x.length>1).forEach(x=>tokens.add(x));return [...tokens]}
function search(query){const qt=tokenize(query);return state.docs.filter(d=>!state.category||d.category===state.category).map(d=>{const title=d.title.toLowerCase(),cat=d.category.toLowerCase(),body=d.content.toLowerCase();let score=0;qt.forEach(t=>{if(title.includes(t))score+=6;if(cat.includes(t))score+=4;if(body.includes(t))score+=1});if(body.includes(query.toLowerCase()))score+=15;return{doc:d,score}}).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,3)}
async function retrieveDocuments(query){const local=search(query);try{const data=await apiJson('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,limit:5})});const remote=(data.documents||[]).map(doc=>({doc,score:doc.score||0}));const merged=[...remote,...local],seen=new Set();return merged.filter(item=>{if(seen.has(item.doc.id))return false;seen.add(item.doc.id);return true}).slice(0,5)}catch{return local}}
function bestExcerpt(doc,query){const sentences=doc.content.split(/(?<=[。！？；])/).filter(Boolean);const qt=tokenize(query);return sentences.map(s=>({s,score:qt.reduce((n,t)=>n+(s.toLowerCase().includes(t)?1:0),0)})).sort((a,b)=>b.score-a.score).slice(0,2).map(x=>x.s).join('')||doc.content.slice(0,220)}
function answer(query){const hits=search(query);if(!hits.length)return{html:'当前知识库中没有找到足够可靠的依据。你可以换一种问法，或先导入相关规则文件。',hits:[]};const points=hits.map((x,i)=>`<p>${i+1}. ${esc(bestExcerpt(x.doc,query))}</p>`).join('');return{html:`<span class="confidence">已匹配 ${hits.length} 条知识</span>${points}`,hits}}
function renderStats(){const cats={};state.docs.forEach(d=>cats[d.category]=(cats[d.category]||0)+1);$('#docCount').textContent=`${state.docs.length} 条`;$('#navCount').textContent=state.docs.length;$('#ruleCount').textContent=state.docs.filter(d=>d.type==='rule').length;$('#caseCount').textContent=state.docs.filter(d=>d.type!=='rule').length;$('#categoryFilters').innerHTML=`<button class="filter ${!state.category?'active':''}" data-cat=""><span>全部知识</span><b>${state.docs.length}</b></button>`+Object.entries(cats).map(([k,v])=>`<button class="filter ${state.category===k?'active':''}" data-cat="${esc(k)}"><span>${esc(k)}</span><b>${v}</b></button>`).join('');const current=$('#libraryCategory').value;$('#libraryCategory').innerHTML='<option value="">全部分类</option>'+Object.keys(cats).map(k=>`<option>${esc(k)}</option>`).join('');$('#libraryCategory').value=current;$$('.filter').forEach(b=>b.onclick=()=>{state.category=b.dataset.cat;renderStats()})}
let libraryLimit=100;
function renderLibrary(){const q=$('#librarySearch').value.toLowerCase(),cat=$('#libraryCategory').value;const docs=state.docs.filter(d=>(!cat||d.category===cat)&&(!q||`${d.title}${d.category}${d.content}${d.source}${d.path||''}`.toLowerCase().includes(q))),visible=docs.slice(0,libraryLimit);$('#librarySummary').textContent=`${docs.length} 条`;$('#knowledgeRows').innerHTML=visible.map(d=>`<tr class="knowledge-row" data-id="${esc(d.id)}"><td><div class="title">${esc(d.title)}</div><div class="excerpt">${esc(d.content)}</div></td><td><span class="tag">${esc(d.category)}</span></td><td>${esc(d.source||'本地导入')}</td><td>${esc(d.updated)}</td><td><button class="delete" data-id="${esc(d.id)}" title="删除"><i data-lucide="trash-2"></i></button></td></tr>`).join('');$('#emptyLibrary').style.display=docs.length?'none':'block';$('#libraryMore').hidden=visible.length>=docs.length;$$('.knowledge-row').forEach(row=>row.onclick=e=>{if(!e.target.closest('.delete'))openDocument(row.dataset.id)});$$('.delete').forEach(b=>b.onclick=e=>{e.stopPropagation();if(confirm('确定删除这条知识吗？')){state.docs=state.docs.filter(d=>d.id!==b.dataset.id);saveDocs();renderAll();toast('知识已删除')}});icons()}
function openDocument(id){const doc=state.docs.find(d=>d.id===id);if(!doc)return;$('#documentTitle').textContent=doc.title;const images=Array.isArray(doc.images)?doc.images:[];$('#documentMeta').textContent=[doc.path,doc.category,doc.updated,images.length?`${images.length} 张图片`:null].filter(Boolean).join(' · ');const content=$('#documentContent');content.replaceChildren();const blocks=Array.isArray(doc.blocks)&&doc.blocks.length?doc.blocks:[{type:'text',text:doc.content},...images.map(image=>({type:'image',...(typeof image==='string'?{path:image}:image)}))];let imageIndex=0;blocks.forEach(block=>{if(block.type==='image'&&block.path){const image=document.createElement('img');image.className='document-inline-image';image.src=block.path;image.alt=`${doc.title} 图片 ${++imageIndex}`;image.loading='lazy';content.append(image)}else if(block.type==='text'&&block.text){const text=document.createElement('div');text.className='document-text';text.textContent=block.text;content.append(text)}});const link=$('#documentSource');link.href=doc.source||'#';link.style.display=doc.source&&/^https?:/.test(doc.source)?'inline-flex':'none';$('#documentModal').classList.add('open');icons()}
$('#closeDocument').onclick=()=>$('#documentModal').classList.remove('open');$('#documentModal').onclick=e=>{if(e.target===e.currentTarget)e.currentTarget.classList.remove('open')};$('#copyDocument').onclick=async()=>{try{await navigator.clipboard.writeText($('#documentContent').textContent);toast('正文已复制')}catch{toast('复制失败，请手动选择正文')}};
function renderAll(){renderStats();renderLibrary()}
async function askQuestion(q,image=''){
  q=q.trim()||(image?'请识别这张淘宝推广数据截图，并结合知识库给出店铺推广优化建议':'请结合知识库分析并给出可执行的淘宝店铺运营建议');
  if(!q)return;
  $('#welcome').style.display='none';
  const messages=$('#messages');let hits=[];
  const imageHtml=image?`<img class="message-image" src="${image}" alt="用户上传的图片">`:'';
  messages.insertAdjacentHTML('beforeend',`<div class="message"><div class="avatar">我</div><div class="bubble"><p>${esc(q)}</p>${imageHtml}</div></div>`);
  persistCurrentChat(q);
  const loadingId=`loading-${Date.now()}`;
  messages.insertAdjacentHTML('beforeend',`<div class="message ai" id="${loadingId}"><div class="avatar">知</div><div class="bubble answer-card"><div class="answer-loading"><span>正在检索知识并组织答案...</span><button type="button" class="stop-answer">停止</button></div></div></div>`);
  const controller=new AbortController();$(`#${loadingId} .stop-answer`).onclick=()=>controller.abort();
  $('.conversation').scrollTop=$('.conversation').scrollHeight;
  let content='',transient=false;
  try{
    hits=await retrieveDocuments(q);if(image&&!hits.length)hits=state.docs.slice(0,3).map(doc=>({doc,score:1}));
    if(!hits.length)throw new Error('知识库中没有找到相关资料，请先导入对应知识。');
    const response=await fetch(apiPath('/api/chat'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,documents:hits.map(x=>x.doc),image}),signal:controller.signal});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'AI 请求失败');
    content=formatAnswer(data.answer);
  }catch(error){
    transient=true;
    if(error.name==='AbortError')content='<p>已停止生成。</p>';else{const fallback=answer(q);content=`<p><strong>AI 暂时不可用：</strong>${esc(error.message)}</p><p>以下是本地检索结果：</p>${fallback.html}`}
  }
  const sources=hits.length?`<div class="sources"><h4>引用来源</h4>${hits.map((x,i)=>`<button class="source source-button" data-doc-id="${esc(x.doc.id)}"><b>[${i+1}]</b><span>${esc(x.doc.title)} · ${esc(x.doc.source)} · ${esc(x.doc.updated)}</span></button>`).join('')}</div>`:'';
  $(`#${loadingId} .bubble`).innerHTML=`<div class="answer-text">${content}</div>${sources}<div class="answer-actions"><button type="button" class="copy-answer" title="复制回答"><i data-lucide="copy"></i></button><button type="button" class="regenerate-answer" data-question="${esc(q)}" title="重新生成"><i data-lucide="refresh-cw"></i></button></div>`;
  $$(`#${loadingId} .source-button`).forEach(button=>button.onclick=()=>openDocument(button.dataset.docId));
  $(`#${loadingId} .copy-answer`).onclick=async()=>{try{await navigator.clipboard.writeText($(`#${loadingId} .answer-text`).innerText);toast('回答已复制')}catch{toast('复制失败')}};
  $(`#${loadingId} .regenerate-answer`).onclick=()=>askQuestion(q);
  icons();
  // 失败/中止结果只在当前页面临时显示，不写进历史，避免下次打开时把旧错误
  // 当成一次新的请求结果重放。用户问题已在请求前保存，成功答案才覆盖写回。
  if(!transient)persistCurrentChat(q);
  $('.conversation').scrollTop=$('.conversation').scrollHeight;
}
const issueLabels={content_too_short:'正文过短',missing_ordered_blocks:'缺少图文顺序',duplicate_sections:'章节重复'};
async function renderQuality(){const rows=$('#qualityRows');rows.innerHTML='<tr><td colspan="6">正在读取...</td></tr>';try{const data=await apiJson('/api/integrity');const documents=data.documents||[];$('#qualitySummary').textContent=`${documents.length} 篇需要检查`;$('#qualityNavCount').textContent=documents.length;rows.innerHTML=documents.map(doc=>{const details=(doc.integrity_details?.duplicate_sections||[]).map(item=>`<div class="quality-detail">${esc(item.heading)} ×${item.count}</div>`).join('');return `<tr><td><div class="quality-title">${esc(doc.title)}</div><div class="quality-path">${esc(doc.path||doc.source)}</div></td><td><div class="issue-list">${(doc.integrity_issues||[]).map(issue=>`<span class="issue-tag">${esc(issueLabels[issue]||issue)}</span>`).join('')}</div>${details}</td><td>${doc.content_length}</td><td>${doc.image_count}</td><td>${doc.block_count}</td><td><button type="button" class="secondary reimport-document" data-id="${esc(doc.id)}" title="重新采集"><i data-lucide="refresh-cw"></i></button></td></tr>`}).join('');$('#emptyQuality').style.display=documents.length?'none':'block';$$('.reimport-document').forEach(button=>button.onclick=()=>reimportDocument(button))}catch(error){rows.innerHTML=`<tr><td colspan="6">${esc(error.message)}</td></tr>`}icons()}
async function reimportDocument(button){button.disabled=true;try{await apiJson('/api/reimport-document',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:button.dataset.id})});toast('已启动单篇重新采集')}catch(error){toast(error.message)}finally{button.disabled=false}}
function setView(view){state.view=view;$$('.view').forEach(v=>v.classList.remove('active'));$(`#${view}View`).classList.add('active');$$('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view===view));const titles={ask:['知识问答','基于已收录规则，快速获得有来源的答案'],library:['知识管理','维护知识内容、分类与来源'],quality:['数据质量','检查文档完整性并重新采集异常内容']};[$('#pageTitle').textContent,$('#pageDesc').textContent]=titles[view]||titles.ask;if(view==='library')renderLibrary();if(view==='quality')renderQuality()}
function openModal(open){$('#importModal').classList.toggle('open',open);if(open)setTimeout(()=>$('#importTitle').focus(),50)}
function toast(msg){const el=$('#toast');el.textContent=msg;el.classList.add('show');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>el.classList.remove('show'),1800)}
function icons(){if(window.lucide)lucide.createIcons()}

async function loadBrowserCapture(){
  const captureId=new URLSearchParams(location.search).get('capture');
  if(!captureId)return;
  history.replaceState(null,'',location.pathname);
  try{
    const data=await apiJson(`/api/browser-capture?id=${encodeURIComponent(captureId)}`);
    const pageText=[`页面标题：${data.title||'未识别'}`,`页面地址：${data.url||'未提供'}`,data.text?`页面内容：\n${data.text}`:''].filter(Boolean).join('\n\n');
    await askQuestion(`请分析这个千牛/淘宝后台页面，提取关键经营数据并给出具体运营建议。\n\n${pageText}`,data.image||'');
  }catch(error){toast(error.message)}
}

$('#suggestions').innerHTML=['商品发布失败后应该怎么排查？','平台规则更新后，旧规则怎么处理？','SKU价格设置要注意什么？','主图发布前需要检查哪些问题？'].map(q=>`<button class="suggestion">${q}</button>`).join('');
$$('.suggestion').forEach(b=>b.onclick=()=>askQuestion(b.textContent));
let pendingImage='';
function clearQuestionImage(){pendingImage='';$('#questionImage').value='';$('#imagePreview').hidden=true;$('#imagePreview img').removeAttribute('src')}
async function prepareImage(file){
  if(!file||!file.type.startsWith('image/'))throw new Error('请选择图片文件');
  const bitmap=await createImageBitmap(file),limit=1600,scale=Math.min(1,limit/Math.max(bitmap.width,bitmap.height));
  const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
  canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
  return canvas.toDataURL('image/jpeg',.82);
}
$('#attachImage').onclick=()=>$('#questionImage').click();
$('#questionImage').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;pendingImage=await prepareImage(file);$('#imagePreview img').src=pendingImage;$('#imageName').textContent=file.name;$('#imagePreview').hidden=false}catch(error){clearQuestionImage();toast(error.message)}};
$('#question').onpaste=async e=>{
  const imageItem=[...(e.clipboardData?.items||[])].find(item=>item.type.startsWith('image/'));
  if(!imageItem)return;
  e.preventDefault();
  try{
    const file=imageItem.getAsFile();
    if(!file)throw new Error('没有读取到剪贴板图片');
    pendingImage=await prepareImage(file);
    $('#imagePreview img').src=pendingImage;
    $('#imageName').textContent='剪贴板图片';
    $('#imagePreview').hidden=false;
    toast('图片已粘贴');
  }catch(error){clearQuestionImage();toast(error.message)}
};
$('#removeImage').onclick=clearQuestionImage;
$('#newChat').onclick=newChat;
$('#askForm').onsubmit=e=>{e.preventDefault();const q=$('#question').value,image=pendingImage;if(!q.trim()&&!image)return;$('#question').value='';clearQuestionImage();askQuestion(q,image)};
$('#question').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('#askForm').requestSubmit()}};
$('.nav-group-toggle').onclick=()=>$('#storeNavGroup').classList.toggle('open');
$$('.sub-nav-item').forEach(button=>button.onclick=()=>{setView('ask');$('#question').value=button.dataset.prompt||'';$('#question').focus()});
$$('.nav-item').forEach(n=>n.onclick=()=>setView(n.dataset.view));
$('#refreshQuality').onclick=renderQuality;
$('#pauseImport').onclick=()=>controlImport('pause');$('#resumeImport').onclick=()=>controlImport('resume');$('#stopImport').onclick=()=>controlImport('stop');
$('#runOcr').onclick=async()=>{try{const data=await apiJson('/api/ocr/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({limit:100})});toast(data.running?'图片文字识别已启动':'图片文字识别未启动')}catch(error){toast(error.message)}};
$('#openImport').onclick=()=>{openModal(true);refreshAlidocsProgress()};$('#closeImport').onclick=$('#cancelImport').onclick=()=>openModal(false);$('#importModal').onclick=e=>{if(e.target===e.currentTarget)openModal(false)};
function showImportProgress(message,error=false){const el=$('#importProgress');el.hidden=false;el.textContent=message;el.classList.toggle('error',error)}
let pendingWebImages=[],pendingWebBlocks=[];
$('#readWebUrl').onclick=async()=>{const url=$('#importUrl').value.trim();if(!url)return showImportProgress('请先输入网页链接',true);pendingWebImages=[];pendingWebBlocks=[];showImportProgress('正在读取网页文字和图片...');try{const data=await apiJson('/api/import-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});$('#importTitle').value=data.title;$('#importSource').value=data.source;$('#importContent').value=data.content;pendingWebImages=Array.isArray(data.images)?data.images:[];pendingWebBlocks=Array.isArray(data.blocks)?data.blocks:[];showImportProgress(`网页已读取：正文和 ${pendingWebImages.length} 张图片，确认后加入知识库`)}catch(error){showImportProgress(error.message,true)}};
let alidocsTimer;
async function refreshAlidocsProgress(){try{const status=await apiJson('/api/alidocs/status');const progress=status.pending?`，本轮 ${status.completed}/${status.pending}`:'';showImportProgress(`钉钉文档：数据库 ${status.documents} 篇${progress}，失败 ${status.failed||0} 篇，完整性告警 ${status.warnings||0} 篇${status.running?'，正在继续...':'，任务已停止'}`,(status.failed||0)>0&&!status.running);$('#showImportFailures').hidden=!(status.failed||0);$('#pauseImport').hidden=!status.running;$('#stopImport').hidden=!status.running;$('#resumeImport').hidden=status.running;await loadAlidocsImports();if(!status.running){clearInterval(alidocsTimer);alidocsTimer=null}}catch(error){showImportProgress(error.message,true)}}
async function controlImport(action){try{await apiJson('/api/alidocs/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});toast(action==='pause'?'任务已暂停':action==='resume'?'任务已继续':'任务已停止');await refreshAlidocsProgress()}catch(error){toast(error.message)}}
$('#showImportFailures').onclick=async()=>{try{const data=await apiJson('/api/alidocs/failures');$('#failureList').innerHTML=(data.failures||[]).map(item=>`<div class="failure-item"><div><strong>${esc(item.title||'未命名文档')}</strong><p>${esc(item.error||'读取失败')}</p></div><a href="https://alidocs.dingtalk.com/i/nodes/${encodeURIComponent(item.uuid||'')}" target="_blank" rel="noreferrer" title="打开原文"><i data-lucide="external-link"></i></a></div>`).join('')||'<div class="empty-state" style="display:block">没有失败项</div>';$('#failureModal').classList.add('open');icons()}catch(error){showImportProgress(error.message,true)}};$('#closeFailures').onclick=()=>$('#failureModal').classList.remove('open');$('#failureModal').onclick=e=>{if(e.target===e.currentTarget)e.currentTarget.classList.remove('open')};
$('#readAlidocs').onclick=async()=>{const url=$('#importUrl').value.trim();if(!url.includes('alidocs.dingtalk.com/'))return showImportProgress('请输入钉钉文档链接',true);showImportProgress('正在启动钉钉知识库批量读取...');try{await apiJson('/api/import-alidocs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});if(!alidocsTimer)alidocsTimer=setInterval(refreshAlidocsProgress,3000);await refreshAlidocsProgress()}catch(error){showImportProgress(error.message,true)}};
$('#fileInput').onchange=async e=>{const f=e.target.files[0];if(!f)return;pendingWebImages=[];pendingWebBlocks=[];try{const text=await f.text();$('#importSource').value=f.name;$('#importTitle').value=$('#importTitle').value||f.name.replace(/\.[^.]+$/,'');if(f.name.toLowerCase().endsWith('.json')){const data=JSON.parse(text);$('#importContent').value=typeof data==='string'?data:JSON.stringify(data,null,2)}else $('#importContent').value=text;toast('文件读取成功')}catch{toast('文件读取失败')}};
$('#importForm').onsubmit=e=>{e.preventDefault();state.docs.unshift({id:`doc-${Date.now()}`,title:$('#importTitle').value.trim(),category:$('#importCategory').value,source:$('#importSource').value.trim()||'本地导入',updated:new Date().toLocaleDateString('sv-SE'),type:$('#importCategory').value==='平台规则'?'rule':'case',content:$('#importContent').value.trim(),images:pendingWebImages,blocks:pendingWebBlocks});pendingWebImages=[];pendingWebBlocks=[];saveDocs();e.target.reset();openModal(false);renderAll();toast('知识已加入')};
$('#librarySearch').oninput=()=>{libraryLimit=100;renderLibrary()};$('#libraryCategory').onchange=()=>{libraryLimit=100;renderLibrary()};$('#loadMoreDocs').onclick=()=>{libraryLimit+=100;renderLibrary()};

async function apiJson(url,options={}){const isIntegrated=window.location.pathname.startsWith('/knowledge/')||new URLSearchParams(window.location.search).get('embedded')==='1';const apiUrl=isIntegrated&&url.startsWith('/api/')?`/knowledge-api/${url.slice(5)}`:url;const response=await fetch(apiUrl,{credentials:'same-origin',...options});const data=await response.json();if(!response.ok)throw new Error(data.error||data.detail||'请求失败');return data}
async function refreshAiStatus(){try{const s=await apiJson('/api/status');$('#aiStatusText').textContent=s.configured?'AI 已连接':'AI 待配置';$('#aiStatusDetail').textContent=s.configured?s.model:'点击顶部 AI 设置';document.querySelector('.status-dot').style.background=s.configured?'#4ac49c':'#e8a23a'}catch{$('#aiStatusText').textContent='请通过启动文件打开';$('#aiStatusDetail').textContent='后端服务未运行';document.querySelector('.status-dot').style.background='#c54141'}}
async function openSettings(){openModal(false);$('#settingsModal').classList.add('open');$('#connectionResult').className='connection-result';try{const c=await apiJson('/api/config');$('#aiBaseUrl').value=c.base_url;$('#aiModel').value=c.model;$('#aiApiKey').value='';$('#aiApiKey').placeholder=c.has_key?'已保存密钥，留空表示不修改':'请输入 API Key'}catch(error){$('#connectionResult').textContent='请双击“启动知识库.bat”后再配置';$('#connectionResult').className='connection-result error'}}
function closeSettings(){$('#settingsModal').classList.remove('open')}
$('#openSettings').onclick=openSettings;$('#closeSettings').onclick=closeSettings;$('#settingsModal').onclick=e=>{if(e.target===e.currentTarget)closeSettings()};
$$('[data-preset]').forEach(button=>button.onclick=()=>{const presets={openai:['https://api.openai.com/v1','gpt-4.1-mini'],deepseek:['https://api.deepseek.com/v1','deepseek-chat'],qwen:['https://dashscope.aliyuncs.com/compatible-mode/v1','qwen-plus']};[$('#aiBaseUrl').value,$('#aiModel').value]=presets[button.dataset.preset]});
$('#settingsForm').onsubmit=async e=>{e.preventDefault();const result=$('#connectionResult');try{await apiJson('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_url:$('#aiBaseUrl').value,model:$('#aiModel').value,api_key:$('#aiApiKey').value})});result.textContent='设置已保存';result.className='connection-result ok';await refreshAiStatus();setTimeout(closeSettings,700)}catch(error){result.textContent=error.message;result.className='connection-result error'}};
$('#testConnection').onclick=async()=>{const result=$('#connectionResult');result.textContent='正在连接模型...';result.className='connection-result ok';try{await apiJson('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({base_url:$('#aiBaseUrl').value,model:$('#aiModel').value,api_key:$('#aiApiKey').value})});const data=await apiJson('/api/test',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});result.textContent=`连接成功：${data.answer}`;result.className='connection-result ok';await refreshAiStatus()}catch(error){result.textContent=error.message;result.className='connection-result error'}};
const embeddedView=new URLSearchParams(location.search).get('view');renderAll();renderChats();icons();refreshAiStatus();loadAlidocsImports();if(state.chats.length)openChat(state.chats[0].id);if(['ask','library','quality'].includes(embeddedView))setView(embeddedView);loadBrowserCapture();
