import { expect, test } from '@playwright/test';

test.describe('demo replay — operator flow', () => {
  test('dashboard → Guwahati → run agents → drafted alert → admin approve → sent', async ({ page }) => {
    await page.goto('./#/');
    await expect(page.getByTestId('demo-pill').first()).toBeVisible();

    // Pick Guwahati from the searchable city selector.
    const select = page.getByTestId('city-select');
    await expect(select.getByRole('option', { name: 'Guwahati' })).toHaveCount(1);
    await select.selectOption({ label: 'Guwahati' });

    await expect(page.getByTestId('city-name')).toHaveText('Guwahati');
    await expect(page.getByTestId('risk-score')).toHaveText(/^\d{1,3}\.\d$/);
    await expect(page.getByTestId('risk-level')).toHaveText(/^(green|yellow|orange|red) · /i);

    // Run the response agents: steps stream in on the Agents page.
    await page.getByTestId('run-agents').click();
    await expect(page).toHaveURL(/#\/agents\?run=/);
    await expect(page.getByTestId('lane-monitor').getByTestId('agent-step').first()).toBeVisible();
    await expect(page.getByTestId('lane-alert_drafter').getByTestId('agent-step').first()).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId('llm-badge')).toBeVisible();
    const drafted = page.getByTestId('drafted-alert');
    await expect(drafted).toBeVisible({ timeout: 60_000 });
    const alertId = await drafted.getAttribute('data-alert-id');
    expect(alertId).toBeTruthy();

    // Review in Admin.
    await page.getByTestId('review-alert').click();
    await expect(page).toHaveURL(/#\/admin\?alert=/);
    await expect(page.getByTestId('alert-editor')).toHaveAttribute('data-alert-id', alertId!);
    await expect(page.getByTestId('alert-status')).toHaveAttribute('data-status', 'pending_approval');

    // Reviewer name is required.
    await expect(page.getByTestId('reviewer-name')).toHaveValue('');
    await page.getByTestId('approve-alert').click();
    await expect(page.getByTestId('reviewer-error')).toBeVisible();
    await expect(page.getByTestId('alert-status')).toHaveAttribute('data-status', 'pending_approval');

    await page.getByTestId('reviewer-name').fill('Duty Officer R. Baruah');
    await page.getByTestId('approve-alert').click();
    await expect(page.getByTestId('alert-status')).toHaveText(/sent/i);
    await expect(page.getByTestId('dispatch-log')).toBeVisible();
    await expect(page.getByTestId('dispatch-log').locator('tbody tr')).toHaveCount(10);

    // State survives a reload (localStorage-backed demo state).
    await page.reload();
    await expect(page.getByTestId('alert-status')).toHaveText(/sent/i);
  });

  test('ward drill-down shows factor breakdown and nearest shelters', async ({ page }) => {
    await page.goto('./#/?city=guwahati');
    await expect(page.getByTestId('city-name')).toHaveText('Guwahati');
    await page.getByTestId('ward-row').first().click();
    const panel = page.getByTestId('ward-panel');
    await expect(panel).toBeVisible();
    await expect(panel.getByRole('meter')).toHaveCount(4);
    await expect(panel.getByText('Nearest shelters & facilities')).toBeVisible();
  });

  test('admin SMS editor counts characters and segments', async ({ page }) => {
    await page.goto('./#/?city=guwahati');
    await page.getByTestId('run-agents').click();
    await expect(page.getByTestId('drafted-alert')).toBeVisible({ timeout: 60_000 });
    await page.getByTestId('review-alert').click();
    const sms = page.getByTestId('sms-text');
    await sms.fill('Flood alert. Call 112.');
    await expect(page.getByTestId('sms-counter')).toHaveText(/^22\/160 · 1 segment · GSM-7/);
    await sms.fill(`Call 112 ${'x'.repeat(160)}`);
    await expect(page.getByTestId('sms-counter')).toContainText('over limit');
  });

  test('citizen view is light: no map/chart/pdf chunks, emergency numbers are tel: links', async ({ page }) => {
    const scripts: string[] = [];
    page.on('request', (r) => {
      if (r.resourceType() === 'script') scripts.push(r.url());
    });
    await page.goto('./#/citizen');
    await expect(page.getByRole('heading', { name: 'Flood risk near you' })).toBeVisible();
    await expect(page.getByTestId('emergency-numbers').getByRole('link', { name: /112/ })).toHaveAttribute('href', 'tel:112');
    await expect(page.getByTestId('emergency-numbers').getByRole('link', { name: /1078/ })).toHaveAttribute('href', 'tel:1078');
    expect(scripts.filter((u) => /leaflet|recharts|charts-|CommandMap|sitrepPdf|jspdf/i.test(u))).toEqual([]);

    await page.getByTestId('citizen-place').fill('Anil Nagar');
    await page.getByTestId('citizen-check').click();
    const choice = page.getByRole('button', { name: /Anil Nagar/ }).filter({ hasNotText: 'Try' });
    if (await page.getByText('Which place did you mean?').isVisible().catch(() => false)) await choice.first().click();
    await expect(page.getByTestId('citizen-risk-card')).toBeVisible();
    await expect(page.getByTestId('directions-link')).toHaveAttribute('href', /openstreetmap\.org\/directions/);

    await page.getByRole('button', { name: 'हिं' }).click();
    await expect(page.getByRole('heading', { name: 'आपके पास बाढ़ का खतरा' })).toBeVisible();
  });
});
