import { useState } from 'react';
import { Link, useLocation, useParams } from 'react-router';
import { graphqlRequest, mutationValue } from '../api/client.js';
import { ARCHIVE_PRODUCT, PRODUCT_DETAIL } from '../api/operations.js';
import { EmptyState, ErrorAlert, LoadingState, Pagination, StockBadge } from '../components/Feedback.jsx';
import MovementTable from '../components/MovementTable.jsx';
import StockMovementForm from '../components/StockMovementForm.jsx';
import useAction from '../hooks/useAction.js';
import useQuery from '../hooks/useQuery.js';
import { money, timestamp, units } from '../utils/format.js';

const LIMIT = 10;

export default function ProductDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const [offset, setOffset] = useState(0);
  const [notice, setNotice] = useState(location.state?.notice || '');
  const [confirmArchive, setConfirmArchive] = useState(false);
  const { data, loading, error, refetch } = useQuery(PRODUCT_DETAIL, { id, limit: LIMIT, offset });
  const archiveAction = useAction();
  function changed(message) { setNotice(message); setOffset(0); refetch(); }
  async function archive() {
    const result = await archiveAction.run(async () => mutationValue(await graphqlRequest(ARCHIVE_PRODUCT, { id }), 'archiveProduct'));
    if (result) { setConfirmArchive(false); changed('Product archived. All stock movements have been preserved.'); }
  }
  const product = data?.product;
  return <>
    <Link className="back-link" to="/products">← Back to products</Link>
    <ErrorAlert error={error} onRetry={refetch} />
    {notice && <div className="alert alert-success d-flex justify-content-between align-items-center" role="status"><span>{notice}</span><button className="btn-close ms-3" aria-label="Dismiss notification" onClick={() => setNotice('')} /></div>}
    {loading && <LoadingState />}
    {data && !product && <EmptyState title="Product not found">This product does not exist. <Link to="/products">View inventory</Link></EmptyState>}
    {product && <>
      <div className="page-heading"><div><div className="eyebrow">{product.sku}</div><h1>{product.name}</h1><p>{product.category} <span className="mx-2" aria-hidden="true">·</span> <StockBadge product={product} /></p></div>{!product.archivedAt && <Link className="btn btn-outline-secondary" to={`/products/${id}/edit`}>Edit product</Link>}</div>
      <div className="row g-4"><div className={product.archivedAt ? 'col-12' : 'col-xl-8'}>
        <section className="panel product-summary"><div><span className="summary-label">Units on hand</span><div className="summary-number">{units(product.currentStock)}</div></div><div><span className="summary-label">Unit price</span><div className="h4 tabular mt-2">{money(product.unitPriceMinor)}</div></div><div><span className="summary-label">Low-stock threshold</span><div className="h4 tabular mt-2">{units(product.lowStockThreshold)}</div></div></section>
        {product.archivedAt && <div className="alert alert-secondary mt-3">Archived {timestamp(product.archivedAt)}. Product details and movement history are preserved; further changes are disabled.</div>}
        <section className="panel mt-4"><div className="panel-heading"><div><h2>Movement history</h2><p>Every quantity change, newest first. Times shown locally.</p></div></div><MovementTable movements={data.stockMovements.items} showProduct={false} /><Pagination total={data.stockMovements.totalCount} offset={offset} limit={LIMIT} onChange={setOffset} /></section>
      </div>
        {!product.archivedAt && <aside className="col-xl-4"><section className="panel p-4"><StockMovementForm product={product} onSuccess={changed} /></section>
          <section className="archive-panel mt-4" aria-labelledby="archive-heading"><h2 id="archive-heading" className="h6">Archive product</h2><p className="small text-secondary">Remove it from active inventory without losing its history. Stock must be zero first.</p><ErrorAlert error={archiveAction.error} />
            {confirmArchive ? <div><p className="small fw-semibold">Archive {product.name}? This product will become read-only.</p><div className="d-flex gap-2"><button className="btn btn-sm btn-outline-danger" onClick={archive} disabled={archiveAction.pending}>{archiveAction.pending ? 'Archiving…' : 'Confirm archive'}</button><button className="btn btn-sm btn-light" onClick={() => setConfirmArchive(false)} disabled={archiveAction.pending}>Cancel</button></div></div> : <button className="btn btn-sm btn-outline-secondary" disabled={product.currentStock !== 0} onClick={() => setConfirmArchive(true)}>Archive product</button>}
          </section>
        </aside>}
      </div>
    </>}
  </>;
}
