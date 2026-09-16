import { Capacitor } from '@capacitor/core'
import { App } from '@capacitor/app'

// Navigation stays in the bundled UI; native HTTP only receives an HTTPS API origin.
if(Capacitor.isNativePlatform()) {
  void App.addListener('backButton',()=>{
    const app=(window as any).__app
    if(!app)return
    const s=app.state
    if(s.apiReportOpen)app.setState({apiReportOpen:false})
    else if(s.agentOpen)app.setState({agentOpen:false})
    else if(s.postId)app.setState({postId:null})
    else if(s.commWriteOpen)app.setState({commWriteOpen:false})
    else if(s.daSheet)app.setState({daSheet:false})
    else if(s.themeSheet)app.setState({themeSheet:null})
    else if(s.story)app.setState({story:null})
    else if(s.menuOpen)app.setState({menuOpen:false})
    else if(!['home','onboarding'].includes(s.screen))app.setState({screen:'home'})
    else void App.minimizeApp()
  })
}
