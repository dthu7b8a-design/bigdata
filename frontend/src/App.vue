<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { BorderBox1 } from '@dataview/datav-vue3'
import ChartPanel from './ChartPanel.vue'
import { numeric, rows, dailyChart, seriesChart, donut, heatmap, crossChart, predictionChart, scatterChart } from './charts.js'

const tabs = [{ id: 'overview', name: '运行总览', en: 'OVERVIEW', icon: '◈' }, { id: 'analysis', name: '多维分析', en: 'EXPLORATION', icon: '▦' }, { id: 'quality', name: '质量与预测', en: 'QUALITY & FORECAST', icon: '⌁' }]
const tab = ref('overview'), data = ref(null), loading = ref(false), error = ref(''), health = ref('checking'), metric = ref('sessions'), crossMetric = ref('sessions')
let controller, requestId = 0
const c = computed(() => data.value?.charts || {}), model = computed(() => data.value?.model || {}), meta = computed(() => data.value?.meta || {})
const metricLabel = computed(() => metric.value === 'sessions' ? '充电次数' : '电量 (kWh)')
const isEmpty = computed(() => data.value && (numeric(data.value.kpis?.sessions) === 0 || (!Object.values(c.value).some(a => Array.isArray(a) && a.length) && numeric(data.value.kpis?.sessions) === null)))
function format(v, digits = 0) { const n = numeric(v); return n === null ? '—' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(n) }
const kpis = computed(() => [
  ['累计充电次数', 'sessions', '次', '↗', 0], ['累计充电电量', 'energy_kwh', 'kWh', 'ϟ', 1], ['覆盖充电站点', 'stations', '个', '▦', 0], ['独立充电用户', 'users', '人', '♙', 0], ['平均连接时长', 'avg_duration_h', '小时', '◷', 2], ['累计原始费用', 'fees', '', '≋', 2]
])
const bestStation = computed(() => [...rows(c.value.stations)].sort((a, b) => (numeric(b.sessions) ?? -1) - (numeric(a.sessions) ?? -1))[0])
const peak = computed(() => [...rows(c.value.hourly)].sort((a, b) => (numeric(b.sessions) ?? -1) - (numeric(a.sessions) ?? -1))[0])
const qualityRows = computed(() => Object.entries(data.value?.quality || {}).filter(([key]) => !['before', 'after', 'rules', 'summary'].includes(key)).map(([key, value]) => ({ key, label: labels[key] || key, value })))
const modelDetails = computed(() => Object.entries(model.value).filter(([k]) => !['metrics', 'predictions', 'forecast'].includes(k)))
const labels = { source_rows: '原始记录数', total_rows: '总记录数', valid_rows: '有效记录数', clean_rows: '清洗后记录数', removed_rows: '剔除记录数', duplicate_rows: '重复记录数', duplicates: '重复记录', missing_values: '缺失值', missing: '缺失情况', invalid_rows: '异常记录数', missing_rate: '缺失率', rules: '清洗规则', summary: '质量摘要', selected_model: '选用模型', target: '预测目标', target_unit: '目标单位', status: '模型状态', message: '说明', train_size: '训练样本数', test_size: '测试样本数', split_date: '数据划分日期', features: '特征', horizon: '预测步数' }
Object.assign(labels, { before: '清洗前', after: '清洗后', duration_iqr: '时长 IQR 阈值', reconciliation: '多维汇总一致性', limitations: '适用范围与限制', split: '训练 / 验证 / 测试划分', selection_rule: '模型选择规则', validation_metrics: '验证集完整评估', ml_forecasts: '各模型历史次日预测' })
function detail(v) { return v === null || v === undefined ? '未提供' : Array.isArray(v) && v.every(x => typeof x !== 'object') ? v.map(x => `· ${x}`).join('\n') : typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v) }
async function load() {
  controller?.abort(); controller = new AbortController(); const ownController = controller, id = ++requestId
  loading.value = true; error.value = ''; data.value = null
  const timeout = setTimeout(() => ownController.abort(), 45000)
  try {
    const response = await fetch('/api/dashboard', { signal: ownController.signal, headers: { Accept: 'application/json' } })
    if (!response.ok) throw new Error(`数据服务返回 HTTP ${response.status}，请确认 Flask 服务及数据加载状态。`)
    const payload = await response.json()
    if (!payload || typeof payload !== 'object' || !payload.meta || !payload.kpis || !payload.charts) throw new Error('接口响应格式不符合 dashboard 契约（缺少 meta / kpis / charts）。')
    if (id === requestId) data.value = payload
  } catch (e) { if (id === requestId) error.value = e.name === 'AbortError' ? '请求超时（45 秒），请检查服务后重试。' : e instanceof SyntaxError ? '接口未返回有效 JSON，请检查 /api/dashboard 路由。' : e.message || '无法连接数据服务。' }
  finally { clearTimeout(timeout); if (id === requestId) loading.value = false }
}
async function checkHealth() { try { const response = await fetch('/api/health', { signal: AbortSignal.timeout(6000) }); health.value = response.ok ? 'online' : 'offline' } catch { health.value = 'offline' } }
function refresh() { load(); checkHealth() }
function ranked(key, name = 'name', limit = 12) { return seriesChart([...rows(c.value[key])].sort((a, b) => (numeric(b[metric.value]) ?? -1) - (numeric(a[metric.value]) ?? -1)).slice(0, limit), name, metric.value, 'bar', true, metricLabel.value) }
onMounted(refresh)
onBeforeUnmount(() => { ++requestId; controller?.abort() })
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="tab = 'overview'"><span class="brand-icon">ϟ</span><div>EV INSIGHT<small>充电数据观测中心</small></div></a>
      <div class="sidebar-caption">数据工作空间 / PHASE 02</div>
      <nav aria-label="主导航"><button v-for="item in tabs" :key="item.id" :class="['nav-item', { active: tab === item.id }]" :aria-current="tab === item.id ? 'page' : undefined" @click="tab = item.id"><span>{{ item.icon }}</span><div>{{ item.name }}<small>{{ item.en }}</small></div><b v-if="tab === item.id">›</b></button></nav>
      <div class="sidebar-bottom"><span class="tiny-label">ANALYTICS STACK</span><p>Vue 3 <i>·</i> DataV <i>·</i> ECharts</p><div class="status-line"><span :class="['dot', health]"></span>{{ health === 'online' ? '数据服务在线' : health === 'checking' ? '检查服务中' : '健康检查不可用' }}</div><small>只读分析 · 数据来自后端接口</small></div>
    </aside>
    <main>
      <header class="topbar"><div class="breadcrumb">第二阶段 <span>/</span> 充电运营分析 <span>/</span> {{ tabs.find(t => t.id === tab).name }}</div><span class="project-badge">BIG DATA LAB <b>02</b></span></header>
      <section class="page-heading"><div><div class="eyebrow">ELECTRIC VEHICLE · DATA OBSERVATORY</div><h1>{{ tab === 'overview' ? '每一次充电，都有迹可循。' : tab === 'analysis' ? '从多重视角，理解充电行为。' : '让数据可信，让趋势可见。' }}</h1><p>{{ tab === 'overview' ? '汇聚充电规模、时序变化与站点表现，掌握运营全貌。' : tab === 'analysis' ? '连接时间、空间与用户特征，探索电动汽车充电规律。' : '追溯数据质量，比较模型效果，查看验证与未来预测。' }}</p></div><span class="heading-symbol">{{ tab === 'quality' ? '⌁' : 'ϟ' }}</span></section>
      <div class="filter-bar"><div class="filter-title"><span>◷</span> 数据时间范围</div><strong class="date-range">{{ meta.range_start || '—' }} <span>→</span> {{ meta.range_end || '—' }}</strong><span class="range-note">历史教学数据 · 全量统计</span><button type="button" class="refresh-button" @click="refresh" :disabled="loading" aria-label="刷新数据">↻</button></div>
      <div class="source-line"><span class="dot" :class="data ? 'online' : ''"></span><span>来源：{{ meta.source || '等待接口返回数据来源' }}</span><span v-if="data">实际范围 {{ meta.range_start || '未提供' }} → {{ meta.range_end || '未提供' }}</span><span v-if="data" class="updated">更新于 {{ meta.updated_at || '未提供' }}</span></div>
      <div v-if="error" role="alert" class="state error"><span>!</span><div><h2>暂时无法展示数据</h2><p>{{ error }}</p><button class="primary" @click="refresh">重新加载</button></div></div>
      <div v-if="loading" role="status" class="state loading"><div class="spinner"></div><div><h2>正在读取真实充电数据</h2><p>正在请求 /api/dashboard，图表将在数据返回后呈现。</p></div></div>
      <template v-if="data && !loading && !error">
        <div v-if="isEmpty" class="notice" role="status">当前数据集暂无充电记录；未提供的指标以“—”显示。</div>
        <section class="kpi-grid" aria-label="关键指标"><article v-for="[name, key, unit, icon, digits] in kpis" :key="key" class="kpi"><div class="kpi-top"><span>{{ name }}</span><span class="kpi-icon">{{ icon }}</span></div><div class="kpi-value">{{ format(data.kpis[key], digits) }}<small>{{ unit }}</small></div><div class="kpi-foot"><span></span>{{ key === 'fees' ? (meta.currency || '原始费用单位（未标明币种）') : '当前返回数据范围' }}</div></article></section>
        <template v-if="tab === 'overview'">
          <div class="section-title"><h2>运营脉搏 <small>OPERATION PULSE</small></h2><span>按日聚合 · 真实记录</span></div>
          <div class="chart-grid overview-grid"><ChartPanel title="充电趋势" subtitle="充电次数与电量 · 双轴展示 / 滚轮缩放" :option="dailyChart(c.daily)" :empty="!rows(c.daily).length" wide /><section class="insight-wrap"><BorderBox1 :color="['#23415b', '#38d6cf']" background-color="#102235"><div class="insight"><div class="eyebrow">OBSERVATION</div><h3>数据观察</h3><div class="insight-stat"><span>充电高峰小时</span><strong>{{ peak ? `${peak.hour}:00` : '—' }}</strong><p>{{ peak ? `${format(peak.sessions)} 次充电记录` : '等待小时分布数据' }}</p></div><div class="insight-stat"><span>充电次数最多的站点</span><strong class="station-name">{{ bestStation?.name || bestStation?.station_id || '—' }}</strong><p>{{ bestStation ? `${format(bestStation.sessions)} 次 · ${format(bestStation.energy_kwh, 1)} kWh` : '等待站点统计数据' }}</p></div><div class="insight-note">观察基于当前接口返回的聚合数据。</div></div></BorderBox1></section>
            <ChartPanel title="24 小时充电节律" subtitle="小时维度 · 充电次数" :option="seriesChart(c.hourly, 'hour', 'sessions', 'line')" :empty="!rows(c.hourly).length" />
            <ChartPanel title="一周充电分布" subtitle="星期维度 · 充电次数" :option="seriesChart(c.weekday, 'weekday', 'sessions')" :empty="!rows(c.weekday).length" />
            <ChartPanel title="站点充电排名" subtitle="按充电次数排序 · Top 10" :option="seriesChart([...rows(c.stations)].sort((a,b) => b.sessions-a.sessions).slice(0,10), 'name', 'sessions', 'bar', true)" :empty="!rows(c.stations).length" />
          </div>
        </template>
        <template v-else-if="tab === 'analysis'">
          <div class="section-title"><h2>多维画像 <small>DIMENSION EXPLORER</small></h2><div class="segmented" aria-label="分析度量"><button :class="{ selected: metric === 'sessions' }" @click="metric = 'sessions'">充电次数</button><button :class="{ selected: metric === 'energy_kwh' }" @click="metric = 'energy_kwh'">充电电量</button></div></div>
          <div class="notice">设施类型按清洗规则映射，未定义编码保留未知标签；managerVehicle 的 0/1 保留原值，不推测含义。连接时长不等于持续通电时长。</div>
          <div class="chart-grid">
            <ChartPanel title="区域分布" :subtitle="`位置维度 · ${metricLabel} / Top 12`" :option="ranked('locations')" :empty="!rows(c.locations).length" />
            <ChartPanel title="设施类型构成" :subtitle="`设施维度 · ${metricLabel}`" :option="donut(c.facility, 'facility_type', metric, metricLabel)" :empty="!rows(c.facility).length" />
            <ChartPanel title="平台来源构成" :subtitle="`平台维度 · ${metricLabel}`" :option="donut(c.platform, 'platform', metric, metricLabel)" :empty="!rows(c.platform).length" />
            <ChartPanel title="车辆管理属性" :subtitle="`车辆维度 · ${metricLabel}`" :option="donut(c.vehicle, 'manager_vehicle', metric, metricLabel)" :empty="!rows(c.vehicle).length" />
            <ChartPanel title="用户充电排名" :subtitle="`用户维度 · ${metricLabel} / Top 12`" :option="ranked('users', 'user_id')" :empty="!rows(c.users).length" />
            <ChartPanel title="充电时长分布" subtitle="时长维度 · 各区间充电次数" :option="seriesChart(c.duration, 'bucket', 'sessions')" :empty="!rows(c.duration).length" />
            <ChartPanel title="站点 × 小时" subtitle="交叉分析 01 · 颜色越亮，充电次数越多 / 滚轮查看站点" :option="heatmap(c.station_hour)" :empty="!rows(c.station_hour).length" wide />
            <ChartPanel title="站点平均连接时长" subtitle="站点维度 · 小时 / Top 12" :option="seriesChart([...rows(c.stations)].sort((a,b) => b.avg_duration_h-a.avg_duration_h).slice(0,12), 'name', 'avg_duration_h', 'bar', true, '平均连接时长 (h)')" :empty="!rows(c.stations).length" />
            <ChartPanel title="连接时长 × 充电电量" :subtitle="`会话级散点 · ${format(rows(c.energy_duration).length)} 条有效会话 / 滚轮缩放`" :option="scatterChart(c.energy_duration)" :empty="!rows(c.energy_duration).length" wide />
          </div>
          <div class="section-title"><h2>平台 × 工作日类型 <small>CROSS ANALYSIS 02</small></h2><div class="segmented"><button :class="{ selected: crossMetric === 'sessions' }" @click="crossMetric = 'sessions'">次数对比</button><button :class="{ selected: crossMetric === 'avg_energy_kwh' }" @click="crossMetric = 'avg_energy_kwh'">单次平均电量</button></div></div>
          <ChartPanel title="不同平台的日类型差异" :subtitle="crossMetric === 'sessions' ? '按 day_type 分组 · 单位：次' : '按 day_type 分组 · 单位：kWh / 次'" :option="crossChart(c.platform_daytype, crossMetric)" :empty="!rows(c.platform_daytype).length" />
        </template>
        <template v-else>
          <div class="section-title"><h2>数据质量 <small>DATA QUALITY</small></h2><span>按后端清洗报告原值展示</span></div>
          <div class="notice">{{ data.quality?.summary || '后端尚未提供质量摘要。' }}</div>
          <div class="quality-grid quality-counts"><article v-for="[key,name] in [['sessions','充电会话'],['stations','充电站点'],['telemetry','电池采样']]" :key="key" class="panel quality-card"><h3>{{ name }} · 清洗前 → 清洗后</h3><div class="quality-number">{{ format(data.quality?.before?.[key]) }} <span>→</span> {{ format(data.quality?.after?.[key]) }}</div></article></div>
          <section class="panel table-panel rules-table"><table><caption>清洗规则与受影响记录（各规则可能重叠，不可相加）</caption><thead><tr><th>规则</th><th>问题</th><th>记录数</th><th>处理方式</th></tr></thead><tbody><tr v-for="rule in rows(data.quality?.rules)" :key="rule.id"><td>{{ rule.id }}</td><td>{{ rule.issue }}</td><td>{{ format(rule.count) }}</td><td>{{ rule.action }}</td></tr><tr v-if="!rows(data.quality?.rules).length"><td colspan="4">尚未提供清洗规则</td></tr></tbody></table></section>
          <div class="quality-grid"><article v-for="item in qualityRows" :key="item.key" class="panel quality-card"><h3>{{ item.label }}</h3><small>{{ item.key }}</small><pre>{{ detail(item.value) }}</pre></article></div>
          <div class="section-title"><h2>预测表现 <small>MODEL EVALUATION</small></h2><span>MAE / RMSE 越低越好 · R² 越接近 1 越好</span></div>
          <section class="panel table-panel"><table><caption>测试集指标对比 · 选用模型：{{ model.selected_model || '未提供' }} · 模型选择依据验证集 RMSE</caption><thead><tr><th>模型</th><th>测试 MAE</th><th>测试 RMSE</th><th>测试 R²</th><th>验证 RMSE</th></tr></thead><tbody><tr v-for="(item,i) in rows(model.metrics)" :key="i"><td>{{ item.model }} <span v-if="item.model === model.selected_model" class="chosen">已选用</span></td><td>{{ format(item.mae, 4) }}</td><td>{{ format(item.rmse, 4) }}</td><td>{{ format(item.r2, 4) }}</td><td>{{ format(item.validation_rmse,4) }}</td></tr><tr v-if="!rows(model.metrics).length"><td colspan="5" class="table-empty">尚无可用模型评估结果</td></tr></tbody></table></section>
          <div class="prediction"><ChartPanel title="测试集实际值与单步预测" :subtitle="`预测目标：${model.target || '后端未提供'} · 高亮点为历史数据结束后的次日预测`" :option="predictionChart(model.predictions, model.forecast)" :empty="!rows(model.predictions).length && !rows(model.forecast).length" /></div>
          <div v-for="item in rows(model.forecast)" :key="item.date" class="forecast-card"><span>历史次日预测 · {{ item.date }}</span><strong>{{ format(item.predicted,2) }} <small>kWh</small></strong><span>{{ model.selected_model || '未提供模型' }} · 单步估计</span></div>
          <div class="notice">预测值为模型估计；评估范围、特征与训练信息以以下后端报告为准。</div>
          <div class="quality-grid"><article v-for="[key,value] in modelDetails" :key="key" class="panel quality-card"><h3>{{ labels[key] || key }}</h3><pre>{{ detail(value) }}</pre></article></div>
        </template>
      </template>
      <footer><span>EV INSIGHT / 充电数据观测中心</span><span v-if="meta.run_id">运行批次 {{ meta.run_id }}</span><span>第二阶段 · 大数据分析与可视化</span></footer>
    </main>
  </div>
</template>
