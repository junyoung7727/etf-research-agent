import { BASE_CSS, FULL_PAGE_CSS, createComponentFactory, createRegistry, createPseudoSheet, compileTemplate } from './generated/runtime.js'

export function createOriginalApp(modules) {
  const registry = createRegistry()
  const style = document.createElement('style')
  const nonce = document.querySelector('meta[name="style-nonce"]')?.content || ''
  style.nonce = nonce
  style.textContent = BASE_CSS + FULL_PAGE_CSS
  document.head.append(style)
  const factory = createComponentFactory(registry, name => {
    if (!Object.hasOwn(modules, name)) throw new Error(`Missing packaged component: ${name}`)
  })
  const host = {
    component: name => factory.getDC(name),
    pseudoClass: createPseudoSheet(document),
    helmet: node => {
      for (const child of node.children) {
        if (child.localName !== 'style') throw new Error(`Unexpected external head element: ${child.localName}`)
        const css = document.createElement('style')
        css.nonce = nonce
        css.textContent = child.textContent
        document.head.append(css)
      }
      return () => null
    },
  }
  for (const [name, component] of Object.entries(modules)) {
    Object.assign(registry.get(name), {Logic:component.Logic,propsMeta:component.propsMeta,preview:component.preview,fetched:true,html:component.html})
  }
  for (const [name, component] of Object.entries(modules)) {
    registry.get(name).tpl = compileTemplate(component.html, host)
  }
  return factory.getDC('App')
}
