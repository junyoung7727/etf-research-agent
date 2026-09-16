// Package the user's original components without evaluating downloaded code at runtime.
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))
const out = path.join(root, 'src/original/generated')
await mkdir(out, { recursive: true })
const source = path.join(root, 'original')
const runtime = await readFile(path.join(source, 'support.js'), 'utf8')
function slice(start, end) {
  const a = runtime.indexOf(start), b = runtime.indexOf(end, a + start.length)
  if (a < 0 || b < 0) throw new Error(`Original runtime section missing: ${start}`)
  return runtime.slice(a, b)
}
const vendor = [
  `// Generated from original/support.js. Preserve the original renderer's layout and lifecycle.\nimport React from 'react'\nconst getReact = () => React\nconst h = (...args) => React.createElement(...args)\n`,
  slice('  var __defProp', '  // src/react.ts'),
  slice('  var BASE_CSS', '  function rootNameForDocument'),
  slice('  // src/expr.ts', '  function evalDcLogic'),
  slice('  // src/component.ts', '  // src/bundled.ts'),
  slice('  // src/pseudo.ts', '  // src/runtime.ts'),
  '\nexport { StreamableLogic as DCLogic, createComponentFactory, createRegistry, createPseudoSheet, compileTemplate, BASE_CSS, FULL_PAGE_CSS };\n',
].join('\n').replace('el = doc.createElement("style");', 'el = doc.createElement("style"); el.nonce = doc.querySelector(\'meta[name="style-nonce"]\')?.content || "";')
if (/new Function\s*\(|\beval\s*\(/.test(vendor)) throw new Error('Dynamic code execution remains in packaged renderer')
await writeFile(path.join(out, 'runtime.js'), vendor)

const unescape = s => s.replace(/&(quot|amp|lt|gt|apos);/g, (_, n) => ({quot:'"',amp:'&',lt:'<',gt:'>',apos:"'"})[n])
const photos = JSON.parse(await readFile(path.join(source,'image-manifest.json'),'utf8'))
for (const asset of Object.values(photos)) {
  if (!/^photo-\d+\.(avif|webp|jpg|png)$/.test(asset.file)) throw new Error('Unexpected original asset filename')
  const bytes = await readFile(path.join(root,'public/original-assets',asset.file))
  if (createHash('sha256').update(bytes).digest('hex') !== asset.sha256) throw new Error(`Original asset hash changed: ${asset.file}`)
}
const localize = s => s.replace(/https:\/\/images\.unsplash\.com\/photo-([^?'"\s]+)\?[^'"\s]+/g, (url, id) => {
  if (photos[id]) return `/original-assets/${photos[id].file}`
  throw new Error(`Unmapped original photo: ${url}`)
})
const entries = [], manifest = []
const files = (await readdir(source)).filter(f => f.endsWith('.dc.html')).sort()
for (const file of files) {
  const raw = await readFile(path.join(source, file), 'utf8')
  const name = file.replace('.dc.html', '')
  const key = file.startsWith('MarketBrew App ') ? 'App' : name
  const templateMatch = raw.match(/<x-dc[^>]*>([\s\S]*?)<\/x-dc>/)
  const scriptMatch = [...raw.matchAll(/<script\b((?:"[^"]*"|'[^']*'|[^'">])*)>([\s\S]*?)<\/script>/g)].find(m => m[1].includes('data-dc-script'))
  if (!templateMatch) throw new Error(`Incomplete original component: ${file}`)
  const encodedProps = scriptMatch?.[1].match(/data-props="([^"]*)"/)?.[1]
  const metadata = encodedProps ? JSON.parse(unescape(encodedProps)) : {}
  const { $preview, ...propsMeta } = metadata
  // Font and asset files are bundled; the source HTML is retained byte for byte.
  const html = localize(templateMatch[1].replace(/<link\b[^>]*>/g, ''))
  const logic = localize(scriptMatch?.[2] ?? 'class Component extends DCLogic {}').replace('class Component extends DCLogic', 'export default class Component extends DCLogic')
  if (!logic.includes('export default class Component')) throw new Error(`Unexpected component class: ${file}`)
  await writeFile(path.join(out, `${key}.js`), `// Generated from original/${file}\nimport { DCLogic } from './runtime.js'\n${logic}`)
  entries.push({key,html,propsMeta,preview:$preview})
  manifest.push({ file, sha256: createHash('sha256').update(raw).digest('hex') })
}
const imports = entries.map((e,i)=>`import Logic${i} from './${e.key}.js'`).join('\n')
const modules = entries.map((e,i)=>`${JSON.stringify(e.key)}: { ...${JSON.stringify(e)}, Logic: Logic${i} }`).join(',\n')
await writeFile(path.join(out, 'modules.js'), `${imports}\nexport default {\n${modules}\n}\n`)
await writeFile(path.join(root,'original/source-manifest.json'),JSON.stringify({source:'MarketBrew-clean',files:manifest,runtimeSha256:createHash('sha256').update(runtime).digest('hex')},null,2)+'\n')
console.log(`Packaged ${entries.length} original components; renderer has no eval/Function constructor.`)
