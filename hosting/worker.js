// Sites serves static assets through ASSETS. This deployment contains no keys.
export default {
  async fetch(request,env) {
    const url=new URL(request.url)
    if(request.method!=='GET' && request.method!=='HEAD')return new Response('Method not allowed',{status:405})
    if(url.pathname==='/api/health')return Response.json({ok:true,dataMode:'DEMO',providersConnected:false})
    if(url.pathname==='/original')url.pathname='/'
    let response=await env.ASSETS.fetch(new Request(url,request))
    const headers=new Headers(response.headers)
    headers.set('X-Content-Type-Options','nosniff')
    headers.set('Referrer-Policy','no-referrer')
    headers.set('Permissions-Policy','camera=(), microphone=(), geolocation=()')
    if(headers.get('Content-Type')?.includes('text/html')) {
      const nonce=btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(24))))
      const html=(await response.text()).replace('<head>',`<head><meta name="style-nonce" content="${nonce}">`)
      headers.set('Content-Security-Policy',`default-src 'self'; script-src 'self'; style-src 'self' 'nonce-${nonce}'; style-src-attr 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'`)
      headers.set('Cache-Control','no-store')
      headers.delete('Content-Length');headers.delete('ETag')
      return new Response(html,{status:response.status,headers})
    }
    return new Response(response.body,{status:response.status,headers})
  },
}
