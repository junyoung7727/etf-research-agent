// Community is a device-local demo. No post or reaction is sent to another visitor.
const record = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {}
const entries = value => Object.entries(record(value)).filter(([key]) => /^[\w-]{1,100}$/.test(key)).slice(0,500)
const text = (value, length) => typeof value === 'string' ? value.slice(0,length) : ''

export function communityState(value, allowed) {
  const p = record(value)
  const reactions = field => Object.fromEntries(entries(p[field]).filter(([,v]) => v === true))
  const quote = value => {
    const q = record(value)
    return /^[\w-]{1,100}$/.test(q.id || '') && (q.etf === '' || allowed.has(q.etf)) ? {id:q.id,etf:q.etf} : null
  }
  return {
    commMine:Object.fromEntries(entries(p.commMine).filter(([k,v]) => (k === '_none' || allowed.has(k)) && Array.isArray(v))
      .map(([k,posts]) => [k,posts.slice(0,100).filter(post => post && typeof post.body === 'string' && Number.isSafeInteger(post.at) && post.at > 0)
        .map(post => ({body:text(post.body,280),at:post.at,mirror:post.mirror === true,quoteOf:quote(post.quoteOf),
          tags:Array.isArray(post.tags) ? [...new Set(post.tags.filter(k => allowed.has(k)))].slice(0,3) : []}))])),
    postReplies:Object.fromEntries(entries(p.postReplies).filter(([,v]) => Array.isArray(v))
      .map(([id,replies]) => [id,replies.slice(0,100).filter(r => r && typeof r.body === 'string').map(r => ({body:text(r.body,280)}))])),
    commLikes:reactions('commLikes'), commReposts:reactions('commReposts'),
    pollVotes:Object.fromEntries(entries(p.pollVotes).filter(([k,v]) => allowed.has(k) && ['buy','wait','sell'].includes(v))),
    meHandle:text(p.meHandle,32) || '@me',
    meAvBg:/^#[0-9a-fA-F]{6}$/.test(p.meAvBg || '') ? p.meAvBg : '#3D34E0',
  }
}

export function communityPreferences(s) {
  return Object.fromEntries(['commMine','postReplies','commLikes','commReposts','pollVotes','meHandle','meAvBg'].map(k => [k,s[k]]))
}
