'use strict';
const $ = id => document.getElementById(id);
const escapeHtml = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state, token, selectedType = 'EventTypeCode', selectedCode = '', clean = '', dirty = false, saving = false, createMode;
const currentType = () => state?.catalog.valueTypes.find(t => t.id === selectedType);
const currentValue = () => currentType()?.values.find(v => v.code === selectedCode);
const message = text => { $('notice').textContent = text; $('notice').hidden = !text; };

async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST', headers:{'Content-Type':'application/json','X-Workbench-Token':token}, body:JSON.stringify(body)} : {});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `조회 실패 (${response.status})`);
  return payload;
}
function updateState() {
  dirty = JSON.stringify(state.catalog) !== clean;
  $('saveState').textContent = saving ? '저장 중…' : dirty ? '저장하지 않은 변경' : state.pendingCount ? `로컬 저장 v${state.revision}` : '라이브러리 원본';
  $('saveState').className = dirty ? 'changed' : '';
  $('save').disabled = saving || !dirty || state.sourceChanged;
  $('reload').disabled = saving;
  $('applyLibrary').disabled = saving || dirty || !state.pendingCount || state.sourceChanged;
  $('sourceState').textContent = `라이브러리 + 미반영 ${state.pendingCount || 0}개 · ${state.sourceChanged ? '원본 변경됨: 비교 필요' : '원본 일치'} · ${state.libraryPath}`;
}
async function load() {
  if (dirty && !confirm('저장하지 않은 변경을 버리고 최신 정의를 불러올까요?')) return;
  try {
    const [status, incoming] = await Promise.all([api('/api/status'), api('/api/value-types')]);
    token = status.token; state = incoming; clean = JSON.stringify(state.catalog);
    if (!currentType()) selectedType = state.catalog.valueTypes[0].id;
    if (!currentValue()) selectedCode = currentType().values[0]?.code || '';
    render();
    message(state.sourceChanged ? '원본이 변경되었습니다. 저장된 초안은 보존했습니다. JSON으로 내보낸 뒤 원본과 비교하세요.' : '');
  } catch (error) { message(error.message); $('saveState').textContent = '불러오기 실패'; }
}
function renderNavigation() {
  const query = $('typeSearch').value.toLowerCase();
  $('typeCount').textContent = state.catalog.valueTypes.length;
  $('typeList').innerHTML = state.catalog.valueTypes.filter(t => `${t.id} ${t.description}`.toLowerCase().includes(query)).map(t =>
    `<button class="type-item" data-type="${escapeHtml(t.id)}" aria-current="${t.id === selectedType}"><b>${escapeHtml(t.id)}</b><span class="count">${t.values.length}</span><small>String · Enum${t.id === 'EventTypeCode' ? ' · 스레드 규칙' : ''}</small></button>`).join('') || '<p class="empty">검색 결과가 없습니다.</p>';
}
function renderList() {
  const type = currentType(), query = $('valueSearch').value.toLowerCase(), group = $('groupFilter').value;
  const values = type.values.filter(v => (!group || v.group === group) && `${v.code} ${v.description}`.toLowerCase().includes(query));
  $('valueCount').textContent = `${values.length} / ${type.values.length}`;
  const scroll = $('valueList').scrollTop;
  $('valueList').innerHTML = values.map(v => `<button class="value-item" role="listitem" data-code="${escapeHtml(v.code)}" aria-current="${v.code === selectedCode}"><b>${escapeHtml(v.code)}</b><small>${escapeHtml(v.description || '원본 설명 없음 · 상세에서 작성 가능')}</small></button>`).join('') || '<p class="empty">검색 결과가 없습니다.</p>';
  $('valueList').scrollTop = scroll;
}
function render() {
  renderNavigation();
  const type = currentType();
  $('typeTitle').textContent = type.id;
  $('typeDescription').textContent = type.description;
  $('typeMeta').innerHTML = `<span class="badge">${escapeHtml(type.baseType)}</span><span class="badge">Enum · ${type.values.length} values</span>` + type.usedBy.map(p => `<span class="badge">관련 속성: ${escapeHtml(p)}</span>`).join('');
  const previousGroup = $('groupFilter').value;
  $('groupFilter').innerHTML = '<option value="">모든 분류</option>' + [...new Set(type.values.map(v => v.group).filter(Boolean))].sort().map(g => `<option>${escapeHtml(g)}</option>`).join('');
  if ([...$('groupFilter').options].some(o => o.value === previousGroup)) $('groupFilter').value = previousGroup;
  renderList(); renderEditor(); renderGraph(); updateState();
}
function renderEditor() {
  const type = currentType(), value = currentValue();
  let html = `<label for="typeDefinition">Value Type description · English</label><textarea id="typeDefinition" data-field="typeDescription" rows="2" maxlength="4000">${escapeHtml(type.description)}</textarea>`;
  if (!value) { $('editor').innerHTML = html + '<p class="empty">허용값을 추가하거나 선택하세요. 저장하려면 값이 하나 이상 필요합니다.</p>'; renderJson(); return; }
  html += `<label for="valueCode">허용값 코드</label><input id="valueCode" readonly value="${escapeHtml(value.code)}"><label for="valueDefinition">Value description · English</label><textarea id="valueDefinition" data-field="description" rows="3" maxlength="4000">${escapeHtml(value.description)}</textarea><label for="valueGroup">분류</label><input id="valueGroup" data-field="group" maxlength="100" value="${escapeHtml(value.group)}">`;
  if (value.rule) {
    const policyValues = state.catalog.valueTypes.find(t => t.id === 'MissingIdentityPolicy')?.values || [];
    const fields = [...new Set([...state.conditionFields, ...(state.catalog.valueTypes.find(t => t.id === 'EventRoleCode')?.values.map(v => v.code) || [])])].sort();
    html += `<section class="rule-box"><h3>같은 스레드로 묶는 조건</h3><p class="helper">이벤트 종류가 같고, 아래 필수 식별값이 모두 같아야 합니다. 한 줄에 코드 하나 · 순서는 식별 키에 반영됩니다.</p><label for="requiredFields">필수 식별 조건 · 모두 일치</label><textarea id="requiredFields" data-field="required" rows="3">${escapeHtml(value.rule.required.join('\n'))}</textarea><label for="optionalFields">보조 구분 조건 · 설계 정의</label><textarea id="optionalFields" data-field="optional" rows="2">${escapeHtml(value.rule.optional.join('\n'))}</textarea><div class="field-picker"><select id="fieldChoice" aria-label="추가할 조건"><option value="">조건 선택</option>${fields.map(f => `<option>${escapeHtml(f)}</option>`).join('')}</select><button data-add-field="required" type="button">필수 ＋</button><button data-add-field="optional" type="button">보조 ＋</button></div><label for="missingPolicy">필수 정보가 부족할 때</label><select id="missingPolicy" data-field="missingPolicy">${policyValues.map(v => `<option value="${escapeHtml(v.code)}" ${v.code === value.rule.missingPolicy ? 'selected' : ''}>${escapeHtml(v.code === 'EMIT_UNKNOWN_LINK_ONLY' ? '연결 보류 · UNKNOWN으로 남김' : v.code)}</option>`).join('')}</select><p class="warning">현재 확인한 로컬 연결 코드는 필수 역할 ID만 비교합니다. 보조 조건은 사용하지 않습니다. 여기서 저장한 변경은 실행 코드에 적용되지 않습니다.</p></section>`;
  }
  const origin = value.origin;
  if (origin) {
    const baseline = state.sourceCatalog.valueTypes.find(t => t.id === type.id)?.values.find(v => v.code === value.code);
    html += `<details><summary>원본 정의와 비교</summary>${origin.identityConflict ? '<p class="warning">타입 사전과 스레드 계약의 필수 조건이 다릅니다.</p>' : ''}<dl class="origin"><dt>타입 사전 · 코드에서 사용하는 조건</dt><dd>${escapeHtml(origin.identityRequired.join(' + '))}</dd><dt>스레드 계약 · 필수 조건</dt><dd>${escapeHtml(origin.contractRequired.join(' + '))}</dd><dt>스레드 계약 · 보조 조건</dt><dd>${escapeHtml(origin.contractOptional.join(', ') || '없음')}</dd><dt>참조 단계 모델</dt><dd>${escapeHtml(origin.lifecycleModel || '없음')}</dd><dt>원본 파일</dt><dd>${escapeHtml(origin.path)}</dd></dl><pre>${escapeHtml(JSON.stringify(baseline?.rule || {}, null, 2))}</pre></details>`;
  }
  $('editor').innerHTML = html;
  renderJson();
}
function renderJson() {
  $('definitionJson').textContent = JSON.stringify({valueType:currentType().id, baseType:currentType().baseType, value:currentValue()}, null, 2);
}
function renderGraph() {
  const value = currentValue();
  if (!value?.rule) {
    $('graphTitle').textContent = '허용값 정의';
    $('graphHint').textContent = '스레드 연결조건은 EventTypeCode의 이벤트 종류에서 관리합니다.';
    $('conditionGraph').innerHTML = '<p class="empty">왼쪽에서 EventTypeCode를 선택하면 이벤트 종류별 조건을 볼 수 있습니다.</p>';
    return;
  }
  $('graphTitle').textContent = '동일 사건을 식별하는 조건';
  $('graphHint').textContent = '실선: 필수 값 모두 일치 · 점선: 보조 조건(현재 코드 미사용)';
  const conditions = [...value.rule.required.map(code => ({code, required:true})), ...value.rule.optional.map(code => ({code, required:false}))];
  if (!conditions.length) { $('conditionGraph').innerHTML = '<p class="warning">필수 조건이 비어 있습니다. 저장 전에 지정하세요.</p>'; return; }
  const height = Math.max(190, conditions.length * 62 + 24), middle = height / 2;
  const rootLines = value.code.match(/.{1,27}/g) || [''];
  let content = `<rect x="8" y="${middle-55}" width="231" height="110" rx="8" fill="#e5efdc" stroke="#477b54" stroke-width="2"/><text x="20" y="${middle-30}" font-size="10">EVENT TYPE · 같은 종류</text>`;
  rootLines.forEach((line, i) => { content += `<text x="20" y="${middle-7+i*17}" font-size="12" font-weight="700">${escapeHtml(line)}</text>`; });
  conditions.forEach((field, i) => {
    const y = 14 + i * 62, center = y + 24;
    content += `<path d="M239 ${middle} H272 V${center} H304" fill="none" stroke="${field.required ? '#315d45' : '#936425'}" stroke-width="2" ${field.required ? '' : 'stroke-dasharray="5 4"'}/><rect x="304" y="${y}" width="320" height="48" rx="6" fill="${field.required ? '#ffffff' : '#fff4dc'}" stroke="${field.required ? '#6d9271' : '#ba955b'}"/><text x="317" y="${y+19}" font-size="12" font-weight="700">${escapeHtml(field.code)}</text><text x="317" y="${y+36}" font-size="10">${field.required ? '식별값이 같아야 연결' : '보조 구분 · 실행 미적용'}</text>`;
  });
  $('conditionGraph').innerHTML = `<svg viewBox="0 0 640 ${height}" role="img" aria-label="${escapeHtml(value.code)} 연결조건"><title>${escapeHtml(value.code)}의 필수·보조 식별 조건</title>${content}</svg>`;
}
function edited() {
  updateState(); renderJson(); renderGraph();
  $('typeDescription').textContent = currentType().description;
  renderList();
}
$('editor').addEventListener('input', event => {
  const field = event.target.dataset.field;
  if (!field) return;
  const value = event.target.value;
  if (field === 'typeDescription') currentType().description = value;
  else if (field === 'required' || field === 'optional') currentValue().rule[field] = value.split(/[\n,]/).map(v => v.trim()).filter(Boolean);
  else if (field === 'missingPolicy') currentValue().rule.missingPolicy = value;
  else currentValue()[field] = value;
  edited();
});
$('editor').addEventListener('click', event => {
  const kind = event.target.dataset.addField, code = $('fieldChoice')?.value;
  if (!kind || !code) return;
  if (!currentValue().rule[kind].includes(code)) currentValue().rule[kind].push(code);
  renderEditor(); edited();
});
$('typeList').addEventListener('click', event => {
  const button = event.target.closest('[data-type]');
  if (!button) return;
  selectedType = button.dataset.type; selectedCode = currentType().values[0]?.code || '';
  $('valueSearch').value = ''; $('groupFilter').value = ''; $('valueList').scrollTop = 0;
  render();
});
$('valueList').addEventListener('click', event => {
  const button = event.target.closest('[data-code]');
  if (!button) return;
  selectedCode = button.dataset.code; renderList(); renderEditor(); renderGraph();
});
$('typeSearch').addEventListener('input', () => state && renderNavigation());
$('valueSearch').addEventListener('input', () => state && renderList());
$('groupFilter').addEventListener('change', () => state && renderList());
$('save').addEventListener('click', async () => {
  saving = true; updateState(); message('');
  try {
    const payload = {catalog:state.catalog, revision:state.revision, sourceHash:state.sourceHash};
    // Lock inputs during the request so a response cannot overwrite newer local typing.
    document.querySelector('main').inert = true;
    state = await api('/api/value-types', payload); clean = JSON.stringify(state.catalog); render();
    message(`로컬 설계 v${state.revision} 저장 완료. 실제 이벤트 연결에는 적용되지 않았습니다.`);
  } catch (error) { message(error.message); }
  finally { saving = false; document.querySelector('main').inert = false; updateState(); }
});
$('reload').addEventListener('click', load);
$('applyLibrary').addEventListener('click', async () => {
  saving = true; updateState(); message(''); document.querySelector('main').inert = true;
  try {
    state = await api('/api/value-types/apply', {revision:state.revision, sourceHash:state.sourceHash});
    clean = JSON.stringify(state.catalog); render();
    message('라이브러리 파일에 반영했습니다. 반영된 초안은 제거했고 Git 커밋은 생성하지 않았습니다.');
  } catch (error) { message(error.message); }
  finally { saving = false; document.querySelector('main').inert = false; updateState(); }
});
$('export').addEventListener('click', () => {
  if (!state) return;
  const blob = new Blob([JSON.stringify({revision:state.revision, sourceHash:state.sourceHash, catalog:state.catalog}, null, 2)], {type:'application/json'});
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'orca-value-types.json'; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
});
function openCreate(mode) {
  if (!state) return;
  createMode = mode; $('createForm').reset(); $('createError').textContent = '';
  $('createKind').textContent = mode === 'type' ? 'STRING ENUM' : currentType().id;
  $('createTitle').textContent = mode === 'type' ? 'Value Type 추가' : '허용값 추가';
  $('createDialog').showModal(); $('createCode').focus();
}
$('addType').addEventListener('click', () => openCreate('type'));
$('addValue').addEventListener('click', () => openCreate('value'));
$('cancelCreate').addEventListener('click', () => $('createDialog').close());
$('createForm').addEventListener('submit', event => {
  event.preventDefault();
  const code = $('createCode').value.trim(), description = $('createDescription').value.trim();
  if (!code) return;
  if (createMode === 'type') {
    if (!/^[A-Za-z][A-Za-z0-9]{0,63}$/.test(code) || state.catalog.valueTypes.some(t => t.id === code)) {
      $('createError').textContent = '중복 없는 영문·숫자 ID를 입력하세요.'; return;
    }
    state.catalog.valueTypes.push({id:code, description, baseType:'String', usedBy:[], values:[]}); selectedType = code; selectedCode = '';
  } else {
    if (currentType().values.some(v => v.code === code)) { $('createError').textContent = '이미 있는 코드입니다.'; return; }
    const value = {code, description, group:''};
    if (selectedType === 'EventTypeCode') value.rule = {required:[], optional:[], missingPolicy:'EMIT_UNKNOWN_LINK_ONLY'};
    currentType().values.push(value); currentType().values.sort((a,b) => a.code.localeCompare(b.code)); selectedCode = code;
  }
  $('valueSearch').value = ''; $('groupFilter').value = ''; $('createDialog').close(); render();
});
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
load();
