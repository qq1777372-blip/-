export async function copyText(value:string){
  const text=String(value||'')
  if(!text)return false
  try{
    await navigator.clipboard.writeText(text)
    return true
  }catch{
    const input=document.createElement('textarea')
    input.value=text
    input.readOnly=true
    input.style.position='fixed'
    input.style.left='-9999px'
    input.style.opacity='0'
    document.body.appendChild(input)
    input.select()
    const copied=document.execCommand('copy')
    input.remove()
    return copied
  }
}
