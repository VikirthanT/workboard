import { expect, test, type Page } from '@playwright/test';

// Runs against the demo world (seed/demo_db.py) in a throwaway database, with the dev account list standing in
// for Google. See playwright.config.ts and `make e2e`.

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await page.getByRole('button', { name: new RegExp(email.replace('.', '\\.')) }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

test('admin creates a team and finds the change in the audit log', async ({ page }) => {
  await signIn(page, 'admin@atimotors.com');

  await page.getByRole('button', { name: /Admin/ }).first().click(); // the avatar menu
  await page.getByRole('menuitem', { name: 'Teams' }).click();
  await expect(page.getByRole('heading', { name: 'Teams' })).toBeVisible();

  await page.getByRole('button', { name: 'Create team' }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Create a team' });
  await dialog.getByLabel('Team name').fill('E2E Team');
  await dialog.getByRole('combobox', { name: /Manager/ }).click();
  await page.getByRole('option', { name: /admin@atimotors\.com/ }).click(); // the only person on no team
  await dialog.getByLabel(/Reason/).fill('End-to-end smoke test');
  await dialog.getByRole('button', { name: 'Create team' }).click();

  await expect(page.getByRole('region', { name: 'E2E Team' })).toBeVisible();

  await page.getByRole('tab', { name: 'Audit log' }).click();
  await expect(page.getByText('Created E2E Team with Admin as manager')).toBeVisible();
  await expect(page.getByText('End-to-end smoke test')).toBeVisible();
});

test('manager adds a task with a due date and drags it to In Progress', async ({ page }) => {
  await signIn(page, 'manager1@atimotors.com');
  const title = `E2E smoke task ${Date.now()}`;

  await page.getByRole('button', { name: 'Add task' }).click();
  const form = page.getByRole('dialog', { name: 'Add task' });
  const add = form.getByRole('button', { name: 'Add task' });
  await expect(add).toBeDisabled(); // nothing filled in yet
  await form.getByLabel('Title').fill(title);
  await expect(add).toBeEnabled();

  const tomorrow = new Date(Date.now() + 86_400_000);
  await form.getByLabel('Due date').click(); // the picker's button is named by its label, not its placeholder
  await page.getByRole('gridcell', { name: tomorrow.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) }).click();
  await add.click();

  const card = page.getByRole('region', { name: 'To Do' }).getByRole('button', { name: new RegExp(title) });
  await expect(card).toBeVisible();

  // dnd-kit starts a drag after 6px of pointer movement, so move in steps rather than jumping.
  const from = (await card.boundingBox())!;
  const to = (await page.getByRole('region', { name: 'In Progress' }).boundingBox())!;
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + from.width / 2 + 12, from.y + from.height / 2 + 12, { steps: 4 });
  await page.mouse.move(to.x + to.width / 2, to.y + 140, { steps: 20 });
  await page.mouse.up();

  const moved = page.getByRole('region', { name: 'In Progress' }).getByRole('button', { name: new RegExp(title) });
  await expect(moved).toBeVisible();
  await page.reload();
  await expect(page.getByRole('region', { name: 'In Progress' }).getByRole('button', { name: new RegExp(title) })).toBeVisible(); // saved on the server
});
