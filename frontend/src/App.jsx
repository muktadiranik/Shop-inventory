import { Component, useEffect } from 'react';
import { Link, NavLink, Route, Routes, useLocation } from 'react-router';
import DashboardPage from './pages/DashboardPage.jsx';
import MovementHistoryPage from './pages/MovementHistoryPage.jsx';
import ProductDetailPage from './pages/ProductDetailPage.jsx';
import ProductFormPage from './pages/ProductFormPage.jsx';
import ProductsPage from './pages/ProductsPage.jsx';

class ErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <div className="alert alert-danger" role="alert"><h1 className="h4">Something went wrong</h1><p>Please reload the page. No stock changes are automatically retried.</p><button className="btn btn-outline-danger" onClick={() => window.location.reload()}>Reload page</button></div>;
    return this.props.children;
  }
}

export default function App() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = `${pathname === '/' ? 'Overview' : pathname.startsWith('/history') ? 'Movement history' : 'Products'} · Stockroom`;
    window.scrollTo(0, 0);
  }, [pathname]);
  return <div className="app-shell">
    <a href="#main-content" className="skip-link">Skip to main content</a>
    <aside className="sidebar"><Link to="/" className="brand"><span className="brand-mark" aria-hidden="true">▦</span><span>stockroom<span className="brand-caption">SMALL SHOP, SIMPLY ORGANIZED</span></span></Link>
      <div className="sidebar-label">WORKSPACE</div><nav aria-label="Main navigation"><NavLink to="/" end><span aria-hidden="true">◫</span> Overview</NavLink><NavLink to="/products"><span aria-hidden="true">▦</span> Products</NavLink><NavLink to="/history"><span aria-hidden="true">↔</span> Movement history</NavLink></nav>
      <div className="sidebar-footer"><span className="local-dot" aria-hidden="true" /> Local workspace<div>One shop. Everything in order.</div></div>
    </aside>
    <div className="workspace"><header className="topbar"><span>Shop inventory</span><span className="workspace-pill">Single-shop workspace</span></header><main id="main-content" className="main-content" tabIndex={-1}>
      <ErrorBoundary key={pathname}><Routes><Route path="/" element={<DashboardPage />} /><Route path="/products" element={<ProductsPage />} /><Route path="/products/new" element={<ProductFormPage />} /><Route path="/products/:id/edit" element={<ProductFormPage />} /><Route path="/products/:id" element={<ProductDetailPage key={pathname} />} /><Route path="/history" element={<MovementHistoryPage />} /><Route path="*" element={<div className="empty-state"><h1>Page not found</h1><Link to="/">Back to overview</Link></div>} /></Routes></ErrorBoundary>
    </main><footer className="workspace-footer">Stockroom <span aria-hidden="true">·</span> Simple inventory for your everyday business</footer></div>
  </div>;
}
