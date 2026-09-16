import { communityPreferences, communityState } from './community.js'

const key = 'edge.original.preferences.v1'
const excludedScreens = new Set(['signup', 'notis', 'profile'])

// Remove whole conditional branches while preserving all other source bytes.
function withoutBranches(html, names) {
  let start = -1, depth = 0, end = 0, result = ''
  for (const match of html.matchAll(/<\/?sc-if\b[^>]*>/g)) {
    const closing = match[0].startsWith('</')
    if (start < 0) {
      const condition = match[0].match(/value="\{\{\s*([^}]+?)\s*\}\}"/)?.[1]
      if (!closing && names.has(condition)) { start = match.index; depth = 1 }
    } else {
      depth += closing ? -1 : 1
      if (depth === 0) { result += html.slice(end, start); end = match.index + match[0].length; start = -1 }
    }
  }
  if (start >= 0) throw new Error('Unbalanced excluded original branch')
  return result + html.slice(end)
}

export function demoTemplate(html) {
  html = withoutBranches(html, new Set([
    'isSignup','isNotis','isProfile','loggedIn','loggedOut',
  ]))
  html = html.replace(/<dc-import\b(?=[^>]*name="IconButton")(?=[^>]*icon="bell")[^>]*><\/dc-import>/g, '')
  const menu = '<sc-for list="{{ menuGroups }}"'
  if (!html.includes(menu)) throw new Error('Original menu boundary changed')
  html = html.replace(menu, `<div style="padding: 0 20px 24px; display: flex; flex-direction: column; gap: 10px;">
    <label for="local-name" style="font-size: 22px; font-weight: 800; letter-spacing: -0.03em;">내 설정</label>
    <input id="local-name" value="{{ localName }}" onChange="{{ onLocalName }}" placeholder="내 이름" maxLength="20" style="background: #F2F4F6; padding: 12px 14px; border-radius: 12px; font: inherit;">
    <span style="font-size: 13px; color: #8B95A1;">관심 목록과 설정은 이 기기에 저장돼요.</span>
  </div>${menu}`)
  // The original's market prices and analysis are design fixtures, including animated ticks.
  const strip = 'pointer-events: none;"></div>'
  if (!html.includes(strip)) throw new Error('Original status strip changed')
  return html.replace(strip, 'pointer-events: none;"><span data-demo-label style="position: absolute; left: 20px; top: 23px; font-size: 11px; font-weight: 500; color: #8B95A1;">데모 · 예시 시세·분석·커뮤니티</span></div>')
}

function preferences(s) {
  return {
    ...communityPreferences(s),
    onboarded: !!s.localOnboarded, meNick: s.meNick || '', watch: s.watch || [],
    themeWatch: s.themeWatch || [], wGroupList: s.wGroupList || [],
    watchGroup: s.watchGroup || 'all', storySeen: s.storySeen || {},
  }
}

function readPreferences(allowed) {
  const raw = localStorage.getItem(key)
  if (!raw) return null
  if (raw.length > 2_000_000) throw new Error('preferences too large')
  const p = JSON.parse(raw)
  if (!p || typeof p !== 'object' || Array.isArray(p)) throw new Error('invalid preferences')
  const strings = (a, limit = 50) => Array.isArray(a) ? [...new Set(a.filter(x => typeof x === 'string' && x.length <= 80))].slice(0, limit) : []
  const watch = strings(p.watch).filter(x => allowed.has(x))
  const wGroupList = (Array.isArray(p.wGroupList) ? p.wGroupList : []).slice(0, 20)
    .filter(g => g && typeof g.id === 'string' && /^[\w-]{1,80}$/.test(g.id) && typeof g.name === 'string')
    .map(g => ({ id:g.id,name:g.name.slice(0,20),keys:strings(g.keys).filter(x => watch.includes(x)) }))
  return {
    ...communityState(p,allowed),
    localOnboarded:p.onboarded === true, meNick:typeof p.meNick === 'string' ? p.meNick.slice(0,20) : '',
    watch, themeWatch:strings(p.themeWatch,20), wGroupList,
    watchGroup:wGroupList.some(g => g.id === p.watchGroup) ? p.watchGroup : 'all',
    storySeen:Object.fromEntries(Object.entries(p.storySeen || {}).filter(([k,v]) => allowed.has(k) && (typeof v === 'boolean' || typeof v === 'string'))),
  }
}

export function demoLogic(Original) {
  return class Demo extends Original {
    async agentAsk(q) {
      if (this.state.agentBusy) return
      const text = String(q).trim().slice(0,2000)
      if (!text) return
      const prev = this.state.agentMsgs || [{role:'assistant',text:this.agentContext(this.state).hello}]
      this.setState({agentDraft:'',agentBusy:false,agentMsgs:[...prev,
        {role:'user',text},
        {role:'assistant',text:'예시 답변입니다. ' + this.agentFallback(this.state,text)},
      ]},()=>this.agentScrollEnd())
    }
    componentDidMount() {
      super.componentDidMount()
      try {
        const saved = readPreferences(new Set(Object.keys(this.ETFS)))
        if (saved) this.setState({...saved,screen:saved.localOnboarded ? 'home' : 'onboarding'})
      } catch { this.setState({localStorageError:'저장된 설정을 읽지 못했어요. 현재 선택은 새로 시작해요.'}) }
      this._localReady = true
    }
    setState(update, cb) {
      const patch = typeof update === 'function' ? update(this.state) : update
      const next = {...this.state,...patch}
      if (excludedScreens.has(next.screen)) next.screen = 'home'
      if (this.state.screen === 'onboarding' && this.state.obStep === 5 && next.screen === 'home') next.localOnboarded = true
      if (this._localReady && JSON.stringify(preferences(next)) !== JSON.stringify(preferences(this.state))) {
        try { localStorage.setItem(key,JSON.stringify(preferences(next))) }
        catch { next.localStorageError = '이 기기에 저장하지 못했어요. 새로고침하면 선택이 사라질 수 있어요.' }
      }
      super.setState(next, cb)
    }
    renderVals() {
      const vals = super.renderVals()
      return {
        ...vals,
        localName:this.state.meNick || '',
        onLocalName:e => this.setState({meNick:e.target.value.slice(0,20)}),
        onMeNick:e => this.setState({meNick:e.target.value.slice(0,20)}),
        onMeHandle:e => this.setState({meHandle:e.target.value.slice(0,32)}),
        onReplyDraft:e => this.setState({replyDraft:e.target.value.slice(0,280)}),
        menuGroups:vals.menuGroups.map(g => ({...g,items:g.items.filter(i => !['notis','signup'].includes(i.go))})).filter(g => g.items.length),
        sumToast:this.state.localStorageError || vals.sumToast,
        sumToastOn:!!this.state.localStorageError || vals.sumToastOn,
      }
    }
  }
}
