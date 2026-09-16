import React from 'react'
import { createRoot } from 'react-dom/client'
// Original component classes are packaged as JavaScript, with no runtime eval.
// @ts-expect-error generated original JavaScript
import modules from './generated/modules.js'
// @ts-expect-error original renderer adapter
import { createOriginalApp } from './renderer.js'
// @ts-expect-error source-preserving demo adapter
import { demoTemplate, demoLogic } from './demo.js'
// @ts-expect-error source adapter uses the original JavaScript component interface
import { connectedLogic, connectedTicker } from './connected.js'
// @ts-expect-error source template adapter
import { connectedTemplate } from './connected-template.js'
import 'pretendard/dist/web/static/pretendard.css'
import './fonts.css'
import './native'

// Fixture mode is for comparing the packaged renderer against the untouched source.
const fixture = new URLSearchParams(location.search).get('fixture') === 'original'
if (!fixture) {
  modules.App = {...modules.App,html:connectedTemplate(demoTemplate(modules.App.html)),Logic:connectedLogic(demoLogic(modules.App.Logic))}
  modules.LiveTicker = {...modules.LiveTicker,Logic:connectedTicker(modules.LiveTicker.Logic)}
}
const App = createOriginalApp(modules)
createRoot(document.getElementById('dc-root')!).render(<App />)
