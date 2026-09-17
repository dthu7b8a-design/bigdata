import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests', timeout: 60000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:4173', viewport: { width: 1600, height: 1100 }, launchOptions: { executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', args: ['--disable-crash-reporter'] } },
  webServer: { command: '"D:/node/node.exe" node_modules/vite/bin/vite.js preview --host 127.0.0.1', url: 'http://127.0.0.1:4173', reuseExistingServer: true, timeout: 30000 },
  reporter: [['list'], ['html', { open: 'never' }]]
})
