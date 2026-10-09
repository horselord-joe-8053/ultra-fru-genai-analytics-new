/**
 * Descriptor-based login for Playwright specs (app-agnostic; copy with HOWTO).
 */
import { type Locator, type Page } from "@playwright/test";

export type LoginPageDescriptor = {
  loginPath: string;
  email: string | Locator;
  password: string | Locator;
  submit: string | Locator;
  expectAfterLogin?: (page: Page) => Promise<void>;
};

function asLocator(page: Page, target: string | Locator): Locator {
  return typeof target === "string" ? page.locator(target) : target;
}

/** Fill credentials and submit; optional post-login assertion hook. */
export async function signIn(page: Page, descriptor: LoginPageDescriptor): Promise<void> {
  await page.goto(descriptor.loginPath);
  if (typeof descriptor.email === "string") {
    await asLocator(page, descriptor.email).fill(descriptor.email);
  }
  if (typeof descriptor.password === "string") {
    await asLocator(page, descriptor.password).fill(descriptor.password);
  }
  await asLocator(page, descriptor.submit).click();
  if (descriptor.expectAfterLogin) {
    await descriptor.expectAfterLogin(page);
  }
}
