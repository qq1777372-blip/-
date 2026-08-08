async function extractPage(){
  const visible=element=>{
    const style=getComputedStyle(element);
    return style.display!=='none'&&style.visibility!=='hidden';
  };
  const originalY=window.scrollY;
  const maxY=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);
  const chunks=[];
  const seen=new Set();
  const collect=()=>{
    const tables=[...document.querySelectorAll('table')].filter(visible).map((table,index)=>{
      const rows=[...table.rows].slice(0,500).map(row=>[...row.cells].map(cell=>cell.innerText.trim()).join('\t'));
      return rows.length?`表格 ${index+1}:\n${rows.join('\n')}`:'';
    }).filter(Boolean);
    const bodyText=(document.body?.innerText||'').replace(/\n{3,}/g,'\n\n').trim();
    for(const value of [bodyText,...tables]){if(value&&!seen.has(value)){seen.add(value);chunks.push(value)}}
  };
  for(let y=0;y<=maxY;y+=Math.max(400,Math.floor(window.innerHeight*.8))){
    window.scrollTo(0,y);
    await new Promise(resolve=>setTimeout(resolve,350));
    collect();
  }
  window.scrollTo(0,originalY);
  return {
    title:document.title,
    url:location.href,
    text:chunks.join('\n\n').slice(0,100000)
  };
}

chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(message.type!=='capture-current-page')return;
  (async()=>{
    try{
      const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
      if(!tab?.id||!/^https?:/.test(tab.url||''))throw new Error('当前页面不支持采集');
      const [{result:page}]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:extractPage});
      let image='';
      try{image=await chrome.tabs.captureVisibleTab(tab.windowId,{format:'jpeg',quality:80})}catch{}
      const response=await fetch('http://127.0.0.1:8765/api/browser-capture',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({...page,image})
      });
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||'知策服务接收失败');
      await chrome.tabs.create({url:`http://127.0.0.1:8765/?capture=${encodeURIComponent(data.capture_id)}`});
      sendResponse({ok:true});
    }catch(error){sendResponse({ok:false,error:error.message.includes('fetch')?'请先启动知策知识库':error.message})}
  })();
  return true;
});
