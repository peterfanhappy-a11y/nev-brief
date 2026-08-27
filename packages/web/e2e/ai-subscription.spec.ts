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
  await page.waitForFunction(() => {
    const token = document.querySelector<HTMLInputElement>(
      'input[name="cf-turnstile-response"]',
    );
    return Boolean(token?.value);
  });
  await page.getByRole("button", { name: "免费订阅" }).click();
  await expect(page.getByRole("heading", { name: "请查收确认邮件" })).toBeVisible();

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

  await page.goto(messageLink(welcome!));
  await expect(page.getByRole("heading", { name: "确认退订" })).toBeVisible();
  await page.getByRole("button", { name: "确认退订" }).click();
  await expect(
    page.getByRole("heading", { name: "已退订 AIVIZENS · AI 趋势" }),
  ).toBeVisible();
});
