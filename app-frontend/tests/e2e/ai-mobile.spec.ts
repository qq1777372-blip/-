import { expect, test } from '@playwright/test'

const routes = [
  '/app/tabs/module/ai-workspace',
  '/app/tabs/module/ai-models',
  '/app/tabs/module/ai-knowledge',
  '/app/tabs/module/ai-operations',
  '/app/tabs/module/ai-capabilities',
  '/app/tabs/manage/peers',
  '/app/tabs/manage/licenses',
  '/app/tabs/manage/account-usage',
  '/app/tabs/manage/devices',
]
const titles: Record<string, string> = {
  '/app/tabs/module/ai-workspace': 'AI 工作台',
  '/app/tabs/module/ai-models': 'AI 模型中心',
  '/app/tabs/module/ai-knowledge': 'AI 知识库',
  '/app/tabs/module/ai-operations': 'AI 运行与治理',
  '/app/tabs/module/ai-capabilities': 'AI 能力库',
  '/app/tabs/manage/peers': '同行店铺',
  '/app/tabs/manage/licenses': '执照档案',
  '/app/tabs/manage/account-usage': '账号使用记录',
  '/app/tabs/manage/devices': '手机设备',
}

test.beforeEach(async ({ page }) => {
  await page.route('**/auth/me', route => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ id: 'e2e', username: 'e2e', display_name: 'E2E', role: 'superadmin', permissions: {} }),
  }))
})

for (const path of routes) {
  test(`${path} loads without horizontal overflow`, async ({ page }) => {
    await page.goto(path)
    await expect(page.locator('.ion-page:not(.ion-page-hidden)').first()).toBeVisible()
    await expect(page.getByText(titles[path], { exact: true }).first()).toBeVisible()
    await expect(page).not.toHaveURL(/\/login/)
    const dimensions = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }))
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.width + 1)
  })
}

test('public AI share opens without login', async ({ page }) => {
  await page.route('**/ai-api/shares?id=*', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ share: { title: '测试分享', messages: [] } }) }))
  await page.goto('/app/ai-workspace/shared/test-share')
  await expect(page.getByText('测试分享')).toBeVisible()
  await expect(page).not.toHaveURL(/\/login/)
})
