import test from 'node:test';
import assert from 'node:assert/strict';
import { parseInteger, parsePrice, priceInput, units } from '../src/utils/format.js';

test('prices convert to minor units without floating point rounding', () => {
  assert.equal(parsePrice('0.29'), 29);
  assert.equal(parsePrice('1.01'), 101);
  assert.equal(parsePrice('12.5'), 1250);
  assert.equal(parsePrice('0'), 0);
  assert.equal(parsePrice('21474836.47'), 2147483647);
  assert.equal(priceInput(29), '0.29');
  assert.equal(priceInput(101), '1.01');
});

for (const invalid of ['-1', '1.001', '1e2', '', '.', 'NaN', '21474836.48', '9999999999999999999999', '1,000.00']) {
  test(`reject invalid price ${JSON.stringify(invalid)}`, () => assert.throws(() => parsePrice(invalid)));
}

test('quantities must be bounded whole numbers', () => {
  assert.equal(parseInteger('0', 'quantity'), 0);
  assert.equal(parseInteger('2147483647', 'quantity'), 2147483647);
  for (const invalid of ['', '1.2', '-1', '1e2', '2147483648']) assert.throws(() => parseInteger(invalid, 'quantity'));
  assert.throws(() => parseInteger('0', 'quantity', 1));
});

test('aggregate quantities retain precision', () => {
  assert.equal(units('4294967294').replace(/\D/g, ''), '4294967294');
});
