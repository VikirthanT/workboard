import { expect, test, type Page } from '@playwright/test';

// The whole working process in a real browser, on the demo world plus the suggestions e2e_seed.py adds (see make e2e).
// The throwaway server has no standup database, no language model and no Slack (its tokens are blanked in
// playwright.config.ts), so a sync is not run here; what the page does with suggestions, and what it says when Slack is
// not set up, is.

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await page.getByRole('button', { name: new RegExp(email.replace('.', '\\.')) }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

/** The day button of the date picker, named the way the calendar names it. */
const dayName = (daysFromToday: number) =>
  new Date(Date.now() + daysFromToday * 86_400_000).toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

const CAN_BUS = 'Fix flaky CAN-bus parser tests';
const ONBOARDING = 'Write onboarding notes for the diagnostics service';

test.describe('the board', () => {
  test('a task is found by part of its title or by its number, and the search clears', async ({ page }) => {
    await signIn(page, 'manager1@atimotors.com');
    const search = page.getByLabel('Search tasks');

    await search.fill('can-bus');
    const card = page.getByRole('button', { name: new RegExp(CAN_BUS) });
    await expect(card).toBeVisible();
    await expect(page.getByRole('button', { name: new RegExp(ONBOARDING) })).toHaveCount(0);

    const number = /^Task (\d+),/.exec((await card.getAttribute('aria-label')) ?? '')![1];
    await expect(card).toContainText(`#${number}`); // the number is on the card

    await page.getByRole('button', { name: 'Clear search' }).click();
    await expect(page.getByRole('button', { name: new RegExp(ONBOARDING) })).toBeVisible();

    await search.fill(`#${number}`);
    await expect(card).toBeVisible();
    await expect(page.getByRole('button', { name: new RegExp(ONBOARDING) })).toHaveCount(0);

    await search.fill('99999');
    await expect(card).toHaveCount(0);
  });

  test('"Needs attention" and "Needs review" are in the Filters menu and nowhere else', async ({ page }) => {
    await signIn(page, 'manager1@atimotors.com');

    await expect(page.getByRole('link', { name: 'Needs review' })).toHaveCount(0); // the old header link
    await expect(page.getByRole('checkbox', { name: /Needs attention/ })).toHaveCount(0); // the old tick beside the search box

    await page.getByRole('button', { name: 'Filters' }).click();
    const options = page.getByRole('menuitemcheckbox');
    await expect(options.first()).toContainText('Needs attention'); // first, with its count
    await expect(options.filter({ hasText: 'Needs my review' })).toHaveCount(1);

    await options.first().click();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('button', { name: 'Remove filter Needs attention' })).toBeVisible();
    await expect(page.getByRole('button', { name: new RegExp(CAN_BUS) })).toBeVisible(); // blocked and overdue: needs attention
    await expect(page.getByRole('button', { name: new RegExp(ONBOARDING) })).toHaveCount(0); // quiet and not due: does not

    await page.getByRole('button', { name: 'Remove filter Needs attention' }).click();
    await expect(page.getByRole('button', { name: new RegExp(ONBOARDING) })).toBeVisible();
  });
});

test.describe('suggestions', () => {
  test('a manager adds suggestions, and the one with no due date needs one first', async ({ page }) => {
    await signIn(page, 'manager1@atimotors.com');
    await page.getByRole('link', { name: /Suggestions/ }).click();
    await expect(page.getByRole('heading', { name: 'Suggestions' })).toBeVisible();
    await expect(page.getByText('Not synced yet').first()).toBeVisible(); // nothing has been read from the standup yet

    const people = page.getByRole('navigation', { name: 'Team members' });
    await people.getByRole('button', { name: /Aarav/ }).click();
    await page.getByRole('button', { name: 'Select', exact: true }).click(); // exact: the people list has buttons that say "selected"
    await people.getByRole('button', { name: /Meera/ }).click();
    await page.getByRole('button', { name: 'Select', exact: true }).click();
    await page.getByRole('button', { name: 'Add (2)' }).click();

    const dialog = page.getByRole('dialog', { name: 'Add 2 tasks' });
    const create = dialog.getByRole('button', { name: 'Create (2)' });
    await expect(create).toBeDisabled(); // a task needs a due date
    await expect(dialog.getByText(/1 still needs a due date/)).toBeVisible();
    await expect(dialog.getByText('Choose a due date.')).toBeVisible();

    const undated = dialog.locator('li', { hasText: 'E2E suggestion without a date' });
    await undated.getByLabel(/Due date/).click();
    await page.getByRole('gridcell', { name: dayName(2) }).click();
    await expect(create).toBeEnabled();
    await create.click();
    await expect(page.getByText(/2 tasks added to the board/)).toBeVisible();

    await page.getByRole('link', { name: 'Work Board home' }).click();
    const todo = page.getByRole('region', { name: 'To Do' });
    await expect(todo.getByRole('button', { name: /E2E suggestion with a date/ })).toBeVisible();
    await expect(todo.getByRole('button', { name: /E2E suggestion without a date/ })).toBeVisible();
    await expect(todo.getByRole('button', { name: /E2E suggestion without a date/ })).toContainText('#'); // numbered like every task
  });

  test('an admin reads any team\'s suggestions and may sync, but adds and changes nothing', async ({ page }) => {
    await signIn(page, 'admin@atimotors.com');
    await page.getByRole('link', { name: /Suggestions/ }).click();

    await expect(page.getByText(/Read-only view of/)).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Team' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sync now' })).toBeEnabled();
    await expect(page.getByRole('button', { name: /^Add \(/ })).toHaveCount(0);
    for (const name of ['Select', 'Edit', 'Reject', 'Restore']) await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0);

    await page.getByRole('combobox', { name: 'Team' }).click();
    await page.getByRole('option', { name: /Validation/ }).click();
    await expect(page.getByText('Read-only view of Validation.')).toBeVisible();
  });
});

test.describe('teams and Slack', () => {
  test('Pull from Slack opens a review, and says so when Slack is not set up', async ({ page }) => {
    await signIn(page, 'admin@atimotors.com');
    await page.getByRole('button', { name: /Admin/ }).first().click();
    await page.getByRole('menuitem', { name: 'Teams' }).click();

    const npi = page.getByRole('region', { name: 'NPI' });
    await npi.getByRole('button', { name: /Pull from Slack/ }).click();

    const dialog = page.getByRole('dialog', { name: /Pull people from Slack into NPI/ });
    await expect(dialog.getByText('The channel could not be read')).toBeVisible();
    await expect(dialog.getByText(/Slack is not set up/)).toBeVisible();
    await expect(dialog.getByRole('button', { name: /^Add / })).toBeDisabled(); // nothing to add
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).toHaveCount(0);
  });

  test('a manager has the button on their own team page', async ({ page }) => {
    await signIn(page, 'manager1@atimotors.com');
    await page.getByRole('button', { name: /Manager 1/ }).first().click();
    await page.getByRole('menuitem', { name: 'My team' }).click();

    await expect(page.getByRole('heading', { name: 'NPI team' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Pull from Slack/ })).toBeEnabled(); // the demo team has a standup channel
  });
});
