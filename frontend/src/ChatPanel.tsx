import { reportSignedOut } from './api'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'

// Chat with the diagnostic agent (student C). The server keeps the model key, the active case and
// the open question; this component only sends text and shows the text the backend returns.
// Nothing here calculates, rounds or derives a value.

type ToolCall = { name: string; status: string | null; code: string | null; request_id: string | null }
type Message = { role: 'technician' | 'trace' | 'problem'; text: string; model?: string | null; tools?: ToolCall[] }

const SUGGESTIONS = [
  'Investigate station ST3003. What happened?',
  'Where does the Motor Speed deviation come from?',
  'Give me a handover for the next shift.',
]

function inline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={index}>{part.slice(1, -1)}</code>
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={index}>{part.slice(2, -2)}</strong>
    return part
  })
}

function cells(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim())
}

// Minimal renderer for the backend's text: tables, bullet lists and paragraphs.
function Blocks({ text }: { text: string }) {
  const lines = text.split('\n')
  const blocks: ReactNode[] = []
  for (let i = 0; i < lines.length;) {
    const line = lines[i]
    if (line.trim().startsWith('|')) {
      const rows: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('|')) rows.push(lines[i++])
      const body = rows.filter((row) => !/^\|[\s|:-]+\|?$/.test(row.trim()))
      const [head, ...rest] = body
      blocks.push(<div className="chat-table" key={blocks.length}><table>
        <thead><tr>{cells(head).map((cell, index) => <th key={index}>{inline(cell)}</th>)}</tr></thead>
        <tbody>{rest.map((row, r) => <tr key={r}>{cells(row).map((cell, index) => <td key={index}>{inline(cell)}</td>)}</tr>)}</tbody>
      </table></div>)
    } else if (line.trim().startsWith('- ')) {
      const items: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('- ')) items.push(lines[i++].trim().slice(2))
      blocks.push(<ul key={blocks.length}>{items.map((item, index) => <li key={index}>{inline(item)}</li>)}</ul>)
    } else {
      if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line)}</p>)
      i += 1
    }
  }
  return <>{blocks}</>
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [caseId, setCaseId] = useState<string | null>(null)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [messages, busy])

  async function send(text: string) {
    const message = text.trim()
    if (!message || busy) return
    setBusy(true)
    setDraft('')
    setMessages((current) => [...current, { role: 'technician', text: message }])
    try {
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, conversation_id: conversationId }),
      })
      const body = await response.json().catch(() => null)
      if (!response.ok || !body || body.status !== 'ok' || typeof body.data?.reply !== 'string') {
        reportSignedOut(response.status, body?.error?.code)
        const code = body?.error?.code ? `${body.error.code}: ` : ''
        const detail = body?.error?.message ?? `The chat service answered with HTTP ${response.status}.`
        setMessages((current) => [...current, { role: 'problem', text: `${code}${detail} Nothing was assumed.` }])
        return
      }
      setConversationId(body.data.conversation_id)
      setCaseId(body.case_id ?? null)
      setMessages((current) => [...current, { role: 'trace', text: body.data.reply, model: body.data.model, tools: body.data.tool_calls }])
    } catch {
      setMessages((current) => [...current, { role: 'problem', text: 'Could not reach the chat service. Check the backend and proxy. Nothing was assumed.' }])
    } finally {
      setBusy(false)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void send(draft)
  }

  function reset() {
    setMessages([])
    setConversationId(null)
    setCaseId(null)
  }

  return (
    <section className="chat" aria-labelledby="chat-heading">
      <h3 id="chat-heading">Ask TRACE</h3>
      <p className="scope-note">Ask about a station in your own words. The AI only picks the check; every value, limit and evidence ID comes from the line database, unchanged. <span className="model-note">Open-weight model, standing in for Microsoft Copilot.</span></p>
      <div className="chat-log" role="log" aria-live="polite">
        {messages.length === 0 && <div className="chat-suggestions">
          {SUGGESTIONS.map((text) => <button key={text} type="button" className="secondary" disabled={busy} onClick={() => void send(text)}>{text}</button>)}
        </div>}
        {messages.map((message, index) => <article key={index} className={`chat-message ${message.role}`}>
          <header>{message.role === 'technician' ? 'Technician' : message.role === 'trace' ? 'TRACE' : 'Problem'}</header>
          {message.role === 'trace' ? <Blocks text={message.text} /> : <p>{message.text}</p>}
          {message.role === 'trace' && <footer>
            {message.tools && message.tools.length > 0
              ? message.tools.map((tool, i) => <span key={i}>tool <code>{tool.name}</code> → {tool.status}{tool.code ? ` (${tool.code})` : ''}{tool.request_id ? <> · request <code>{tool.request_id}</code></> : null}</span>)
              : <span>no tool called</span>}
            {message.model && <span> · model <code>{message.model}</code></span>}
          </footer>}
        </article>)}
        {busy && <p role="status">TRACE is working…</p>}
        <div ref={end} />
      </div>
      <form onSubmit={handleSubmit} className="chat-form">
        <label htmlFor="chat-input">Message</label>
        <div className="station-controls">
          <input id="chat-input" type="text" value={draft} maxLength={2000} autoComplete="off" disabled={busy}
            placeholder="e.g. Investigate station ST3003" onChange={(event) => setDraft(event.target.value)} />
          <button type="submit" disabled={busy || !draft.trim()}>Send</button>
          <button type="button" className="secondary" disabled={busy || messages.length === 0} onClick={reset}>New conversation</button>
        </div>
      </form>
      {caseId && <p className="scope-note">Active case: <code>{caseId}</code></p>}
    </section>
  )
}
