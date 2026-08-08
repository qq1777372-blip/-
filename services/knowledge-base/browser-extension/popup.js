const button=document.querySelector('#capture');
const status=document.querySelector('#status');
button.addEventListener('click',async()=>{
  button.disabled=true;
  status.className='';
  status.textContent='正在读取当前页面...';
  try{
    const result=await chrome.runtime.sendMessage({type:'capture-current-page'});
    if(!result?.ok)throw new Error(result?.error||'采集失败');
    status.textContent='已发送，正在打开知策 AI';
    setTimeout(()=>window.close(),500);
  }catch(error){
    status.className='error';
    status.textContent=error.message;
    button.disabled=false;
  }
});
