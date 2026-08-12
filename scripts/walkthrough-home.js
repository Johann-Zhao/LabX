// 主界面重构走查：桌面三栏 + 手机单列截图
// playwright 通过 npx 缓存提供，用绝对路径 require（npm-global 里没有实体包）
const { chromium } = require('C:/Users/matebook 14/AppData/Local/npm-cache/_npx/9833c18b2d85bc59/node_modules/playwright')

;(async () => {
  // 用本机 Chrome（缓存的 playwright 版本与已下载浏览器不一致，走系统 Chrome 通道）
  const browser = await chromium.launch({ channel: 'chrome' })

  // 桌面 1440px：应出现左能力矩阵 + 中对话 + 右物料精选
  const dctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const dpage = await dctx.newPage()
  await dpage.addInitScript(() => localStorage.setItem('labx_intro_seen', '1'))
  await dpage.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
  await dpage.waitForTimeout(1200)
  await dpage.screenshot({ path: '/tmp/labx-home-desktop.png' })

  // 桌面：点一条指令行发送，看对话态（用 mock 或真实流式都可，只截过程显化）
  await dpage.click('.cmd-row:first-child')
  await dpage.waitForTimeout(2500)
  await dpage.screenshot({ path: '/tmp/labx-home-chat.png' })

  // 手机 375px：单列，对话在上，侧轨沉底
  const mctx = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true })
  const mpage = await mctx.newPage()
  await mpage.addInitScript(() => localStorage.setItem('labx_intro_seen', '1'))
  await mpage.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
  await mpage.waitForTimeout(1200)
  await mpage.screenshot({ path: '/tmp/labx-home-mobile.png' })
  // 滚到页面底部看沉底的侧轨
  await mpage.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await mpage.waitForTimeout(600)
  await mpage.screenshot({ path: '/tmp/labx-home-mobile-rails.png' })

  await browser.close()
  console.log('SHOTS_DONE')
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
