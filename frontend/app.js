const BACKEND = '/api/chat'

const output = document.getElementById('chat-output')
const input = document.getElementById('msg')
const sendBtn = document.getElementById('send')
const status = document.getElementById('status')

function setStatus(t){ status.textContent = t }

function append(role, text){
  const wrap = document.createElement('div')
  wrap.className = 'msg ' + (role === 'user' ? 'user' : 'bot')
  const bubble = document.createElement('div')
  bubble.className = 'bubble'
  bubble.textContent = text
  wrap.appendChild(bubble)
  output.appendChild(wrap)
  output.scrollTop = output.scrollHeight
}

async function sendMessage(){
  const text = input.value.trim()
  if(!text) return

  append('user', text)
  input.value = ''
  sendBtn.disabled = true
  setStatus('Sending...')

  try{
    const resp = await fetch(BACKEND, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    })

    if(!resp.ok){
      const tx = await resp.text()
      append('bot', 'Error: ' + resp.status + ' — ' + tx)
    } else {
      const j = await resp.json()
      const reply = j.reply ?? j.message ?? JSON.stringify(j)
      append('bot', reply)
    }
  }catch(err){
    append('bot', 'Network error — check backend: ' + (err.message || err))
  } finally{
    sendBtn.disabled = false
    setStatus('Idle')
  }
}

sendBtn.addEventListener('click', sendMessage)
input.addEventListener('keydown', (e)=>{ if(e.key === 'Enter') sendMessage() })

append('bot', 'Hello! This is a minimal chat UI. Type a message and press Send.')
