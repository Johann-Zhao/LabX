// 登录认证全流程走查：intro→登录页→学生/管理员分流→权限拦截→退出
const { chromium } = require('C:/Users/matebook 14/AppData/Local/npm-cache/_npx/9833c18b2d85bc59/node_modules/playwright')

;(async () => {
  const b = await chromium.launch({ channel: 'chrome' })
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 } })
  const p = await ctx.newPage()
  const ok = (name, cond) => console.log(cond ? `PASS ${name}` : `FAIL ${name}`)

  // 1. 首访：守卫先弹 /login，intro 覆盖其上
  await p.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
  await p.waitForTimeout(1200)
  ok('未登录跳/login', p.url().includes('/login'))
  ok('intro 在播', await p.evaluate(() => !!document.querySelector('.intro-scroller')))

  // 2. 跳过 intro → 登录页可见
  await p.click('button:has-text("跳过")')
  await p.waitForTimeout(800)
  ok('登录表单可见', await p.evaluate(() => !!document.querySelector('input') && document.body.innerText.includes('学号')))
  await p.screenshot({ path: 'verify-login-page.png' })

  // 3. 错误密码 → 1008 提示
  await p.fill('input >> nth=0', '2024001')
  await p.fill('input[type="password"]', 'wrong1')
  await p.keyboard.press('Enter')
  await p.waitForTimeout(1200)
  ok('错误密码有提示', await p.evaluate(() => document.body.innerText.includes('学号或密码错误')))

  // 4. 学生正确登录 → 首页，无"管理"tab
  await p.fill('input[type="password"]', '123456')
  await p.keyboard.press('Enter')
  await p.waitForTimeout(1500)
  ok('学生登录回首页', p.url() === 'http://localhost:5173/')
  const tabs1 = await p.evaluate(() => [...document.querySelectorAll('a.tab')].map(a => a.getAttribute('href')))
  ok('学生无管理tab', !tabs1.includes('/admin') && tabs1.includes('/materials'))
  await p.screenshot({ path: 'verify-student-home.png' })

  // 5. 学生直闯 /admin → 挡回 /
  await p.goto('http://localhost:5173/admin')
  await p.waitForTimeout(800)
  ok('学生闯/admin被挡回', p.url() === 'http://localhost:5173/')

  // 6. 退出登录 → 回 /login
  await p.click('button:has-text("退出")')
  await p.waitForTimeout(800)
  ok('退出回/login', p.url().includes('/login'))

  // 7. 管理员登录 → 默认 /admin
  await p.fill('input >> nth=0', 'admin')
  await p.fill('input[type="password"]', 'admin888')
  await p.keyboard.press('Enter')
  await p.waitForTimeout(1500)
  ok('管理员登录进/admin', p.url().includes('/admin'))
  await p.screenshot({ path: 'verify-admin-home.png' })

  // 8. 管理员左下返回学生端 → 首页有"管理"tab
  await p.click('text=返回学生端')
  await p.waitForTimeout(1000)
  ok('返回学生端到首页', p.url() === 'http://localhost:5173/')
  const tabs2 = await p.evaluate(() => [...document.querySelectorAll('a.tab')].map(a => a.getAttribute('href')))
  ok('管理员有管理tab', tabs2.includes('/admin'))

  // 9. 刷新保持登录态
  await p.reload({ waitUntil: 'networkidle' })
  await p.waitForTimeout(800)
  ok('刷新保持登录', !p.url().includes('/login'))

  await b.close()
  console.log('WALKTHROUGH_DONE')
})().catch((e) => { console.error('ERROR', e.message); process.exit(1) })
