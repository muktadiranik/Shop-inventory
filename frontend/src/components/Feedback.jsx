import { useId } from 'react';

export function ErrorAlert({ error, onRetry }) {
  if (!error) return null;
  return <div className="alert alert-danger" role="alert">
    <strong>We couldn’t complete that.</strong> {error.message || String(error)}
    {onRetry && <button className="btn btn-sm btn-outline-danger ms-3" onClick={onRetry}>Try again</button>}
  </div>;
}

export function LoadingState({ text = 'Loading inventory…' }) {
  return <div className="loading-state" role="status"><span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />{text}</div>;
}

export function EmptyState({ title = 'Nothing here yet', children }) {
  return <div className="empty-state"><div className="empty-symbol" aria-hidden="true">□</div><h3 className="h5">{title}</h3>{children && <div className="text-secondary">{children}</div>}</div>;
}

export function Field({ label, name, error, help, as = 'input', children, className = '', ...props }) {
  const uniqueId = useId();
  const id = `${name}-${uniqueId}`;
  const describedBy = [help && `${id}-help`, error && `${id}-error`].filter(Boolean).join(' ') || undefined;
  const controlProps = { ...props, id, name, className: `${as === 'select' ? 'form-select' : 'form-control'} ${error ? 'is-invalid' : ''} ${className}`, 'aria-invalid': error ? true : undefined, 'aria-describedby': describedBy };
  return <div className="mb-3">
    <label className="form-label" htmlFor={id}>{label}</label>
    {as === 'select' ? <select {...controlProps}>{children}</select> : as === 'textarea' ? <textarea {...controlProps} /> : <input {...controlProps} />}
    {help && <div className="form-text" id={`${id}-help`}>{help}</div>}
    {error && <div className="invalid-feedback" id={`${id}-error`}>{error}</div>}
  </div>;
}

export function Pagination({ total, offset, limit, onChange }) {
  if (!total) return null;
  return <nav className="pagination-bar" aria-label="Pagination">
    <span className="text-secondary small" aria-live="polite">{Math.min(offset + 1, total)}–{Math.min(offset + limit, total)} of {total}</span>
    <div className="d-flex gap-2">
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</button>
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</button>
    </div>
  </nav>;
}

export function StockBadge({ product }) {
  if (product.archivedAt) return <span className="badge text-bg-secondary">Archived</span>;
  if (product.currentStock === 0) return <span className="stock-badge stock-out">Out of stock</span>;
  return product.isLowStock ? <span className="stock-badge stock-low">Low stock</span> : <span className="stock-badge stock-healthy">In stock</span>;
}
