<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { FlaskConical, LayoutDashboard, Library, SlidersHorizontal, Play, CircleAlert, BookOpen, ArrowUpRight, Plus, Download, Search, X, ChevronRight, Pause, RotateCcw, Check, LoaderCircle, GitCompareArrows, FileCheck2, ExternalLink, Layers3 } from 'lucide-vue-next'
import Chart from './components/Chart.vue'

const page = ref('results'), loading = ref(true), error = ref(''), busy = ref(false), toast = ref('')
const health = ref({}), datasets = ref([]), configs = ref([]), runs = ref([]), docs = ref([])
const selectedDataset = ref(''), selectedRun = ref(''), selectedType = ref(''), search = ref('')
const questions = ref([]), quality = ref(null), summary = ref({ rows: [] }), items = ref({ rows: [], total: 0 }), bad = ref(null)
const itemPage = ref(1), itemConfig = ref(''), sampledOnly = ref(false), badTag = ref('')
const modal = ref(null), form = ref({}), detail = ref(null), judgeVisible = ref(false), comparison = ref(null)
const selectedConfigs = ref([]), compareLeft = ref(''), compareRight = ref(''), compareRun = ref('')
const importInput = ref(null)
const types = { fact: '事实型', reasoning: '推理型', multihop: '多跳型', refusal: '拒答型' }
const strategies = { fixed: '固定长度', recursive: '递归分块', semantic: '语义分块' }
const stateNames = { queued: '排队中', running: '运行中', pausing: '暂停中', paused: '已暂停', failed: '有失败项', completed: '已完成', pending: '待处理', succeeded: '成功' }
const nav = [
  { id: 'results', label: '结果看板', icon: LayoutDashboard }, { id: 'datasets', label: '评测集', icon: Library },
  { id: 'configs', label: '配置版本', icon: SlidersHorizontal }, { id: 'runs', label: '跑批任务', icon: Play },
  { id: 'bad', label: 'Bad Case', icon: CircleAlert }, { id: 'documents', label: '知识库', icon: BookOpen }
]
const titles = { results: ['实验结果', '让每一次优化，都有证据。'], datasets: ['评测集管理', '从高质量问题，建立可信的评测基线。'], configs: ['配置版本', '控制变量，发现真正有效的改动。'], runs: ['跑批任务', '批量评测、持久记录，随时暂停与续跑。'], bad: ['Bad Case 分析', '沿着证据定位问题，把失败变成下一次改进。'], documents: ['知识库来源', '保存原文与来源，让检索结果可以追溯。'] }
const run = computed(() => runs.value.find(r => r.id === selectedRun.value))
const rows = computed(() => summary.value.rows || [])
const best = computed(() => [...rows.value].filter(r => r.success_coverage === 1 && r.task_success != null).sort((a,b) => b.task_success - a.task_success || b.mrr - a.mrr || a.qa_ms - b.qa_ms)[0])
const filteredQuestions = computed(() => questions.value.filter(q => (!selectedType.value || q.type === selectedType.value) && (!search.value || q.question.includes(search.value) || q.id.includes(search.value))))
const currentDataset = computed(() => datasets.value.find(d => d.id === selectedDataset.value))
const sameKRows = computed(() => {
  const baseline = rows.value.find(r => r.config_id === 'config-c01') || rows.value[0]
  if (!baseline) return []
  return rows.value.filter(r => Object.keys(baseline.parameters).every(k => k === 'top_k' || JSON.stringify(r.parameters[k]) === JSON.stringify(baseline.parameters[k]))).sort((a,b) => a.parameters.top_k - b.parameters.top_k)
})
const percentage = value => value == null ? '—' : (value * 100).toFixed(1) + '%'
const number = (value, digits = 3) => value == null ? '—' : Number(value).toFixed(digits)
const labelConfig = id => (run.value?.configs || configs.value).find(c => c.id === id)?.name || id
const download = (url) => { window.location.href = url }
const feedback = message => { toast.value = message; setTimeout(() => toast.value = '', 4500) }

async function api(path, options = {}) {
  const response = await fetch('/api' + path, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers }, body: options.body ? JSON.stringify(options.body) : undefined })
  let payload
  try { payload = await response.json() } catch { throw new Error('服务响应异常，请检查后端是否启动') }
  if (!response.ok) throw new Error(payload.message || `请求失败 (${response.status})`)
  return payload.data
}
async function act(fn) {
  busy.value = true
  try { await fn() } catch (e) { feedback(e.message) } finally { busy.value = false }
}
async function bootstrap() {
  loading.value = true; error.value = ''
  try {
    const results = await Promise.all([api('/health'), api('/datasets'), api('/configs'), api('/runs'), api('/documents')])
    ;[health.value, datasets.value, configs.value, runs.value, docs.value] = results
    if (!selectedDataset.value) selectedDataset.value = datasets.value[0]?.id || ''
    if (!selectedRun.value) selectedRun.value = runs.value[0]?.id || ''
    if (!selectedConfigs.value.length) selectedConfigs.value = configs.value.filter(c => ['config-c01','config-c02','config-c03','config-c04','config-c06','config-c07'].includes(c.id)).map(c => c.id)
    if (!compareLeft.value) compareLeft.value = configs.value[0]?.id || ''
    if (!compareRight.value) compareRight.value = configs.value[5]?.id || configs.value[1]?.id || ''
    await refreshPage()
  } catch (e) { error.value = e.message } finally { loading.value = false }
}
async function loadDataset() {
  if (!selectedDataset.value) { questions.value = []; quality.value = null; return }
  ;[questions.value, quality.value] = await Promise.all([api(`/datasets/${selectedDataset.value}/questions`), api(`/datasets/${selectedDataset.value}/quality`)])
}
async function loadItems() {
  if (!selectedRun.value) { items.value = { rows: [], total: 0 }; return }
  const query = new URLSearchParams({ page: itemPage.value, page_size: 15 })
  if (itemConfig.value) query.set('config_id', itemConfig.value)
  if (sampledOnly.value) query.set('sampled_only', 'true')
  if (page.value === 'bad') query.set('bad_only', 'true')
  if (page.value === 'bad' && badTag.value) query.set('tag', badTag.value)
  items.value = await api(`/runs/${selectedRun.value}/items?${query}`)
}
async function loadResults() {
  if (!selectedRun.value) { summary.value = { rows: [] }; bad.value = null; return }
  ;[summary.value, bad.value] = await Promise.all([api(`/runs/${selectedRun.value}/metrics`), api(`/runs/${selectedRun.value}/bad-cases`)])
  await loadItems()
}
async function refreshPage() {
  if (page.value === 'datasets') await loadDataset()
  if (['results', 'bad'].includes(page.value)) await loadResults()
}
watch(page, () => { itemPage.value = 1; search.value = ''; act(refreshPage) })
watch(selectedDataset, () => { if (page.value === 'datasets') act(loadDataset) })
watch(selectedRun, () => { itemPage.value = 1; act(loadResults) })
watch([itemConfig, sampledOnly, badTag], () => { itemPage.value = 1; act(loadItems) })
let polling, refreshing = false
onMounted(async () => {
  await bootstrap()
  polling = setInterval(async () => {
    if (refreshing || !runs.value.some(r => ['queued','running','pausing'].includes(r.state))) return
    refreshing = true
    try { runs.value = await api('/runs'); if (['results','bad'].includes(page.value)) await loadResults() }
    catch (e) { error.value = e.message } finally { refreshing = false }
  }, 2500)
})
onBeforeUnmount(() => clearInterval(polling))

