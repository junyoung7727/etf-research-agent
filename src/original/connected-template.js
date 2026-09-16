import { Capacitor } from '@capacitor/core'

export function connectedTemplate(html) {
  html=html.replace('데모 · 예시 시세·분석·커뮤니티','{{ apiLabel }}')
  if(Capacitor.isNativePlatform()) html=html.replace('width: 402px; height: 874px; border-radius: 44px;','width: 100vw; height: 100dvh; border-radius: 0;').replace('box-shadow: 0 24px 70px rgba(0,0,0,0.18);','box-shadow: none;')
  const content=`
<sc-if value="{{ agentBubbleOn }}"><button data-api-agent aria-label="ETF AI에게 질문" onClick="{{ openAgent }}" style="position: absolute; right: 20px; bottom: {{ agentBottom }}; z-index: 29; width: 48px; height: 48px; border: none; border-radius: 50%; background: #3D34E0; color: #FFFFFF; font: 800 15px Pretendard; box-shadow: 0 4px 18px rgba(61,52,224,0.2); cursor: pointer;">AI</button></sc-if>
<sc-if value="{{ agentOpen }}">
  <div onClick="{{ closeAgent }}" style="position: absolute; inset: 0; z-index: 89; background: rgba(0,0,0,0.4); animation: fadeIn 0.2s ease both;"></div>
  <div data-screen-label="ETF AI 대화" style="position: absolute; left: 0; right: 0; bottom: 0; z-index: 90; height: 82%; display: flex; flex-direction: column; border-radius: 22px 22px 0 0; background: #FFFFFF; padding: 10px 20px 24px; font-family: Pretendard,sans-serif; animation: sheetUp 0.28s cubic-bezier(0.32,0.72,0,1);">
    <dc-import name="SheetHead" hint-size="100%,60px" title="ETF AI" sub="{{ agentSub }}"></dc-import>
    <button onClick="{{ closeAgent }}" aria-label="대화 닫기" style="position: absolute; right: 20px; top: 24px; border: none; background: #F2F4F6; border-radius: 50%; width: 30px; height: 30px; font: 18px Pretendard; cursor: pointer;">×</button>
    <div id="agentScroll" style="flex: 1; min-height: 0; overflow-y: auto; padding: 16px 0;">
      <sc-for list="{{ agentMsgs }}" as="m"><div style="display: flex; justify-content: {{ m.justify }}; margin-bottom: 12px;"><div style="max-width: 90%; padding: 13px 15px; border-radius: {{ m.radius }}; background: {{ m.bg }}; color: {{ m.c }}; font-size: 14px; line-height: 1.65; white-space: pre-line; overflow-wrap: anywhere;">{{ m.text }}</div></div></sc-for>
      <sc-if value="{{ agentThinking }}"><div role="status" style="font-size: 13px; color: #6B7684; padding: 12px;">근거를 확인하고 있어요…</div></sc-if>
      <sc-for list="{{ apiChatSources }}" as="source"><div style="font-size: 12px; line-height: 1.6; margin: 8px 0;"><sc-if value="{{ source.linked }}"><a href="{{ source.url }}" target="_blank" rel="noopener noreferrer">{{ source.title }}</a></sc-if><sc-if value="{{ !source.linked }}"><span>{{ source.title }}</span></sc-if></div></sc-for>
      <sc-if value="{{ agentShowQuick }}"><sc-for list="{{ agentQuick }}" as="q"><button data-q="{{ q.q }}" onClick="{{ agentAskQuick }}" style="display: block; margin: 8px 0; border: 1px solid #E5E8EB; background: #FFFFFF; border-radius: 12px; padding: 10px 12px; font: 13px Pretendard; text-align: left; cursor: pointer;">{{ q.label }}</button></sc-for></sc-if>
    </div>
    <div style="display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid #E5E8EB;"><textarea aria-label="ETF 질문" maxLength="1000" rows="2" value="{{ agentDraft }}" onChange="{{ onAgentDraft }}" placeholder="{{ agentPlaceholder }}" style="flex: 1; min-width: 0; resize: none; border: none; border-radius: 12px; background: #F2F4F6; padding: 12px; font: 14px/1.5 Pretendard;"></textarea><button onClick="{{ agentSend }}" disabled="{{ agentThinking }}" style="border: none; border-radius: 12px; padding: 12px; background: {{ agentSendBg }}; color: #FFFFFF; font: 700 13px Pretendard; cursor: pointer;">전송</button></div>
  </div>
</sc-if>
<sc-if value="{{ apiHasError }}">
  <div data-api-error style="position: fixed; top: 76px; left: 16px; right: 16px; z-index: 110; background: #FFF3F4; border: 1px solid #F8CED3; border-radius: 14px; padding: 12px 14px; color: #B81E2B; font: 13px/1.5 Pretendard, sans-serif;">
    {{ apiError }} <button onClick="{{ apiRetry }}" style="border: none; background: transparent; color: #3D34E0; font: inherit; font-weight: 800; cursor: pointer;">다시 시도</button>
  </div>
</sc-if>
<sc-if value="{{ apiReportOpen }}">
  <div onClick="{{ apiCloseReport }}" style="position: absolute; inset: 0; z-index: 100; background: rgba(0,0,0,0.4); animation: fadeIn 0.2s ease both;"></div>
  <div data-screen-label="연결된 분석" style="position: absolute; left: 0; right: 0; bottom: 0; max-height: 86%; overflow-y: auto; z-index: 101; border-radius: 22px 22px 0 0; background: #FFFFFF; padding: 10px 20px 30px; font-family: Pretendard, sans-serif; animation: sheetUp 0.28s cubic-bezier(0.32,0.72,0,1);">
    <dc-import name="SheetHead" hint-size="100%,60px" title="분석과 출처" sub="{{ apiReportDate }}"></dc-import>
    <div style="display: flex; gap: 8px; margin: 10px 0 20px;"><sc-for list="{{ apiReportDates }}" as="d"><button data-ari="{{ d.index }}" onClick="{{ apiSelectReport }}" style="border: none; border-radius: 10px; padding: 10px 12px; background: {{ d.bg }}; color: {{ d.c }}; font: 700 13px Pretendard; cursor: pointer;">{{ d.label }}</button></sc-for></div>
    <h2 style="font-size: 24px; font-weight: 800; line-height: 1.38; letter-spacing: -0.03em; color: #191F28;">{{ apiReportTitle }}</h2>
    <p style="font-size: 15px; line-height: 1.7; color: #333D4B; white-space: pre-line; margin: 16px 0 22px;">{{ apiReportSummary }}</p>
    <sc-for list="{{ apiReportFactors }}" as="f"><div style="padding: 16px; background: #F7F8FA; border-radius: 16px; margin-bottom: 12px;">
      <b style="font-size: 17px;">{{ f.label }}</b><p style="font-size: 14px; line-height: 1.6; margin-top: 8px; color: #4E5968;">{{ f.explanation }}</p>
      <sc-for list="{{ f.metrics }}" as="m"><div style="display: flex; justify-content: space-between; gap: 12px; margin-top: 10px; font-size: 13px;"><span>{{ m.label }}</span><b>{{ m.display }}</b></div></sc-for>
    </div></sc-for>
    <sc-for list="{{ apiReportSources }}" as="source"><div style="padding: 14px 0; border-top: 1px solid #E5E8EB; font-size: 13px; line-height: 1.6;"><sc-if value="{{ source.linked }}"><a href="{{ source.url }}" target="_blank" rel="noopener noreferrer">{{ source.title }}</a></sc-if><sc-if value="{{ !source.linked }}"><span>{{ source.title }}</span></sc-if><p style="color: #6B7684; margin-top: 6px;">{{ source.excerpt }}</p></div></sc-for>
    <p style="color: #B81E2B; font-size: 13px;">{{ apiAnalysisError }}</p>
    <dc-import name="CtaButton" hint-size="100%,54px" label="{{ apiAnalysisLabel }}" disabled="{{ apiAnalysisDisabled }}" on-click="{{ apiRunAnalysis }}"></dc-import>
    <button onClick="{{ apiCloseReport }}" style="display: block; width: 100%; border: none; padding: 14px; margin-top: 10px; border-radius: 12px; background: #F2F4F6; font: 700 14px Pretendard; cursor: pointer;">닫기</button>
  </div>
</sc-if>`
  // Insert inside the 402×874 device, before its enclosing wrappers close.
  const anchor='<sc-if value="{{ postOpen }}">'
  if(!html.includes(anchor))throw new Error('Original overlay anchor missing')
  html=html.replace(anchor,content+anchor)
  const brief='<sc-if value="{{ isStockBrief }}" hint-placeholder-val="{{ true }}">'
  if(!html.includes(brief))throw new Error('Original analysis entry missing')
  html=html.replace(brief,brief+`<div style="margin: 12px 20px 0;"><dc-import name="LinkRow" hint-size="100%,48px" label="연결된 분석·출처" variant="accent" on-click="{{ apiOpenReport }}"></dc-import><p style="font-size: 12px; line-height: 1.5; color: #6B7684; margin-top: 8px;">{{ apiDetailNote }}</p><sc-if value="{{ apiDetailFailed }}"><button onClick="{{ apiDetailRetry }}" style="padding: 10px; border: none; border-radius: 10px; color: #3D34E0; background: #F2F4F6; font: 700 13px Pretendard;">자료 다시 불러오기</button></sc-if></div>`)
  return html
}
