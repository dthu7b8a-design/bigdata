import { test, expect } from '@playwright/test'
import { mkdir, readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const source = process.env.BIGDATA_RESULT ? resolve(process.env.BIGDATA_RESULT) : new URL('../../data/ads/dashboard.json', import.meta.url)
const actualData = JSON.parse(await readFile(source, 'utf8'))
const sourceDir = process.env.BIGDATA_SOURCE || fileURLToPath(new URL('../../datasets/teacher/', import.meta.url))
const screenshots = process.env.BIGDATA_SCREENSHOTS || fileURLToPath(new URL('../test-results/screenshots/', import.meta.url))
const sessionCount = new Intl.NumberFormat('zh-CN').format(actualData.kpis.sessions)
const scatterCount = new Intl.NumberFormat('zh-CN').format(actualData.charts.energy_duration.length)
const forecast = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(actualData.model.forecast[0].predicted)
async function serveActual(page) {
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }))
  await page.route('**/api/dashboard', r => r.fulfill({ json: actualData }))
}
async function shot(page, name) { await mkdir(screenshots, { recursive: true }); await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: join(screenshots, `${name}.png`), fullPage: true }) }
test('ADS 来源与教师 CSV 的原始字节哈希一致', async () => {
  for (const [name, expected] of Object.entries(actualData.meta.source_sha256)) {
    expect(createHash('sha256').update(await readFile(join(sourceDir, name))).digest('hex')).toBe(expected)
  }
})
test('真实 ADS 数据：三页面、DataV、图表、度量切换', async ({ page }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message))
  await serveActual(page); await page.goto('/')
  await expect(page.locator('.kpi-value').first()).toHaveText(`${sessionCount}次`)
  await expect(page.locator('input[type=date]')).toHaveCount(0)
  await expect(page.locator('.insight-wrap svg').first()).toBeVisible()
  await expect(page.locator('canvas')).toHaveCount(4)
  await page.waitForTimeout(1500); await shot(page, 'overview')
  await page.getByRole('button', { name: /多维分析/ }).click()
  await expect(page.getByText(`${scatterCount} 条有效会话`, { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '充电电量', exact: true }).click()
  await page.getByRole('button', { name: '单次平均电量', exact: true }).click()
  await expect(page.locator('.chart-panel')).toHaveCount(10)
  for (const host of await page.locator('.chart-panel .chart').all()) await expect(host.locator('canvas').first()).toBeVisible()
  await page.waitForTimeout(1200); await shot(page, 'analysis')
  await page.getByRole('button', { name: /质量与预测/ }).click()
  await expect(page.getByText('年份0014/0015规范化', { exact: true })).toBeVisible()
  await expect(page.locator('.forecast-card strong').first()).toHaveText(`${forecast} kWh`)
  await expect(page.getByText('已选用', { exact: true })).toBeVisible()
  await page.waitForTimeout(1000); await shot(page, 'quality')
  expect(errors).toEqual([])
})
test('移动端布局与真实图表', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await serveActual(page); await page.goto('/')
  await expect(page.locator('.kpi-value').first()).toHaveText(`${sessionCount}次`)
  for (const name of [/运行总览/, /多维分析/, /质量与预测/]) {
    await page.getByRole('button', { name }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  await page.getByRole('button', { name: /运行总览/ }).click(); await page.waitForTimeout(1000); await shot(page, 'mobile')
})
test('HTTP 错误不显示伪造 KPI，重试后恢复真实数据', async ({ page }) => {
  await page.route('**/api/health', r => r.fulfill({ status: 503 }))
  await page.route('**/api/dashboard', r => r.fulfill({ status: 503 }))
  await page.goto('/'); await expect(page.getByRole('alert')).toContainText('HTTP 503')
  await expect(page.locator('.kpi')).toHaveCount(0); await shot(page, 'error')
  await page.unroute('**/api/dashboard'); await page.route('**/api/dashboard', r => r.fulfill({ json: actualData }))
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.locator('.kpi-value').first()).toHaveText(`${sessionCount}次`)
})
test('空数据与缺失维度均有明确状态', async ({ page }) => {
  await page.route('**/api/health', r => r.fulfill({ json: {} }))
  await page.route('**/api/dashboard', r => r.fulfill({ json: { meta: {}, kpis: { sessions: 0 }, charts: {}, quality: {}, model: {} } }))
  await page.goto('/'); await expect(page.getByText('当前数据集暂无充电记录', { exact: false })).toBeVisible()
  await expect(page.getByText('该维度暂无可用数据')).toHaveCount(4)
  await expect(page.locator('.kpi-value').nth(1)).toContainText('—'); await shot(page, 'empty')
  await page.getByRole('button', { name: /质量与预测/ }).click()
  await expect(page.getByText('尚无可用模型评估结果')).toBeVisible()
})
test('无效 JSON 和错误契约清晰报错', async ({ page }) => {
  await page.route('**/api/dashboard', r => r.fulfill({ body: '<html>not json</html>', contentType: 'text/html' }))
  await page.goto('/'); await expect(page.getByRole('alert')).toContainText('有效 JSON')
  await page.unroute('**/api/dashboard'); await page.route('**/api/dashboard', r => r.fulfill({ json: { broken: true } }))
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.getByRole('alert')).toContainText('契约')
})
test('加载状态可见，不显示旧数据', async ({ page }) => {
  let release
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/dashboard', async r => { await gate; await r.fulfill({ json: actualData }) })
  await page.goto('/'); await expect(page.getByRole('status')).toContainText('正在读取真实充电数据')
  await expect(page.locator('.kpi')).toHaveCount(0); release()
  await expect(page.locator('.kpi-value').first()).toHaveText(`${sessionCount}次`)
})
test('Flask 在线时执行真实 HTTP 集成', async ({ page, request }) => {
  let available = false
  try { available = (await request.get('http://127.0.0.1:5000/api/health', { timeout: 5000 })).ok() } catch {}
  test.skip(!available, 'Flask 5000 尚未启动；其他用例直接读取真实 ADS 文件，不使用合成业务数据。')
  const errors = []; page.on('pageerror', e => errors.push(e.message))
  await page.goto('http://127.0.0.1:5000/'); await expect(page.locator('.kpi-value').first()).toHaveText(`${sessionCount}次`)
  await page.waitForTimeout(1200); await shot(page, 'live-flask')
  await page.getByRole('button', { name: /多维分析/ }).click()
  await expect(page.locator('.chart-panel')).toHaveCount(10)
  await page.waitForTimeout(1200); await shot(page, 'live-analysis')
  await page.getByRole('button', { name: /质量与预测/ }).click()
  await expect(page.getByText('已选用', { exact: true })).toBeVisible()
  await page.waitForTimeout(1200); await shot(page, 'live-quality')
  expect(errors).toEqual([])
})
