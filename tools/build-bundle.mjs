import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { sites } from '@openai/sites-vite-plugin'
import { mkdir, readFile, writeFile, rename } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root=fileURLToPath(new URL('../',import.meta.url))
process.chdir(root)
const target=process.argv[2]
if(!['mobile','site'].includes(target))throw new Error('Use mobile or site')
const origin=process.env.EDGE_API_ORIGIN||''
if(origin && (!origin.startsWith('https://')||new URL(origin).origin!==origin))throw new Error('EDGE_API_ORIGIN must be an HTTPS origin without a path')
if(target==='site' && origin)throw new Error('The public Site is a labelled, key-free demo. Deploy the full Docker server for live mode.')
execFileSync(process.execPath,['tools/build-original.mjs'],{stdio:'inherit'})
const outDir=target==='mobile'?'dist-mobile':'dist/client'
await build({configFile:false,plugins:[react(),...(target==='site'?[sites()]:[])],define:{
  'import.meta.env.VITE_EDGE_BUNDLED_DEMO':JSON.stringify(origin?'0':'1'),
  'import.meta.env.VITE_EDGE_API_BASE':JSON.stringify(origin),
  'import.meta.env.VITE_EDGE_ALLOW_SOURCE_FIXTURE':JSON.stringify('0'),
},build:{outDir,reportCompressedSize:false,rolldownOptions:{input:{original:'original.html'}}}})
await rename(path.join(outDir,'original.html'),path.join(outDir,'index.html'))
if(target==='site') {
  await mkdir('dist/server',{recursive:true})
  await writeFile('dist/server/index.js',await readFile('hosting/worker.js','utf8'))
}
console.log(`${target} bundle ready; mode=${origin?'server connection':'explicit offline demo'}`)
