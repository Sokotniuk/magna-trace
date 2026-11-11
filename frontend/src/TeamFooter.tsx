import { useEffect, useRef, useState } from 'react'

// Team credit. Names appear on hover, on keyboard focus and on click/tap (not hover alone).
const TEAM = 'Codex’sFanClub'
const MEMBERS = ['Nikita Sokotniuk', 'Ivan Kysel', 'Mykyta Terenia', 'Vasyl Slyvka']

export default function TeamFooter() {
  const [pinned, setPinned] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!pinned) return
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setPinned(false)
    }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setPinned(false) }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [pinned])

  return (
    <footer className="team-footer">
      <div ref={root} className={`team${pinned ? ' pinned' : ''}`}>
        <button type="button" className="team-button" aria-expanded={pinned} aria-controls="team-members"
          onClick={() => setPinned((value) => !value)}>
          <span className="team-button-label">Built by</span>
          <span className="team-button-name">{TEAM}</span>
        </button>
        <ul id="team-members" className="team-members" aria-label={`${TEAM} members`}>
          {MEMBERS.map((name, index) => (
            <li key={name} style={{ ['--i' as string]: index }}>
              <span className="team-initials" aria-hidden="true">{name.split(' ').map((part) => part[0]).join('')}</span>
              {name}
            </li>
          ))}
        </ul>
      </div>
    </footer>
  )
}
