import { Link } from 'react-router';
import { DASHBOARD } from '../api/operations.js';
import { EmptyState, ErrorAlert, LoadingState } from '../components/Feedback.jsx';
import ProductTable from '../components/ProductTable.jsx';
import useQuery from '../hooks/useQuery.js';
import { units } from '../utils/format.js';

export default function DashboardPage() {
  const { data, loading, error, refetch } = useQuery(DASHBOARD);
  return <>
    <div className="page-heading"><div><div className="eyebrow">YOUR SHOP, AT A GLANCE</div><h1>Inventory overview</h1><p>Know what’s on the shelf and what needs attention.</p></div><Link className="btn btn-primary" to="/products/new">+ Add product</Link></div>
    <ErrorAlert error={error} onRetry={refetch} />
    {loading && <LoadingState />}
    {data && <>
      <div className="row g-3 mb-4">
        <div className="col-sm-6 col-lg-4"><div className="summary-card"><span className="summary-icon" aria-hidden="true">▦</span><div className="summary-label">Active products</div><div className="summary-number">{units(data.dashboard.productCount)}</div><Link to="/products">Browse inventory <span aria-hidden="true">→</span></Link></div></div>
        <div className="col-sm-6 col-lg-4"><div className="summary-card"><span className="summary-icon" aria-hidden="true">▤</span><div className="summary-label">Total units on hand</div><div className="summary-number">{units(data.dashboard.totalUnits)}</div><span className="small text-secondary">Across all active products</span></div></div>
        <div className="col-sm-12 col-lg-4"><div className="summary-card summary-warning"><span className="summary-icon" aria-hidden="true">!</span><div className="summary-label">Products running low</div><div className="summary-number">{units(data.dashboard.lowStockCount)}</div><Link to="/products?low=1">Review low stock <span aria-hidden="true">→</span></Link></div></div>
      </div>
      <section className="panel"><div className="panel-heading"><div><h2>Needs attention</h2><p>Products at or below their low-stock threshold.</p></div><Link to="/products?low=1" className="text-link">View all →</Link></div>
        {data.products.items.length ? <ProductTable products={data.products.items} compact /> : <EmptyState title={data.dashboard.productCount ? 'Stock levels look healthy' : 'Welcome to your stockroom'}>{data.dashboard.productCount ? 'No active products are running low.' : <Link to="/products/new">Add your first product to get started.</Link>}</EmptyState>}
      </section>
      <div className="tip-box"><strong>A clear trail, every time.</strong> Every opening balance, receipt, issue, and adjustment is recorded. <Link to="/history">View movement history →</Link></div>
    </>}
  </>;
}
