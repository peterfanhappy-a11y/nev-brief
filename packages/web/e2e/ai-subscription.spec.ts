import { expect, test, type APIRequestContext } from "@playwright/test";

interface CapturedEmail {
  body: {
    to: string;
    subject: string;
    text: string;
  };
}

const fakeResendUrl = process.env.RESEND_BASE_URL ?? "http://127.0.0.1:55438";
const LINK = /https?:\/\/[^\s<]+\/(?:confirm|unsubscribe)\?[^\s<]+/;

async function capturedMessages(request: APIRequestContext) {
  const response = await request.get(`${fakeResendUrl}/_test/messages`);
  expect(response.status()).toBe(200);
  return (await response.json()) as CapturedEmail[];
}

function messageLink(message: CapturedEmail): string {
  const match = LINK.exec(message.body.text);
  expect(match).not.toBeNull();
  return match![0];
}

test("fresh reader confirms and explicitly unsubscribes through the browser", async ({
  page,
  request,
}) => {
  const email = `browser-${Date.now()}-${test.info().workerIndex}@example.com`;
  const clear = await request.delete(`${fakeResendUrl}/_test/messages`);
  expect(clear.status()).toBe(204);

  await page.goto("/");
  await page.getByPlaceholder("输入你的邮箱").fill(email);
  await page.getByRole("button", { name: "免费订阅" }).click();
  await expect(page.getByRole("dialog", { name: "人机验证" })).toBeVisible();
  const progressBar = page.getByRole("button", { name: "长按进度条 2 秒" });
  await progressBar.hover();
  await page.mouse.down();
  await page.waitForTimeout(2_100);
  await page.mouse.up();
  await expect(page.getByRole("heading", { name: "订阅请求已收到" })).toBeVisible();

  await expect
    .poll(async () => (await capturedMessages(request)).length)
    .toBeGreaterThanOrEqual(1);
  const confirmation = (await capturedMessages(request)).find(
    (message) => message.body.to === email && message.body.subject.includes("确认订阅"),
  );
  expect(confirmation).toBeDefined();

  await page.goto(messageLink(confirmation!));
  await expect(page.getByRole("heading", { name: "确认订阅" })).toBeVisible();
  await page.getByRole("button", { name: "确认订阅" }).click();
  await expect(page.getByRole("heading", { name: "订阅确认成功" })).toBeVisible();

  await expect
    .poll(async () => (await capturedMessages(request)).length)
    .toBeGreaterThanOrEqual(2);
  const welcome = (await capturedMessages(request)).find(
    (message) => message.body.to === email && message.body.subject.includes("欢迎加入"),
  );
  expect(welcome).toBeDefined();

  await page.goto("/unsubscribe");
  await page.getByLabel("订阅邮箱").fill(email);
  await page.getByRole("button", { name: "发送退订链接" }).click();
  await expect(page.getByRole("heading", { name: "请查收退订邮件" })).toBeVisible();

  await expect
    .poll(async () => (await capturedMessages(request)).length)
    .toBeGreaterThanOrEqual(3);
  const unsubscribe = (await capturedMessages(request)).find(
    (message) => message.body.to === email && message.body.subject.includes("确认退订"),
  );
  expect(unsubscribe).toBeDefined();

  await page.goto(messageLink(unsubscribe!));
  await expect(page.getByRole("heading", { name: "确认退订" })).toBeVisible();
  await page.getByRole("button", { name: "确认退订" }).click();
  await expect(
    page.getByRole("heading", { name: "已退订 AIVIZENS · AI 趋势" }),
  ).toBeVisible();
});

test.describe("touch verification", () => {
  test.use({ hasTouch: true, isMobile: true, viewport: { width: 820, height: 1180 } });

  test("prevents a context menu and submits after a two-second touch hold", async ({
    page,
    request,
  }) => {
    const email = `touch-${Date.now()}-${test.info().workerIndex}@example.com`;
    const clear = await request.delete(`${fakeResendUrl}/_test/messages`);
    expect(clear.status()).toBe(204);

    await page.goto("/");
    await page.getByPlaceholder("输入你的邮箱").fill(email);
    await page.getByRole("button", { name: "免费订阅" }).click();
    const progressBar = page.getByRole("button", { name: "长按进度条 2 秒" });

    const menuWasAllowed = await progressBar.evaluate((element) =>
      element.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true })),
    );
    expect(menuWasAllowed).toBe(false);

    await progressBar.dispatchEvent("pointerdown", {
      button: 0,
      pointerId: 7,
      pointerType: "touch",
    });
    await page.waitForTimeout(2_100);
    await progressBar.dispatchEvent("pointerup", {
      button: 0,
      pointerId: 7,
      pointerType: "touch",
    });

    await expect(page.getByRole("heading", { name: "订阅请求已收到" })).toBeVisible();
  });
});
