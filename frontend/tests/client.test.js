import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { graphqlRequest, mutationValue, RequestError, ValidationError } from '../src/api/client.js';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('uses POST with GraphQL variables, not interpolated user input', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/graphql');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(options.body), { query: 'query Q($search: String!) { test }', variables: { search: '" malicious input' } });
    return new Response(JSON.stringify({ data: { test: true } }));
  };
  assert.deepEqual(await graphqlRequest('query Q($search: String!) { test }', { search: '" malicious input' }), { test: true });
});

test('handles network failures', async () => {
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(graphqlRequest('query'), RequestError);
});

test('preserves request cancellation', async () => {
  globalThis.fetch = async () => { throw new DOMException('Aborted', 'AbortError'); };
  await assert.rejects(graphqlRequest('query'), { name: 'AbortError' });
});

test('rejects GraphQL errors even when HTTP status is 200', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ errors: [{ message: 'Invalid query' }] }));
  await assert.rejects(graphqlRequest('query'), /Invalid query/);
});

test('handles HTTP and non-JSON failures', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: 'Forbidden' }), { status: 403 });
  await assert.rejects(graphqlRequest('query'), /Forbidden/);
  globalThis.fetch = async () => new Response('<html>Bad gateway</html>', { status: 502 });
  await assert.rejects(graphqlRequest('query'), /unreadable/);
});

test('preserves field validation errors from mutation payloads', () => {
  assert.throws(() => mutationValue({ createProduct: { errors: [{ code: 'DUPLICATE_SKU', field: 'sku', message: 'Already used' }] } }, 'createProduct'), ValidationError);
  assert.equal(mutationValue({ issueStock: { product: { currentStock: 1 }, errors: [] } }, 'issueStock').product.currentStock, 1);
});

for (const invalid of [null, [], { errors: 'not an array' }, { errors: [null] }, { data: [] }, { data: 'invalid' }]) {
  test(`rejects malformed GraphQL envelope ${JSON.stringify(invalid)} with a useful error`, async () => {
    globalThis.fetch = async () => new Response(JSON.stringify(invalid));
    await assert.rejects(graphqlRequest('query'), (error) => error instanceof RequestError && /invalid GraphQL response/i.test(error.message));
  });
}

test('rejects incomplete mutation success rather than causing a render failure', () => {
  assert.throws(() => mutationValue({ createProduct: { errors: [], product: null } }, 'createProduct'), RequestError);
});

test('preserves cancellation while reading the response body', async () => {
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => { throw new DOMException('Aborted', 'AbortError'); } });
  await assert.rejects(graphqlRequest('query'), { name: 'AbortError' });
});
