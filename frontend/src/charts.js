const colors = ['#7ce38b', '#548dff', '#b4a0ff', '#f6c873', '#5bc8ee', '#38d6cf', '#fa929e']
export const numeric = v => v !== null && v !== '' && v !== undefined && Number.isFinite(Number(v)) ? Number(v) : null
export const rows = v => Array.isArray(v) ? v : []
const base = () => ({ color: colors, backgroundColor: 'transparent', textStyle: { color: '#99adc0', fontFamily: 'Microsoft YaHei, sans-serif' }, tooltip: { trigger: 'axis', confine: true, backgroundColor: '#13273a', borderColor: '#30506b', textStyle: { color: '#ecf6ff' } }, grid: { left: 18, right: 24, top: 42, bottom: 18, containLabel: true }, legend: { top: 0, textStyle: { color: '#aabdd0' }, icon: 'roundRect' } })
const axis = (type, data) => ({ type, data, axisLine: { lineStyle: { color: '#294154' } }, axisTick: { show: false }, axisLabel: { color: '#92a7bc', hideOverlap: true }, splitLine: { show: type === 'value', lineStyle: { color: '#1b3042', type: 'dashed' } } })
export function seriesChart(data, key, metric, type = 'bar', horizontal = false, label = '充电次数') {
  let items = [...rows(data)]
  if (key === 'hour') items.sort((a, b) => Number(a.hour) - Number(b.hour))
  if (key === 'weekday') {
    const order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    const labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    items.sort((a, b) => order.indexOf(a.weekday) - order.indexOf(b.weekday))
    items = items.map(r => ({ ...r, weekday: labels[order.indexOf(r.weekday)] ?? r.weekday }))
  }
  const category = axis('category', items.map(r => String(r[key] ?? '未知')))
  if (horizontal) { category.inverse = true; category.axisLabel.width = 90; category.axisLabel.overflow = 'truncate' }
  return { ...base(), xAxis: horizontal ? axis('value') : category, yAxis: horizontal ? category : axis('value'), series: [{ name: label, type, data: items.map(r => numeric(r[metric])), smooth: true, barMaxWidth: 22, showSymbol: items.length < 30, itemStyle: { borderRadius: type === 'bar' ? 3 : 0 }, areaStyle: type === 'line' ? { opacity: 0.1 } : undefined }], ...(items.length > 25 ? { dataZoom: [{ type: 'inside', ...(horizontal ? { yAxisIndex: 0 } : {}), start: 0, end: Math.min(100, 25 / items.length * 100) }] } : {}) }
}
export function dailyChart(data) {
  return { ...base(), xAxis: axis('category', rows(data).map(r => r.date)), yAxis: [axis('value'), { ...axis('value'), splitLine: { show: false } }], series: [{ name: '充电次数', type: 'bar', barMaxWidth: 18, data: rows(data).map(r => numeric(r.sessions)), itemStyle: { opacity: 0.6 } }, { name: '电量 (kWh)', type: 'line', smooth: true, yAxisIndex: 1, showSymbol: false, data: rows(data).map(r => numeric(r.energy_kwh)) }], dataZoom: [{ type: 'inside' }] }
}
export function donut(data, key, metric, label) {
  return { ...base(), tooltip: { ...base().tooltip, trigger: 'item', formatter: '{b}<br/>{a}: {c} ({d}%)' }, legend: { type: 'scroll', bottom: 0, textStyle: { color: '#aabdd0' } }, series: [{ name: label, type: 'pie', radius: ['44%', '67%'], center: ['50%', '44%'], itemStyle: { borderColor: '#101f30', borderWidth: 4, borderRadius: 5 }, label: { color: '#b8cbdc', formatter: '{b}\n{d}%', overflow: 'truncate', width: 90 }, data: rows(data).map(r => ({ name: String(r[key] ?? '未知'), value: numeric(r[metric]) })) }] }
}
export function heatmap(data) {
  const items = rows(data), ids = [...new Set(items.map(r => r.station_id))]
  const names = ids.map(id => String(items.find(r => r.station_id === id)?.name ?? id))
  return { ...base(), grid: { left: 15, right: 24, top: 12, bottom: 52, containLabel: true }, xAxis: axis('category', Array.from({ length: 24 }, (_, i) => `${i}时`)), yAxis: { ...axis('category', names), axisLabel: { width: 85, overflow: 'truncate' } }, visualMap: { min: 0, max: Math.max(1, ...items.map(r => numeric(r.sessions) ?? 0)), calculable: true, orient: 'horizontal', left: 'center', bottom: 0, textStyle: { color: '#aabdd0' }, inRange: { color: ['#152a42', '#226a89', '#3ce2cf'] } }, tooltip: { ...base().tooltip, trigger: 'item', formatter: p => `${echartsEscape(names[p.value[1]])}<br/>${p.value[0]}时 · ${p.value[2]}次` }, series: [{ type: 'heatmap', data: items.map(r => [Number(r.hour), ids.indexOf(r.station_id), numeric(r.sessions)]) }], ...(ids.length > 15 ? { dataZoom: [{ type: 'inside', yAxisIndex: 0, start: 0, end: 15 / ids.length * 100 }] } : {}) }
}
function echartsEscape(v) { return String(v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]) }
export function crossChart(data, metric = 'sessions') {
  const items = rows(data), platforms = [...new Set(items.map(r => r.platform))], types = [...new Set(items.map(r => r.day_type))]
  return { ...base(), xAxis: axis('category', platforms), yAxis: axis('value'), series: types.map(t => ({ name: String(t), type: 'bar', barMaxWidth: 28, data: platforms.map(p => numeric(items.find(r => r.platform === p && r.day_type === t)?.[metric])) })) }
}
export function predictionChart(predictions, forecast) {
  const past = rows(predictions), future = rows(forecast), dates = [...new Set([...past, ...future].map(r => r.date))].sort()
  return { ...base(), xAxis: axis('category', dates), yAxis: axis('value'), series: [{ name: '测试集实际值', type: 'line', showSymbol: false, data: dates.map(d => numeric(past.find(r => r.date === d)?.actual)) }, { name: '测试集预测', type: 'line', showSymbol: false, data: dates.map(d => numeric(past.find(r => r.date === d)?.predicted)) }, { name: '历史次日预测', type: 'scatter', symbol: 'diamond', symbolSize: 12, data: dates.map(d => numeric(future.find(r => r.date === d)?.predicted)) }], dataZoom: [{ type: 'inside' }] }
}
export function scatterChart(data) {
  return { ...base(), grid: { left: 20, right: 24, top: 32, bottom: 40, containLabel: true }, xAxis: { ...axis('value'), name: '连接时长 (h)', nameLocation: 'middle', nameGap: 28 }, yAxis: { ...axis('value'), name: '电量 (kWh)' }, tooltip: { ...base().tooltip, trigger: 'item', formatter: p => `会话 ${echartsEscape(p.value[2])}<br/>连接时长 ${p.value[0]} h<br/>电量 ${p.value[1]} kWh` }, dataZoom: [{ type: 'inside' }], series: [{ name: '充电会话', type: 'scatter', symbolSize: 5, itemStyle: { opacity: 0.45 }, data: rows(data).map(r => [numeric(r.duration_h), numeric(r.energy_kwh), r.session_id]) }] }
}
