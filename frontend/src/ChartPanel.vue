<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, HeatmapChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([BarChart, LineChart, PieChart, HeatmapChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, VisualMapComponent, CanvasRenderer])
const props = defineProps({ title: String, subtitle: String, option: Object, empty: Boolean, wide: Boolean })
const host = ref(null)
let chart, observer
function render() { if (chart && props.option && !props.empty) chart.setOption(props.option, true) }
onMounted(() => { chart = echarts.init(host.value, null, { renderer: 'canvas' }); observer = new ResizeObserver(() => chart.resize()); observer.observe(host.value); render() })
watch(() => [props.option, props.empty], render, { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template>
  <section class="panel chart-panel" :class="{ wide }">
    <div class="panel-heading"><div><h3>{{ title }}</h3><p>{{ subtitle }}</p></div><span class="panel-mark">▥</span></div>
    <div class="chart-body"><div ref="host" class="chart" :aria-label="title" role="img" :style="{ visibility: empty ? 'hidden' : 'visible' }"></div><div v-if="empty" class="chart-empty">该维度暂无可用数据</div></div>
  </section>
</template>