function openCase(q = null) {
  const base = q ? JSON.parse(JSON.stringify(q)) : { id: `Q-${Date.now()}`, question: '', type: 'fact', gold_answer: '', difficulty: 'medium', evidence: [], status: 'draft', annotator: '', reviewed_at: null, annotation_note: '', gold_doc: [], gold_chunk_id: [] }
  form.value = { ...base, isReviewed: base.status === 'reviewed' }; modal.value = 'case'
}
function openConfig(config = null) {
  form.value = config ? { ...JSON.parse(JSON.stringify(config)), name: config.name + ' · 新版本' } : { name: '新配置', parameters: { chunk_strategy:'fixed',chunk_size:500,chunk_overlap:80,semantic_threshold:0.55,retrieval:'vector',top_k:3,candidate_k:15,similarity_threshold:0,rerank:false,rerank_top_n:5,rrf_k:60,model:health.value.model || 'deepseek-flash',thinking:false,input_price:null,output_price:null,temperature:0,max_tokens:700,evidence_coverage:0.8 } }
  modal.value = 'config'
}
async function saveCase() {
  await act(async () => {
    const data = { ...form.value }; delete data.row_id; delete data.isReviewed
    data.status = form.value.isReviewed ? 'reviewed' : form.value.status === 'demo' ? 'demo' : 'draft'
    if (form.value.isReviewed && !data.reviewed_at) data.reviewed_at = new Date().toISOString()
    if (!form.value.isReviewed) { data.annotator = null; data.reviewed_at = null }
    if (data.type === 'refusal') { data.evidence = []; data.gold_doc = []; data.gold_chunk_id = [] }
    else { data.gold_doc = []; data.gold_chunk_id = []; data.evidence = data.evidence.map(e => ({ doc_id: e.doc_id, quote: e.quote, start: null, end: null })) }
    await api(form.value.row_id ? `/questions/${form.value.row_id}` : `/datasets/${selectedDataset.value}/questions`, { method: form.value.row_id ? 'PUT' : 'POST', body: data })
    modal.value = null; await bootstrap(); await loadDataset(); feedback('题目与标注已保存')
  })
}
async function saveConfig() {
  await act(async () => { const parameters={...form.value.parameters}; for(const field of ['input_price','output_price']) if(parameters[field]==='') parameters[field]=null; await api(form.value.id ? `/configs/${form.value.id}/clone` : '/configs', { method:'POST', body:{ name:form.value.name, parameters } }); modal.value=null; await bootstrap(); feedback('已保存为独立配置版本') })
}
async function importFile(event) {
  const file = event.target.files[0]; if (!file) return
  await act(async () => { await api(`/datasets/${selectedDataset.value}/import`, { method:'POST', body:{format:file.name.toLowerCase().endsWith('.csv')?'csv':'json', text:await file.text()} }); await bootstrap(); await loadDataset(); feedback('题目批量导入成功') })
  event.target.value = ''
}
function openRun() { form.value = { name:'RAG配置对比实验', dataset_id:selectedDataset.value || datasets.value[0]?.id, mode:'demo', concurrency:3, sample_seed:42 }; modal.value='run' }
async function startRun() {
  await act(async () => { const response = await api('/runs', {method:'POST',body:{...form.value,config_ids:selectedConfigs.value}}); modal.value=null; selectedRun.value=response.id; page.value='runs'; await bootstrap(); feedback('任务已创建，Worker将自动领取') })
}
async function taskAction(r, action) { await act(async () => { await api(`/runs/${r.id}/${action}`, {method:'POST'}); runs.value=await api('/runs'); feedback(action==='pause'?'正在停止领取新题，在途调用结束后暂停':'任务已加入续跑队列') }) }
async function openDetail(item) {
  await act(async () => { detail.value=await api(`/items/${item.id}`); judgeVisible.value=false; form.value={tags:[...detail.value.tags], note:detail.value.note, accuracy:3, completeness:3, refused:false, unsupported:false, factually_incorrect:null, reviewer:'', review_note:''}; modal.value='detail' })
}
async function saveTags() { await act(async () => { await api(`/items/${detail.value.id}/tags`, {method:'PUT',body:{tags:form.value.tags,note:form.value.note}}); await loadResults(); feedback('标签与备注已保存') }) }
async function saveHuman() {
  await act(async () => { await api(`/items/${detail.value.id}/human-review`, {method:'PUT',body:{accuracy:form.value.accuracy,completeness:form.value.completeness,refused:form.value.refused,unsupported:form.value.unsupported,factually_incorrect:form.value.factually_incorrect,reviewer:form.value.reviewer,note:form.value.review_note}}); await loadResults(); feedback('独立人工评分已保存，一致率已更新') })
}
async function compareHistory() { await act(async () => { comparison.value=await api(`/compare?left=${encodeURIComponent(compareRun.value)}&right=${encodeURIComponent(selectedRun.value)}`); modal.value='history' }) }

