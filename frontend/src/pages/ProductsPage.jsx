import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { graphqlRequest } from '../api/client.js';
import { EXPORT_CSV, PRODUCTS } from '../api/operations.js';
import { ErrorAlert, Field, LoadingState, Pagination } from '../components/Feedback.jsx';
import ProductTable from '../components/ProductTable.jsx';
import useAction from '../hooks/useAction.js';
import useQuery from '../hooks/useQuery.js';
import { downloadCsv } from '../utils/format.js';

const LIMIT = 20;

export default function ProductsPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const [search, setSearch] = useState(q);
  useEffect(() => setSearch(q), [q]);
  const archive = ['ACTIVE', 'ARCHIVED', 'ALL'].includes(params.get('archive')) ? params.get('archive') : 'ACTIVE';
  const page = Math.max(1, Math.min(1000000, Number.parseInt(params.get('page'), 10) || 1));
  const offset = (page - 1) * LIMIT;
  const filter = { search: q, category: params.get('category') || null, lowStockOnly: params.get('low') === '1', archiveStatus: archive };
  const { data, loading, error, refetch } = useQuery(PRODUCTS, { filter, archiveStatus: archive, limit: LIMIT, offset });
  useEffect(() => {
    if (data && !loading && offset > 0 && offset >= data.products.totalCount) {
      setParams((current) => { const next = new URLSearchParams(current); next.delete('page'); return next; }, { replace: true });
    }
  }, [data, loading, offset, setParams]);
  const exportAction = useAction();
  const [exported, setExported] = useState(false);
  function update(changes) {
    const next = new URLSearchParams(params);
    next.delete('page');
    for (const [key, value] of Object.entries(changes)) value ? next.set(key, value) : next.delete(key);
    setParams(next); setExported(false);
  }
  async function exportCsv() {
    const result = await exportAction.run(async () => {
      const result = await graphqlRequest(EXPORT_CSV, { filter });
      downloadCsv(result.inventoryCsv);
      return true;
    });
    if (result) setExported(true);
  }
  return <>
    <div className="page-heading"><div><div className="eyebrow">YOUR CATALOG</div><h1>Products</h1><p>Manage products, check stock, and keep your shelves ready.</p></div><div className="d-flex gap-2 flex-wrap"><button className="btn btn-outline-secondary" onClick={exportCsv} disabled={exportAction.pending || loading || !data?.products.totalCount}>{exportAction.pending ? 'Exporting…' : '↓ Export CSV'}</button><Link className="btn btn-primary" to="/products/new">+ Add product</Link></div></div>
    <ErrorAlert error={error} onRetry={refetch} /><ErrorAlert error={exportAction.error} />
    {exported && <div className="alert alert-success py-2" role="status">CSV downloaded with all products matching your current filters.</div>}
    <section className="panel">
      <div className="filter-bar"><form className="search-form" onSubmit={(event) => { event.preventDefault(); update({ q: search.trim() }); }}><label htmlFor="product-search" className="visually-hidden">Search products by SKU or name</label><input id="product-search" className="form-control" type="search" placeholder="Search by product name or SKU…" value={search} maxLength={160} onChange={(event) => setSearch(event.target.value)} /><button className="btn btn-outline-secondary" type="submit">Search</button></form>
        <div className="filter-controls"><Field label="Category" name="category" as="select" value={filter.category || ''} onChange={(event) => update({ category: event.target.value })}><option value="">All categories</option>{(data?.categories || (filter.category ? [filter.category] : [])).map((category) => <option key={category}>{category}</option>)}</Field>
          <Field label="Show" name="archive" as="select" value={archive} onChange={(event) => update({ archive: event.target.value, category: '' })}><option value="ACTIVE">Active products</option><option value="ARCHIVED">Archived products</option><option value="ALL">All products</option></Field>
          <div className="form-check low-filter"><input className="form-check-input" type="checkbox" id="low-only" checked={filter.lowStockOnly} onChange={(event) => update({ low: event.target.checked ? '1' : '' })} /><label className="form-check-label" htmlFor="low-only">Low stock only</label></div>
        </div>
      </div>
      {loading && <LoadingState />}
      {data && <><ProductTable products={data.products.items} /><Pagination total={data.products.totalCount} offset={offset} limit={LIMIT} onChange={(next) => { const paramsCopy = new URLSearchParams(params); paramsCopy.set('page', String(next / LIMIT + 1)); setParams(paramsCopy); }} /></>}
    </section>
    <p className="small text-secondary mt-3">Prices use your shop’s currency. Low stock includes products with zero units.</p>
  </>;
}
