import type { CapacitorConfig } from '@capacitor/cli'

const config:CapacitorConfig={
  appId:'com.marketbrew.edge',
  appName:'EDGE',
  webDir:'dist-mobile',
  backgroundColor:'#FAFAF8',
  server:{androidScheme:'https'},
  android:{allowMixedContent:false,webContentsDebuggingEnabled:false},
  ios:{contentInset:'automatic',allowsLinkPreview:false},
}
export default config