const palette = ['#2c7657','#83af94','#d6a150','#8f9eae']
const chartBase = { color:palette, textStyle:{fontFamily:'Inter, Microsoft YaHei, sans-serif',fontSize:11,color:'#68746c'}, tooltip:{trigger:'axis'}, grid:{left:42,right:20,top:48,bottom:65}, legend:{top:5,itemWidth:10,itemHeight:10,textStyle:{fontSize:10}} }
const bars = computed(() => ({ ...chartBase, xAxis:{type:'category',data:rows.value.map(r=>r.name.split(' ')[0]),axisLine:{lineStyle:{color:'#e4e8e1'}},axisTick:{show:false}}, yAxis:{type:'value',max:1,splitLine:{lineStyle:{color:'#edf0e9'}}}, series:[['recall','证据 Recall@K'],['mrr','MRR@K'],['correct','答案正确率']].map(([key,name])=>({name,type:'bar',barMaxWidth:14,data:rows.value.map(r=>r[key]),itemStyle:{borderRadius:[3,3,0,0]}})) }))
const line = computed(() => ({ ...chartBase, legend:{top:5}, xAxis:{type:'category',name:'Top-K',data:sameKRows.value.map(r=>r.parameters.top_k),axisTick:{show:false}},yAxis:{type:'value',max:1,splitLine:{lineStyle:{color:'#edf0e9'}}},series:[['recall','Recall@K'],['correct','正确率']].map(([key,name])=>({name,type:'line',smooth:false,symbolSize:8,data:sameKRows.value.map(r=>r[key])})) }))
const scatter = computed(() => ({...chartBase,tooltip:{trigger:'item',formatter:p=>`${p.data[2]}<br>对话成本 ${p.data[0]} ${summary.value.currency}<br>问答延迟 ${number(p.data[1],0)} ms`},xAxis:{type:'value',name:`对话成本 (${summary.value.currency || 'CNY'})`,nameLocation:'middle',nameGap:25},yAxis:{type:'value',name:'问答延迟 ms',splitLine:{lineStyle:{color:'#edf0e9'}}},series:[{type:'scatter',symbolSize:15,data:rows.value.filter(r=>r.dialogue_cost!=null).map(r=>[r.dialogue_cost,r.qa_ms,r.name])}]}))
const pie = computed(() => ({color:['#2c7657','#a7b98a','#d6a150','#b96e58','#8296ad','#c4b4c7'],tooltip:{trigger:'item'},legend:{bottom:0,textStyle:{fontSize:11}},series:[{type:'pie',radius:['48%','70%'],center:['50%','43%'],label:{show:false},data:Object.entries(bad.value?.tag_counts || {}).map(([name,value])=>({name,value}))}]}))
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="page='results'"><span class="brand-icon"><FlaskConical :size="23"/></span><span>RAG<span class="brand-light">Lab</span><small>EVALUATION WORKSPACE</small></span></a>
      <div class="workspace"><span class="workspace-mark">F</span><div>飞的评测工作台<small>个人项目 · LOCAL</small></div><ChevronRight :size="14"/></div>
      <div class="nav-label">工作空间</div>
      <nav><button v-for="n in nav" :key="n.id" :class="{active:page===n.id}" @click="page=n.id"><component :is="n.icon" :size="18"/><span>{{n.label}}</span><span v-if="n.id==='configs'" class="nav-count">{{configs.length}}</span></button></nav>
      <div class="sidebar-note"><Layers3 :size="20"/><strong>以证据，驱动迭代。</strong><p>固定题集 · 控制变量<br>追溯每一次实验结果</p><span class="small-dot"></span> 评测工作流 v0.1</div>
      <div class="profile"><span class="avatar">飞</span><div>独立开发项目<small>FastAPI + Vue 3</small></div><span class="online-dot"></span></div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><div><span class="muted">工作空间</span><ChevronRight :size="13"/><span>{{titles[page][0]}}</span></div><div class="topbar-right"><span class="status-dot"></span>本地服务<span class="divider"></span><span class="version">v0.1</span><span class="avatar small">飞</span></div></header>
      <main>
        <div class="page-header"><div><div class="eyebrow">RAG QUALITY & OPTIMIZATION</div><h1>{{titles[page][0]}}</h1><p>{{titles[page][1]}}</p></div><button class="primary" @click="openRun"><Play :size="15"/>新建评测任务</button></div>
        <div v-if="error" class="alert error"><CircleAlert :size="18"/><span>{{error}}</span><button @click="bootstrap">重试</button></div>
        <div v-if="loading" class="empty"><LoaderCircle class="spin"/>正在加载工作空间…</div>
        <template v-else>
          <template v-if="['results','bad'].includes(page)">
            <div class="toolbar"><div class="select-group"><span>评测任务</span><select v-model="selectedRun"><option value="" disabled>选择任务</option><option v-for="r in runs" :value="r.id">{{r.name}} · {{stateNames[r.state]}} {{r.mode==='demo'?'[模拟]':''}}</option></select></div><span v-if="run" class="pill" :class="run.state">{{stateNames[run.state]}}</span><div class="grow"></div><button v-if="run" class="outline" @click="download(`/api/runs/${run.id}/export?format=csv`)"><Download :size="14"/>导出指标</button><button v-if="run" class="outline" @click="download(`/api/runs/${run.id}/export?format=markdown`)">生成报告<ArrowUpRight :size="14"/></button></div>
            <div v-if="run?.mode==='demo'" class="demo-banner"><FlaskConical :size="17"/><span><strong>本地模拟实验</strong> · 检索、答案和评分用于验证工程流程；这些数据不代表云端模型效果。</span></div>
            <div v-if="!run" class="empty card"><FlaskConical :size="36"/><h3>开始你的第一次对比实验</h3><p>选择评测集和配置，运行后即可查看指标与逐题证据。</p><button class="primary" @click="openRun">创建评测任务<ArrowUpRight :size="15"/></button></div>
            <template v-else-if="page==='results'">
              <div class="kpi-grid">
                <div class="kpi"><div>全题任务成功率 <FileCheck2 :size="17"/></div><strong>{{percentage(best?.task_success)}}</strong><span>候选最佳配置 · {{best?.name.split(' ')[0] || '等待完成'}}</span></div>
                <div class="kpi"><div>证据 Recall@K <Search :size="17"/></div><strong>{{percentage(best?.recall)}}</strong><span>回答题标准证据覆盖</span></div>
                <div class="kpi"><div>平均问答延迟 <RotateCcw :size="17"/></div><strong>{{number(best?.qa_ms,0)}}<em>ms</em></strong><span>不含 Judge 与建索引</span></div>
                <div class="kpi"><div>已完成问答 <Layers3 :size="17"/></div><strong>{{run.counts.succeeded || 0}}<em>/ {{run.total}}</em></strong><span>{{run.configs.length}} 套配置 · {{run.total / run.configs.length}} 道题目</span></div>
              </div>
              <div class="charts-grid"><section class="card"><div class="card-heading"><div><h3>多配置质量对比</h3><p>同一题集，检索与答案质量并排观察</p></div><span class="subtle-tag">QUALITY</span></div><Chart :option="bars"/></section><section class="card"><div class="card-heading"><div><h3>Top-K 效果变化</h3><p>仅比较其余参数一致的配置</p></div><span class="subtle-tag">ABLATION</span></div><Chart :option="line"/></section></div>
              <div class="charts-grid secondary"><section class="card"><div class="card-heading"><div><h3>配置指标明细</h3><p>质量均值仅统计成功项，覆盖率单列</p></div></div><div class="table-scroll"><table class="compact"><thead><tr><th>配置</th><th>MRR@K</th><th>正确率</th><th>拒答率</th><th>覆盖率</th><th>P95 / ms</th></tr></thead><tbody><tr v-for="r in rows" :class="{recommended:r.config_id===best?.config_id}"><td>{{r.name}}<span v-if="r.config_id===best?.config_id" class="recommended-label">候选最佳</span></td><td>{{number(r.mrr)}}</td><td>{{percentage(r.correct)}}</td><td>{{percentage(r.refusal_correct)}}</td><td>{{percentage(r.success_coverage)}}</td><td>{{number(r.p95_ms,0)}}</td></tr></tbody></table></div></section><section class="card"><div class="card-heading"><div><h3>成本与延迟</h3><p>仅包含生成 + Judge 对话费用</p></div></div><Chart v-if="rows.some(r=>r.dialogue_cost!=null)" :option="scatter"/><div v-else class="empty small-empty"><Layers3 :size="27"/><strong>费用数据尚不可用</strong><p>真实API用量和模型价格齐备后显示。<br>Embedding / Rerank 费用需另外统计。</p></div></section></div>
              <div class="history-toolbar"><GitCompareArrows :size="17"/><strong>历史回归对比</strong><select v-model="compareRun"><option value="">选择历史任务</option><option v-for="r in runs.filter(r=>r.id!==selectedRun)" :value="r.id">{{r.name}} · {{r.id.slice(-6)}}</option></select><button class="outline" :disabled="!compareRun" @click="compareHistory">对比版本</button><div class="grow"></div><span>人工核验 {{rows.reduce((n,r)=>n+r.agreement_n,0)}} 条</span><button class="text-button" @click="download(`/api/runs/${run.id}/export?format=human`)">导出核验记录<Download :size="13"/></button></div>
            </template>
            <template v-else>
              <div class="kpi-grid three"><div class="kpi"><div>失败 / 低分结果</div><strong>{{bad?.total || 0}}</strong><span>按题目 × 配置运行项统计</span></div><div class="kpi"><div>待人工归因</div><strong>{{bad?.untagged || 0}}</strong><span>自动建议标签可由人修订</span></div><div class="kpi"><div>归因类别</div><strong>6</strong><span>同一案例支持多个标签</span></div></div>
              <div class="charts-grid"><section class="card"><div class="card-heading"><div><h3>标签分布</h3><p>多标签频次，类别总数可大于案例数</p></div></div><Chart :option="pie"/></section><section class="card"><div class="card-heading"><div><h3>反复出现的问题</h3><p>按不同配置下的失败频次排序</p></div></div><div v-if="!bad?.typical.length" class="empty small-empty">暂无失败案例</div><div v-for="(c,i) in bad?.typical.slice(0,6)" class="typical"><span>{{String(i+1).padStart(2,'0')}}</span><div><strong>{{c.question}}</strong><small>{{c.case_id}}</small></div><b>{{c.frequency}} 次</b></div></section></div>
            </template>
            <section v-if="run" class="card detail-table"><div class="card-heading"><div><h3>{{page==='bad'?'案例证据与归因':'逐题结果与证据'}}</h3><p>查看召回内容、模型答案与评分依据</p></div><div class="table-controls"><select v-model="itemConfig"><option value="">全部配置</option><option v-for="c in run.configs" :value="c.id">{{c.name}}</option></select><select v-if="page==='bad'" v-model="badTag"><option value="">全部标签</option><option v-for="tag in health.tags" :value="tag">{{tag}}</option></select><label class="checkbox"><input type="checkbox" v-model="sampledOnly"/>仅人工抽样</label></div></div><div class="table-scroll"><table><thead><tr><th>题目 / ID</th><th>题型</th><th>配置</th><th>状态</th><th>正确</th><th>{{page==='bad'?'归因标签':'MRR@K'}}</th><th></th></tr></thead><tbody><tr v-for="item in items.rows" :key="item.id"><td class="question-cell"><strong>{{item.question}}</strong><small>{{item.case_id}} <span v-if="item.sampled" class="sample-mark">人工抽样</span><span v-if="item.reviewed"> · 已核验</span></small></td><td><span class="type-tag">{{types[item.type]}}</span></td><td>{{labelConfig(item.config_id).split(' ')[0]}}</td><td><span class="pill" :class="item.state">{{stateNames[item.state]}}</span></td><td>{{item.metrics ? item.metrics.task_success ? '是':'否':'—'}}</td><td>{{page==='bad'?item.tags.join(' · ') || '待标注':number(item.metrics?.mrr)}}</td><td><button class="text-button" @click="openDetail(item)">查看<ChevronRight :size="14"/></button></td></tr></tbody></table><div v-if="!items.rows.length" class="empty small-empty">当前筛选条件下没有结果</div></div><div class="pagination"><span>共 {{items.total}} 条结果</span><button :disabled="itemPage<=1" @click="itemPage--;act(loadItems)">上一页</button><span>{{itemPage}} / {{Math.max(1,Math.ceil(items.total/15))}}</span><button :disabled="itemPage*15>=items.total" @click="itemPage++;act(loadItems)">下一页</button></div></section>
          </template>

          <template v-if="page==='datasets'">
            <div class="toolbar"><div class="select-group"><span>评测集</span><select v-model="selectedDataset"><option v-for="d in datasets" :value="d.id">{{d.name}}</option></select></div><div class="grow"></div><button class="outline" @click="form={name:'',description:''};modal='dataset'"><Plus :size="14"/>新建题集</button><button class="outline" :disabled="!currentDataset" @click="form={id:currentDataset.id,name:currentDataset.name,description:currentDataset.description};modal='dataset'">编辑题集</button><button class="text-button danger" :disabled="!currentDataset" @click="form={id:currentDataset.id,name:currentDataset.name};modal='delete-dataset'">删除</button></div>
            <div class="kpi-grid"><div class="kpi"><div>题目总数</div><strong>{{quality?.total || 0}}</strong><span>正式验收要求 ≥100 题</span></div><div class="kpi"><div>已人工审核</div><strong>{{quality?.statuses.reviewed || 0}}</strong><span>云端正式任务要求逐题审核</span></div><div class="kpi"><div>平均题目长度</div><strong>{{number(quality?.average_question_length,0)}}<em>字</em></strong><span>题型与来源统计均可复核</span></div><div class="kpi"><div>字符串泄漏命中</div><strong>{{quality?.leakage_matches.length || 0}}</strong><span>题目原文与知识库包含比对</span></div></div>
            <div class="distribution"><span v-for="(name,key) in types">{{name}} <b>{{quality?.types[key] || 0}}</b></span><div class="grow"></div><span>标准来源 {{Object.keys(quality?.sources || {}).length}} 份</span></div>
            <section class="card"><div class="card-heading"><div class="table-controls"><div class="search-box"><Search :size="15"/><input v-model="search" placeholder="搜索问题或 ID"/></div><select v-model="selectedType"><option value="">全部题型</option><option v-for="(name,key) in types" :value="key">{{name}}</option></select></div><div class="actions"><input ref="importInput" type="file" accept=".json,.csv" hidden @change="importFile"/><button class="outline" :disabled="!selectedDataset" @click="importInput.click()">批量导入</button><button class="outline" :disabled="!selectedDataset" @click="download(`/api/datasets/${selectedDataset}/export`)"><Download :size="14"/>导出</button><button class="primary" :disabled="!selectedDataset" @click="openCase()"><Plus :size="14"/>新增题目</button></div></div><div class="table-scroll"><table><thead><tr><th>ID</th><th>问题</th><th>题型</th><th>标准来源</th><th>审核状态</th><th></th></tr></thead><tbody><tr v-for="q in filteredQuestions"><td class="mono">{{q.id}}</td><td class="question-cell"><strong>{{q.question}}</strong><small>{{q.gold_answer.slice(0,65)}}…</small></td><td><span class="type-tag">{{types[q.type]}}</span></td><td>{{q.evidence.length}} 条证据</td><td><span class="pill" :class="q.status==='reviewed'?'succeeded':'paused'">{{q.status==='reviewed'?'已审核':q.status==='demo'?'模拟题':'待审核'}}</span></td><td><div class="actions"><button class="text-button" @click="openCase(q)">编辑</button><button class="text-button danger" @click="form={row_id:q.row_id};modal='delete-case'">删除</button></div></td></tr></tbody></table><div v-if="!filteredQuestions.length" class="empty small-empty">暂无题目，新增或批量导入开始构建评测集。</div></div></section>
          </template>

          <template v-if="page==='configs'">
            <div class="toolbar"><span class="muted">{{configs.length}} 套独立配置版本 · 修改将创建新版本</span><div class="grow"></div><button class="primary" @click="openConfig()"><Plus :size="15"/>创建配置</button></div>
            <div class="config-grid"><section v-for="c in configs" class="card config-card"><div class="config-title"><span class="config-icon"><SlidersHorizontal :size="18"/></span><h3>{{c.name}}</h3><span class="subtle-tag">{{c.id.includes('c01')?'BASELINE':'VERSION'}}</span></div><div class="config-properties"><div><span>分块策略</span><strong>{{strategies[c.parameters.chunk_strategy]}}</strong></div><div><span>块大小 / 重叠</span><strong>{{c.parameters.chunk_size}} / {{c.parameters.chunk_overlap}}</strong></div><div><span>检索方式</span><strong>{{c.parameters.retrieval==='hybrid'?'BM25 + 向量 + RRF':'向量检索'}}</strong></div><div><span>Top-K / 候选数</span><strong>{{c.parameters.top_k}} / {{c.parameters.candidate_k}}</strong></div><div><span>重排</span><strong>{{c.parameters.rerank?'开启':'关闭'}}</strong></div><div><span>生成模型</span><strong>{{c.parameters.model}}</strong></div></div><div class="config-footer"><small class="mono">{{c.id}}</small><button class="text-button" @click="openConfig(c)">克隆 / 修改</button><button class="icon-button" aria-label="导出配置" @click="download(`/api/configs/${c.id}/export`)"><Download :size="15"/></button></div></section></div>
            <section class="card"><div class="card-heading"><div><h3>参数差异对照</h3><p>让每次实验的改动清晰可见</p></div><div class="table-controls"><select v-model="compareLeft"><option v-for="c in configs" :value="c.id">{{c.name}}</option></select><GitCompareArrows :size="17"/><select v-model="compareRight"><option v-for="c in configs" :value="c.id">{{c.name}}</option></select></div></div><div class="table-scroll"><table><thead><tr><th>参数</th><th>{{configs.find(c=>c.id===compareLeft)?.name}}</th><th>{{configs.find(c=>c.id===compareRight)?.name}}</th><th>差异</th></tr></thead><tbody><tr v-for="(value,key) in configs.find(c=>c.id===compareLeft)?.parameters" :class="{different:value!==configs.find(c=>c.id===compareRight)?.parameters[key]}"><td class="mono">{{key}}</td><td>{{value}}</td><td>{{configs.find(c=>c.id===compareRight)?.parameters[key]}}</td><td>{{value!==configs.find(c=>c.id===compareRight)?.parameters[key]?'已变化':'一致'}}</td></tr></tbody></table></div></section>
          </template>

          <template v-if="page==='runs'">
            <div class="demo-banner"><CircleAlert :size="17"/><span>任务由独立 Worker 执行。排队任务长时间不动时，请先启动 Worker。暂停会等待在途调用完成。</span></div>
            <div v-if="!runs.length" class="empty card"><Play :size="32"/><h3>还没有评测任务</h3><p>创建任务后，可以在这里跟踪进度与续跑。</p></div>
            <section v-for="r in runs" class="card run-card"><div class="run-heading"><div><div class="actions"><h3>{{r.name}}</h3><span class="pill" :class="r.state">{{stateNames[r.state]}}</span><span class="subtle-tag">{{r.mode==='demo'?'本地模拟':'云端正式'}}</span></div><p>{{r.dataset_name}} · {{r.configs.length}} 套配置 · {{new Date(r.created_at).toLocaleString('zh-CN')}}</p></div><div class="actions"><button v-if="['queued','running'].includes(r.state)" class="outline" @click="taskAction(r,'pause')"><Pause :size="14"/>暂停</button><button v-if="['paused','failed'].includes(r.state)" class="outline" @click="taskAction(r,'resume')"><RotateCcw :size="14"/>断点续跑</button><button class="text-button" @click="selectedRun=r.id;page='results'">查看结果<ArrowUpRight :size="14"/></button></div></div><div class="progress"><div :style="{width:100*r.done/Math.max(1,r.total)+'%'}"></div></div><div class="run-stats"><strong>{{r.done}} / {{r.total}} 已处理</strong><span>成功 {{r.counts.succeeded || 0}}</span><span>失败 {{r.counts.failed || 0}}</span><span v-if="r.current_configs.length">当前 {{r.current_configs.map(labelConfig).join('、')}}</span><div class="grow"></div><span>预计剩余 {{r.eta_seconds==null?'待估算':Math.ceil(r.eta_seconds/60)+' 分钟'}}</span></div><div v-if="r.error" class="alert error">{{r.error}}</div><small class="mono muted">{{r.id}} · 题集版本 {{r.dataset_hash.slice(0,12)}}</small></section>
          </template>

          <template v-if="page==='documents'">
            <div class="toolbar"><span class="muted">{{docs.filter(d=>d.kind==='real').length}} 份真实文档 · {{docs.filter(d=>d.kind==='real').reduce((n,d)=>n+d.baseline_chunks,0)}} 个基线文本块</span><div class="grow"></div><button class="primary" @click="form={title:'',source_url:'',content:'',kind:'real'};modal='document'"><Plus :size="15"/>导入原文</button></div><section class="card"><div class="table-scroll"><table><thead><tr><th>文档</th><th>来源性质</th><th>字符数</th><th>基线块数</th><th>原始来源</th><th></th></tr></thead><tbody><tr v-for="d in docs"><td><strong>{{d.title}}</strong><small class="mono">{{d.id}}</small></td><td><span class="pill" :class="d.kind==='real'?'succeeded':'paused'">{{d.kind==='real'?'真实公开来源':'合成演示'}}</span></td><td>{{d.characters.toLocaleString()}}</td><td>{{d.baseline_chunks}}</td><td><a v-if="d.source_url" :href="d.source_url" target="_blank" rel="noopener noreferrer" class="text-button">访问原文<ExternalLink :size="12"/></a><span v-else>—</span></td><td><button class="text-button" @click="act(async()=>{form=await api(`/documents/${d.id}`);modal='view-document'})">查看</button></td></tr></tbody></table></div></section>
          </template>
          <footer class="page-footer"><span>RAG Lab · 每个指标，回到每条证据。</span><span>版本化实验 / 可复现结果</span></footer>
        </template>
      </main>
    </div>
    <div v-if="toast" class="toast" role="status">{{toast}}</div>
    <div v-if="modal" class="modal-backdrop" @click.self="modal=null">
      <section class="modal" :class="{wide:['detail','case','config','history'].includes(modal)}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div class="modal-heading"><h2 id="modal-title">{{{case:'题目与标准证据',config:'保存配置版本',dataset:'评测集信息',run:'新建评测任务',detail:'逐题证据与人工核验',history:'历史版本对比',document:'导入知识库原文','view-document':'原文快照','delete-case':'删除题目','delete-dataset':'删除评测集'}[modal]}}</h2><button class="icon-button" aria-label="关闭" @click="modal=null"><X :size="20"/></button></div>
        <form v-if="modal==='case'" @submit.prevent="saveCase">
          <div class="form-row"><label>题目ID<input v-model="form.id" required/></label><label>题型<select v-model="form.type"><option v-for="(name,key) in types" :value="key">{{name}}</option></select></label><label>难度<select v-model="form.difficulty"><option value="easy">简单</option><option value="medium">中等</option><option value="hard">困难</option></select></label></div><label>问题<textarea v-model="form.question" required rows="2"></textarea></label><label>标准答案要点<textarea v-model="form.gold_answer" required rows="3"></textarea></label>
          <div v-if="form.type!=='refusal'" class="evidence-editor"><div class="section-label">标准来源证据 <button type="button" class="text-button" @click="form.evidence.push({doc_id:docs[0]?.id,quote:''})"><Plus :size="13"/>添加来源</button></div><div v-for="(e,i) in form.evidence" class="evidence-block"><div class="actions"><select v-model="e.doc_id"><option v-for="d in docs" :value="d.id">{{d.title}}</option></select><button type="button" class="icon-button danger" @click="form.evidence.splice(i,1)"><X :size="15"/></button></div><textarea v-model="e.quote" required placeholder="粘贴该文档中的完整证据原文。保存时会验证原文并定位坐标。" rows="3"></textarea></div></div>
          <label class="checkbox"><input type="checkbox" v-model="form.isReviewed"/>我已人工核对答案要点和全部标准来源</label><label v-if="form.isReviewed">审核人<input v-model="form.annotator" required placeholder="填写真实审核人"/></label><label>标注备注<input v-model="form.annotation_note"/></label><div class="modal-footer"><button type="button" class="outline" @click="modal=null">取消</button><button class="primary" :disabled="busy">保存题目<Check :size="15"/></button></div>
        </form>
        <form v-if="modal==='config'" @submit.prevent="saveConfig"><label>版本名称<input v-model="form.name" required/></label><div class="form-row"><label>分块策略<select v-model="form.parameters.chunk_strategy"><option v-for="(name,key) in strategies" :value="key">{{name}}</option></select></label><label>块大小<input type="number" v-model.number="form.parameters.chunk_size" min="100" max="5000"/></label><label>重叠大小<input type="number" v-model.number="form.parameters.chunk_overlap" min="0"/></label></div><div class="form-row"><label>检索方式<select v-model="form.parameters.retrieval"><option value="vector">向量</option><option value="hybrid">混合（BM25 + 向量 + RRF）</option></select></label><label>Top-K<input type="number" v-model.number="form.parameters.top_k" min="1" max="30"/></label><label>候选数<input type="number" v-model.number="form.parameters.candidate_k" min="1" max="100"/></label></div><div class="form-row"><label>向量相似度阈值<input type="number" v-model.number="form.parameters.similarity_threshold" min="-1" max="1" step="0.05"/></label><label>语义边界阈值<input type="number" v-model.number="form.parameters.semantic_threshold" min="-1" max="1" step="0.05"/></label><label>RRF 常数<input type="number" v-model.number="form.parameters.rrf_k" min="1"/></label></div><div class="form-row"><label>重排开关<select v-model="form.parameters.rerank"><option :value="false">关闭</option><option :value="true">开启</option></select></label><label>Rerank Top-N<input type="number" v-model.number="form.parameters.rerank_top_n" min="1" max="100"/></label><label>证据覆盖阈值<input type="number" v-model.number="form.parameters.evidence_coverage" min="0.1" max="1" step="0.1"/></label></div><div class="form-row"><label>生成模型<input v-model="form.parameters.model" required/></label><label>Temperature<input type="number" v-model.number="form.parameters.temperature" min="0" max="2" step="0.1"/></label><label>最大输出Token<input type="number" v-model.number="form.parameters.max_tokens" min="32" max="8192"/></label></div><div class="form-row"><label>思考模式<select v-model="form.parameters.thinking"><option :value="false">关闭</option><option :value="true">开启</option></select></label><label>输入单价 / 百万Token<input type="number" v-model.number="form.parameters.input_price" min="0" step="0.01" placeholder="未填写表示未知"/></label><label>输出单价 / 百万Token<input type="number" v-model.number="form.parameters.output_price" min="0" step="0.01" placeholder="未填写表示未知"/></label></div><p class="help">保存为新版本，已有任务使用原始配置快照。</p><div class="modal-footer"><button type="button" class="outline" @click="modal=null">取消</button><button class="primary" :disabled="busy">保存版本</button></div></form>
        <form v-if="modal==='dataset'" @submit.prevent="act(async()=>{await api(form.id?`/datasets/${form.id}`:'/datasets',{method:form.id?'PUT':'POST',body:{name:form.name,description:form.description}});modal=null;await bootstrap()})"><label>题集名称<input v-model="form.name" required/></label><label>用途说明<textarea v-model="form.description" rows="3"></textarea></label><div class="modal-footer"><button class="primary" :disabled="busy">保存题集</button></div></form>
        <form v-if="modal==='run'" @submit.prevent="startRun"><label>实验名称<input v-model="form.name" required/></label><label>评测集<select v-model="form.dataset_id" required><option v-for="d in datasets" :value="d.id">{{d.name}}（{{d.total}}题 / 已审核{{d.reviewed}}）</option></select></label><div class="form-row"><label>运行模式<select v-model="form.mode"><option value="demo">本地模拟（不收费）</option><option value="cloud">正式云API评测</option></select></label><label>并发数<input v-model.number="form.concurrency" type="number" min="1" max="20"/></label><label>人工抽样种子<input v-model.number="form.sample_seed" type="number"/></label></div><div class="section-label">选择配置版本</div><label v-for="c in configs" class="checkbox config-checkbox"><input type="checkbox" :value="c.id" v-model="selectedConfigs"/>{{c.name}}</label><div class="alert" v-if="form.mode==='cloud'">正式任务要求题目逐题人工审核，DeepSeek和Embedding凭据齐备；开启重排还需配置重排服务。</div><div class="modal-footer"><span>{{selectedConfigs.length}} 套 × {{datasets.find(d=>d.id===form.dataset_id)?.total || 0}} 题</span><button class="primary" :disabled="busy || !selectedConfigs.length"><Play :size="14"/>开始评测</button></div></form>
        <div v-if="modal==='detail' && detail" class="detail-body"><div class="detail-meta"><span class="type-tag">{{types[detail.case.type]}}</span><span class="mono">{{detail.case.id}}</span><span>{{labelConfig(detail.config_id)}}</span><span class="pill" :class="detail.state">{{stateNames[detail.state]}}</span></div><h3>{{detail.case.question}}</h3><div v-if="detail.error" class="alert error">{{detail.error}}</div><div class="section-label">标准答案</div><div class="answer-box">{{detail.case.gold_answer}}</div><div class="section-label">生成答案 <span class="muted">{{detail.generation?.model}}</span></div><div class="answer-box generated">{{detail.generation?.answer || '尚未生成'}}</div><div class="section-label">实际召回证据 · {{detail.generation?.chunks.length || 0}} 条</div><div v-for="(c,i) in detail.generation?.chunks" class="evidence-block"><div class="evidence-meta"><b>#{{i+1}}</b><span class="mono">{{c.id}}</span><span>相似度 {{number(c.vector_score)}}</span></div><p>{{c.text}}</p><a v-if="c.source_url" :href="c.source_url" target="_blank" rel="noopener noreferrer">原始来源 ↗</a></div><div class="section-label">人工独立评分 <small class="muted">先评分，再查看Judge，减少相互影响</small></div><form @submit.prevent="saveHuman"><div class="form-row"><label>准确性（1—5）<input type="number" v-model.number="form.accuracy" min="1" max="5" required/></label><label>完整性（1—5）<input type="number" v-model.number="form.completeness" min="1" max="5" required/></label><label>核验人<input v-model="form.reviewer" required/></label></div><div class="actions"><label class="checkbox"><input type="checkbox" v-model="form.refused"/>答案为拒答</label><label class="checkbox"><input type="checkbox" v-model="form.unsupported"/>存在无依据主张</label></div><label>事实错误判断<select v-model="form.factually_incorrect"><option :value="null">无法确定</option><option :value="true">确认有事实错误</option><option :value="false">未发现事实错误</option></select></label><label>核验说明<input v-model="form.review_note"/></label><div class="actions"><button class="primary" :disabled="busy || detail.state!=='succeeded'">保存人工评分</button><button type="button" class="outline" @click="judgeVisible=!judgeVisible">{{judgeVisible?'收起Judge':'查看Judge评分'}}</button></div></form><div v-if="judgeVisible" class="judge-box"><strong>准确性 {{detail.judgement?.scores.accuracy || '—'}} / 5 · 完整性 {{detail.judgement?.scores.completeness || '—'}} / 5</strong><p>{{detail.judgement?.scores.reason || '尚未评分'}}</p></div><div class="section-label">Bad Case 标签与备注 <small class="muted">初始标签为自动建议，请人工确认</small></div><div class="tag-selector"><label v-for="tag in health.tags" class="checkbox"><input type="checkbox" :value="tag" v-model="form.tags"/>{{tag}}</label></div><textarea v-model="form.note" rows="2" placeholder="记录失败根因与改进建议"></textarea><button class="outline" :disabled="busy" @click="saveTags">保存归因</button></div>
        <div v-if="modal==='history'"><div class="alert" :class="{error:!comparison?.comparable}">{{comparison?.message}}</div><div class="table-scroll"><table><thead><tr><th>配置</th><th>Recall变化</th><th>MRR变化</th><th>正确率变化</th><th>延迟变化 / ms</th></tr></thead><tbody><tr v-for="r in comparison?.rows"><td>{{labelConfig(r.config_id)}}</td><td>{{number(r.delta.recall)}}</td><td>{{number(r.delta.mrr)}}</td><td>{{number(r.delta.correct)}}</td><td>{{number(r.delta.qa_ms,0)}}</td></tr></tbody></table></div><p class="help">变化值 = 当前任务 − 所选历史任务。质量负值表示退化；延迟正值表示变慢。</p></div>
        <form v-if="modal==='document'" @submit.prevent="act(async()=>{await api('/documents',{method:'POST',body:form});modal=null;await bootstrap();feedback('原文已入库')})"><label>文档标题<input v-model="form.title" required/></label><label>来源URL<input type="url" v-model="form.source_url" required/></label><label>原文内容<textarea v-model="form.content" rows="12" required></textarea></label><div class="modal-footer"><button class="primary" :disabled="busy">保存原文</button></div></form>
        <div v-if="modal==='view-document'"><h3>{{form.title}}</h3><small class="mono">{{form.content_hash}}</small><pre class="document-content">{{form.content}}</pre></div>
        <div v-if="modal==='delete-case'"><p>删除当前题目？已有任务仍保留题目快照。</p><div class="modal-footer"><button class="outline" @click="modal=null">取消</button><button class="primary danger-fill" @click="act(async()=>{await api(`/questions/${form.row_id}`,{method:'DELETE'});modal=null;await bootstrap();await loadDataset()})">确认删除</button></div></div>
        <div v-if="modal==='delete-dataset'"><p>删除“{{form.name}}”及其中所有题目？已有任务仍保留快照。</p><div class="modal-footer"><button class="outline" @click="modal=null">取消</button><button class="primary danger-fill" @click="act(async()=>{await api(`/datasets/${form.id}`,{method:'DELETE'});selectedDataset='';modal=null;await bootstrap()})">确认删除</button></div></div>
      </section>
    </div>
  </div>
</template>
