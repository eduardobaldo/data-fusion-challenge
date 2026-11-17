import { useEffect, useMemo, useState } from 'react'
import { Activity, ArrowDownRight, ArrowUpRight, CalendarDays, Check, ChevronDown, ChevronLeft, ChevronRight, CloudSun, Compass, MapPin, Plus, Search, ShieldCheck, Users, X } from 'lucide-react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const VENUES_PER_PAGE = 20

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json', ...options.headers }, ...options })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || 'Não foi possível concluir a solicitação.')
  return body
}

function dateLabel(value, weekday = true) {
  return new Intl.DateTimeFormat('pt-BR', { weekday: weekday ? 'short' : undefined, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function localDateInput(value) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function capacityLabel(match) { return `${match.attendee_count}/${match.capacity}` }

function App() {
  const [venues, setVenues] = useState([])
  const [matches, setMatches] = useState([])
  const [city, setCity] = useState('Sua cidade')
  const [region, setRegion] = useState('')
  const [selectedVenue, setSelectedVenue] = useState(null)
  const [query, setQuery] = useState('')
  const [venuePage, setVenuePage] = useState(1)
  const [person, setPerson] = useState(() => localStorage.getItem('fdb-name') || '')
  const [nameInput, setNameInput] = useState(() => localStorage.getItem('fdb-name') || '')
  const [formOpen, setFormOpen] = useState(false)
  const [venueFormOpen, setVenueFormOpen] = useState(false)
  const [venueEditId, setVenueEditId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [forecast, setForecast] = useState({})

  async function refresh() {
    const [nextVenues, nextMatches, config] = await Promise.all([request('/venues'), request('/matches'), request('/config')])
    setVenues(nextVenues)
    setMatches(nextMatches)
    setCity(config.city)
    setRegion(config.region)
    setSelectedVenue(current => current ? nextVenues.find(v => v.id === current.id) || nextVenues[0] : nextVenues[0])
  }

  useEffect(() => { refresh().catch(err => setMessage(err.message)) }, [])

  const filteredVenues = useMemo(() => venues.filter(v => `${v.name} ${v.address}`.toLowerCase().includes(query.toLowerCase())), [venues, query])
  const totalVenuePages = Math.max(1, Math.ceil(filteredVenues.length / VENUES_PER_PAGE))
  const venueStartIndex = (venuePage - 1) * VENUES_PER_PAGE
  const pagedVenues = filteredVenues.slice(venueStartIndex, venueStartIndex + VENUES_PER_PAGE)
  const pageNumbers = totalVenuePages <= 7
    ? Array.from({ length: totalVenuePages }, (_, i) => i + 1)
    : venuePage <= 4
      ? [1, 2, 3, 4, 5, '…', totalVenuePages]
      : venuePage >= totalVenuePages - 3
        ? [1, '…', totalVenuePages - 4, totalVenuePages - 3, totalVenuePages - 2, totalVenuePages - 1, totalVenuePages]
        : [1, '…', venuePage - 1, venuePage, venuePage + 1, '…', totalVenuePages]
  useEffect(() => { setVenuePage(1) }, [query])
  useEffect(() => { if (venuePage > totalVenuePages) setVenuePage(totalVenuePages) }, [venuePage, totalVenuePages])
  // Operational indicators are calculated from live API data so they update
  // immediately after a match or attendance change.
  const totalGames = matches.length
  const totalPlayers = matches.reduce((sum, match) => sum + match.attendee_count, 0)
  const avgOccupancy = matches.length
    ? matches.reduce((sum, match) => sum + (match.attendee_count / match.capacity) * 100, 0) / matches.length
    : null

  function rememberName() {
    const clean = nameInput.trim()
    if (clean.length < 2) return setMessage('Digite um nome com pelo menos 2 caracteres.')
    localStorage.setItem('fdb-name', clean)
    setPerson(clean)
    setMessage(`Tudo certo, ${clean}! Seu nome ficará salvo neste navegador.`)
  }

  async function createMatch(event) {
    event.preventDefault()
    if (!person) return setMessage('Defina seu nome no perfil antes de criar uma partida.')
    const data = new FormData(event.currentTarget)
    setBusy(true)
    try {
      const startsAt = new Date(data.get('starts_at')).toISOString()
      await request('/matches', { method: 'POST', body: JSON.stringify({ venue_id: Number(data.get('venue_id')), title: data.get('title'), starts_at: startsAt, capacity: Number(data.get('capacity')), organizer_name: person }) })
      setFormOpen(false)
      setMessage('Partida criada. Você já está confirmado como organizador.')
      await refresh()
    } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function saveVenue(event) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const payload = { name: data.get('name'), latitude: Number(data.get('latitude')), longitude: Number(data.get('longitude')), address: data.get('address') }
    setBusy(true)
    try {
      if (venueEditId) await request(`/venues/${venueEditId}`, { method: 'PATCH', body: JSON.stringify(payload) })
      else await request('/venues', { method: 'POST', body: JSON.stringify(payload) })
      setVenueFormOpen(false)
      setVenueEditId(null)
      setMessage(venueEditId ? 'Dados do campo atualizados.' : 'Campo adicionado ao catálogo da cidade.')
      await refresh()
    } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function attendance(match, action) {
    if (!person) return setMessage('Defina seu nome no perfil para confirmar presença.')
    setBusy(true)
    try {
      if (action === 'join') await request(`/matches/${match.id}/attendees`, { method: 'POST', body: JSON.stringify({ display_name: person }) })
      else await request(`/matches/${match.id}/attendees/${encodeURIComponent(person)}`, { method: 'DELETE' })
      setMessage(action === 'join' ? 'Presença confirmada!' : 'Você saiu da partida.')
      await refresh()
    } catch (error) { setMessage(error.message) } finally { setBusy(false) }
  }

  async function loadForecast(match) {
    setForecast(current => ({ ...current, [match.id]: { loading: true } }))
    try {
      const value = await request(`/venues/${match.venue_id}/forecast?starts_at=${encodeURIComponent(match.starts_at)}`)
      setForecast(current => ({ ...current, [match.id]: { value } }))
    } catch (error) { setForecast(current => ({ ...current, [match.id]: { error: error.message } })) }
  }

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top"><span className="brand-mark">FB</span><span>futebol<span className="brand-light"> de bairro</span></span></a>
      <nav className="nav-links"><a className="nav-active" href="#campos">Explorar</a><a href="#partidas">Partidas</a><a href="#dados">Dados da comunidade</a></nav>
      <div className="profile-area"><span className="city-pill"><MapPin size={14}/>{city}</span><button className="profile-button" onClick={() => document.getElementById('profile')?.scrollIntoView({ behavior: 'smooth' })}><span className="avatar">{person ? person[0].toUpperCase() : '👤'}</span><ChevronDown size={14}/></button></div>
    </header>

    <main id="top">
      <section className="hero">
        <div className="hero-copy"><div className="eyebrow"><span className="pulse-dot"/> O futebol acontece perto</div><h1>O próximo jogo<br/>começa <em>no seu bairro.</em></h1><p>Encontre um campo, reúna a galera e tire a partida do grupo de mensagens.</p><a className="button button-dark" href="#campos">Encontrar um campo <ArrowDownRight size={17}/></a></div>
        <div className="hero-art" aria-label="Ilustração de um campo de futebol"><div className="sun"/><div className="field-lines"><span className="midline"/><span className="center-circle"/><span className="box left-box"/><span className="box right-box"/><span className="corner one"/><span className="corner two"/></div><div className="hero-sticker sticker-top"><CloudSun size={17}/> clima ao vivo</div><div className="hero-sticker sticker-bottom"><span className="sticker-ball">⚽</span><span><b>Joga junto</b><small>Tem espaço pra você</small></span></div><div className="art-note">seu campinho<br/>favorito ↗</div></div>
        <div className="hero-index"><span>01 / 03</span><span className="index-bar"><i/></span><span>{region ? `${region}, BR` : city}</span></div>
      </section>

      <section className="stats-strip" id="dados"><div className="stats-intro"><span className="tiny-kicker">BOLA ROLANDO</span><strong>O que está<br/>acontecendo</strong></div><div className="stat"><span>PARTIDAS ORGANIZADAS</span><b>{Number(totalGames).toLocaleString('pt-BR')}</b><small><Activity size={14}/> na comunidade</small></div><div className="stat"><span>JOGADORES EM CAMPO</span><b>{Number(totalPlayers).toLocaleString('pt-BR')}</b><small><Users size={14}/> confirmados</small></div><div className="stat"><span>OCUPAÇÃO MÉDIA</span><b>{avgOccupancy == null ? '—' : `${Math.round(avgOccupancy)}%`}</b><small><ArrowUpRight size={14}/> das partidas</small></div><div className="stat-aside">Resumo atualizado<br/>com as partidas cadastradas <span>↘</span></div></section>

      <section className="explore-section" id="campos"><div className="section-heading"><div><span className="tiny-kicker">SEU PRÓXIMO GRAMADO</span><h2>Campos por perto<span className="heading-dot">.</span></h2><p>Descubra espaços e partidas na sua região.</p></div><div className="heading-actions"><label className="search-box"><Search size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar campo ou bairro"/></label><button className="button button-green" onClick={() => { setFormOpen(true); document.getElementById('new-match')?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }}><Plus size={17}/> Criar partida</button></div></div>
        {message && <div className="notice" role="status"><span>{message}</span><button onClick={() => setMessage('')} aria-label="Fechar"><X size={15}/></button></div>}
        <div className="venue-tools"><button className="text-action" onClick={() => { setVenueEditId(null); setVenueFormOpen(open => !open) }}><Plus size={14}/> Adicionar campo</button>{selectedVenue && <button className="text-action" onClick={() => { setVenueEditId(selectedVenue.id); setVenueFormOpen(true) }}>Corrigir campo selecionado</button>}</div>
        {venueFormOpen && <form className="venue-edit-form" onSubmit={saveVenue}><label>Nome do local<input name="name" defaultValue={venueEditId ? selectedVenue?.name : ''} required minLength="3" maxLength="120"/></label><label>Endereço ou bairro<input name="address" defaultValue={venueEditId ? selectedVenue?.address : ''} maxLength="240"/></label><div className="form-row"><label>Latitude<input name="latitude" type="number" step="any" min="-90" max="90" defaultValue={venueEditId ? selectedVenue?.latitude : ''} required/></label><label>Longitude<input name="longitude" type="number" step="any" min="-180" max="180" defaultValue={venueEditId ? selectedVenue?.longitude : ''} required/></label></div><div className="edit-form-actions"><button className="button button-green" disabled={busy}>{busy ? 'Salvando…' : 'Salvar campo'} <Check size={15}/></button><button type="button" className="text-action" onClick={() => { setVenueFormOpen(false); setVenueEditId(null) }}>Cancelar</button></div></form>}
        <div className="venue-layout"><div className="venue-list">{pagedVenues.length ? pagedVenues.map((venue, index) => <button key={venue.id} className={`venue-card ${selectedVenue?.id === venue.id ? 'selected' : ''}`} onClick={() => setSelectedVenue(venue)}><span className="venue-number">{String(venueStartIndex + index + 1).padStart(2, '0')}</span><span className="venue-info"><b>{venue.name}</b><small><MapPin size={13}/>{venue.address || `${venue.city}, ${venue.region}`}</small><small className="venue-source">{venue.source === 'demo' ? 'Dado demonstrativo' : venue.source === 'manual' ? 'Informado pela comunidade' : 'OpenStreetMap'} · {venue.upcoming_matches} partidas futuras</small></span><ArrowUpRight size={17}/></button>) : <div className="empty-state">Nenhum campo encontrado. Tente outro termo.</div>}
          <div className="osm-credit"><ShieldCheck size={14}/> Dados do mapa: © OpenStreetMap contributors</div><div className="venue-pagination"><span className="pagination-summary">{filteredVenues.length ? `${venueStartIndex + 1}–${Math.min(venueStartIndex + VENUES_PER_PAGE, filteredVenues.length)} de ${filteredVenues.length} campos` : '0 campos'}</span><div className="pagination-controls" aria-label="Paginação dos campos"><button className="page-arrow" aria-label="Página anterior" disabled={venuePage === 1} onClick={() => setVenuePage(page => Math.max(1, page - 1))}><ChevronLeft size={15}/></button>{pageNumbers.map((page, index) => page === '…' ? <span className="page-ellipsis" key={`ellipsis-${index}`}>…</span> : <button key={page} className={`page-number ${page === venuePage ? 'active' : ''}`} aria-current={page === venuePage ? 'page' : undefined} onClick={() => setVenuePage(page)}>{page}</button>)}<button className="page-arrow" aria-label="Próxima página" disabled={venuePage === totalVenuePages} onClick={() => setVenuePage(page => Math.min(totalVenuePages, page + 1))}><ChevronRight size={15}/></button></div></div></div>
          <div className="venue-detail">{selectedVenue ? <><div className="detail-top"><div><span className="tiny-kicker">CAMPO SELECIONADO</span><h3>{selectedVenue.name}</h3><p><MapPin size={14}/>{selectedVenue.address || `${selectedVenue.city}, ${selectedVenue.region}`}</p></div><span className="detail-icon"><Compass size={22}/></span></div><div className="map-preview"><iframe title={`Mapa de ${selectedVenue.name}`} loading="lazy" src={`https://www.openstreetmap.org/export/embed.html?bbox=${selectedVenue.longitude - 0.012},${selectedVenue.latitude - 0.008},${selectedVenue.longitude + 0.012},${selectedVenue.latitude + 0.008}&layer=mapnik&marker=${selectedVenue.latitude},${selectedVenue.longitude}`}/><div className="map-credit">© OpenStreetMap contributors</div></div><a className="map-link" href={`https://www.openstreetmap.org/?mlat=${selectedVenue.latitude}&mlon=${selectedVenue.longitude}#map=16/${selectedVenue.latitude}/${selectedVenue.longitude}`} target="_blank" rel="noreferrer">Abrir no mapa <ArrowUpRight size={15}/></a><div className="detail-foot"><span>COORDENADAS</span><code>{Number(selectedVenue.latitude).toFixed(4)}, {Number(selectedVenue.longitude).toFixed(4)}</code></div></> : <div className="empty-state">Carregando campos…</div>}</div></div>
      </section>

      <section className="matches-section" id="partidas"><div className="section-heading match-heading"><div><span className="tiny-kicker">BORA JOGAR?</span><h2>Partidas abertas<span className="heading-dot">.</span></h2><p>Confirme presença e complete o time.</p></div><div className="match-count"><span className="pulse-dot"/> {matches.length} {matches.length === 1 ? 'partida marcada' : 'partidas marcadas'}</div></div><div className="match-grid">{matches.map((match, i) => { const isGoing = person && match.attendees.some(name => name.toLowerCase() === person.toLowerCase()); const full = match.attendee_count >= match.capacity; const weather = forecast[match.id]; return <article className="match-card" key={match.id}><div className="match-card-head"><span className="match-tag"><span className="pulse-dot"/> JOGO ABERTO</span><span className="match-number">JOGO Nº {String(i + 1).padStart(2, '0')}</span></div><h3>{match.title}</h3><div className="match-meta"><span><CalendarDays size={15}/>{dateLabel(match.starts_at)}</span><span><MapPin size={15}/>{match.venue_name}</span></div><div className="match-capacity"><div><span>VAGAS PREENCHIDAS</span><b>{capacityLabel(match)} <small>jogadores</small></b></div><div className="capacity-track"><i style={{ width: `${Math.min(100, match.attendee_count / match.capacity * 100)}%` }}/></div></div><div className="match-people"><div className="avatar-stack">{match.attendees.slice(0, 4).map((name, j) => <span key={`${name}-${j}`} title={name} className={`mini-avatar color-${j}`}>{name[0].toUpperCase()}</span>)}{match.attendee_count > 4 && <span className="more-people">+{match.attendee_count - 4}</span>}</div><span>{match.attendee_count} confirmados</span></div><div className="weather-box">{weather?.value ? <><CloudSun size={17}/><span><b>{weather.value.forecast.temperature_2m ?? '—'}{weather.value.units.temperature_2m || '°C'}</b> · chance de chuva {weather.value.forecast.precipitation_probability ?? '—'}%</span><small>Open-Meteo · {dateLabel(weather.value.fetched_at, false)}</small></> : weather?.loading ? <><CloudSun size={17}/><span>Consultando previsão…</span></> : weather?.error ? <><CloudSun size={17}/><span>Previsão indisponível</span><small>{weather.error}</small><button className="weather-load" onClick={() => loadForecast(match)}>Tentar novamente</button></> : <button className="weather-load" onClick={() => loadForecast(match)}><CloudSun size={17}/> Ver previsão do tempo</button>}</div><div className="match-actions">{isGoing ? <button disabled={busy} className="button button-outline" onClick={() => attendance(match, 'leave')}><Check size={16}/> Presença confirmada · sair</button> : <button disabled={busy || full} className="button button-dark full-width" onClick={() => attendance(match, 'join')}>{full ? 'Partida lotada' : 'Quero jogar'} <ArrowUpRight size={16}/></button>}</div><div className="organizer-note">Organiza {match.organizer_name} · confirme a disponibilidade do campo diretamente.</div></article> })}{!matches.length && <div className="empty-state match-empty">Ainda não há partidas abertas. Crie a primeira!</div>}</div></section>

      <section className="bottom-grid"><div className="create-card" id="new-match"><div className="create-icon"><Plus size={20}/></div><span className="tiny-kicker">TODO JOGO COMEÇA COM ALGUÉM</span><h2>Chama a galera<br/>pro campo.</h2><p>Marque o horário, escolha o lugar e deixa o time se formar.</p><button className="button button-dark" onClick={() => setFormOpen(open => !open)}>{formOpen ? 'Fechar formulário' : 'Marcar uma partida'} <ArrowUpRight size={16}/></button>{formOpen && <form className="match-form" onSubmit={createMatch}><label>Nome do jogo<input name="title" placeholder="Ex.: Racha de sábado" minLength="3" maxLength="100" required/></label><label>Campo<select name="venue_id" required value={selectedVenue?.id || ''} onChange={e => setSelectedVenue(venues.find(v => v.id === Number(e.target.value)))}>{venues.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}</select></label><div className="form-row"><label>Data e horário<input name="starts_at" type="datetime-local" min={localDateInput(Date.now() + 3600000)} max={localDateInput(Date.now() + 7 * 86400000)} required/></label><label>Vagas<select name="capacity" defaultValue="10">{[6,8,10,12,14,16,18,20,22,24,26,28,30].map(n => <option key={n}>{n}</option>)}</select></label></div><button className="button button-green full-width" disabled={busy} type="submit">{busy ? 'Salvando…' : 'Criar partida'} <ArrowUpRight size={16}/></button></form>}</div>
        <div className="profile-card" id="profile"><span className="tiny-kicker">QUEM VAI JOGAR?</span><h2>Seu nome<br/>no time.</h2><p>Sem conta ou senha. Use o mesmo nome para confirmar presença e sair de uma partida.</p><label className="profile-input">Nome de exibição<input value={nameInput} maxLength={50} minLength={2} onChange={e => setNameInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && rememberName()} placeholder="Como a galera te chama?"/></label><button className="button button-green full-width" onClick={rememberName}>{person ? 'Atualizar meu nome' : 'Salvar meu nome'} <Check size={16}/></button><div className="privacy-note"><ShieldCheck size={14}/> Salvo apenas neste navegador e nas confirmações de presença.</div></div></section>
    </main>
    <footer className="footer"><a className="brand" href="#top"><span className="brand-mark">FB</span><span>futebol<span className="brand-light"> de bairro</span></span></a><span>Feito para quem acredita que todo mundo merece jogar. ⚽</span><span>Dados de mapa © OpenStreetMap</span></footer>
  </div>
}

export default App
