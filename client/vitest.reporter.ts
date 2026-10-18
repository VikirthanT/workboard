/* One line per test: its name, PASSED / FAILED / SKIPPED, and how far through the run it is, in the same shape as
   `pytest -v`. Used by `make test` (scripts/test_all.py), which sets two environment variables:
     WB_TEST_TOTAL    how many tests there are (from `vitest list`), so the percentage means something;
     WB_TEST_SUMMARY  a file to write the counts to, for the combined summary.
   Without them the lines still print, with no percentage and no summary file. */
import { writeFileSync } from 'node:fs';
import { relative } from 'node:path';
import type { Reporter, TestCase, TestModule } from 'vitest/node';

const COLOR = process.stdout.isTTY ? { PASSED: '\x1b[32m', FAILED: '\x1b[31m', SKIPPED: '\x1b[33m', reset: '\x1b[0m' } : null;

export default class ProgressReporter implements Reporter {
  private done = 0;
  private readonly total = Number(process.env.WB_TEST_TOTAL ?? 0);
  private readonly counts = { passed: 0, failed: 0, skipped: 0 };
  private readonly failures: { name: string; message: string }[] = [];

  onTestCaseResult(test: TestCase) {
    const result = test.result();
    const state = result.state === 'passed' ? 'PASSED' : result.state === 'failed' ? 'FAILED' : 'SKIPPED';
    this.done += 1;
    this.counts[state === 'PASSED' ? 'passed' : state === 'FAILED' ? 'failed' : 'skipped'] += 1;

    const name = `${relative(process.cwd(), test.module.moduleId)}::${test.fullName}`;
    if (state === 'FAILED') this.failures.push({ name, message: result.errors?.[0]?.message ?? 'failed' });

    const percent = this.total ? `[${String(Math.min(100, Math.floor((this.done / this.total) * 100))).padStart(3)}%]` : '';
    const tag = COLOR ? `${COLOR[state]}${state}${COLOR.reset}` : state;
    console.log(`${name} ${tag} ${percent}`.trimEnd());
  }

  onTestRunEnd(modules: ReadonlyArray<TestModule>, unhandledErrors: ReadonlyArray<unknown>) {
    // A file that failed to load never reports a test; count it so the run cannot look clean.
    const broken = modules.filter((m) => m.state() === 'failed' && [...m.children.allTests()].length === 0).length;
    const errors = unhandledErrors.length + broken;

    for (const f of this.failures) console.log(`\nFAILED ${f.name}\n  ${f.message.split('\n').join('\n  ')}`);

    const file = process.env.WB_TEST_SUMMARY;
    if (file) writeFileSync(file, JSON.stringify({ ...this.counts, errors, failures: this.failures.map((f) => f.name) }));
  }
}
