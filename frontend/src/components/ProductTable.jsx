import { Link } from 'react-router';
import { money, units } from '../utils/format.js';
import { EmptyState, StockBadge } from './Feedback.jsx';

export default function ProductTable({ products, compact = false }) {
  if (!products.length) return <EmptyState title="No products found">Add your first product or try different filters.</EmptyState>;
  return <div className="table-responsive" tabIndex={0} role="region" aria-label="Inventory products; scroll horizontally for more columns"><table className="table align-middle mb-0">
    <caption className="visually-hidden">Inventory products and current stock</caption>
    <thead><tr><th scope="col">Product</th><th scope="col">Category</th>{!compact && <th scope="col" className="text-end">Unit price</th>}<th scope="col" className="text-end">On hand</th><th scope="col">Status</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
    <tbody>{products.map((product) => <tr key={product.id}>
      <td><Link className="product-name" to={`/products/${product.id}`}>{product.name}</Link><div className="sku">{product.sku}</div></td>
      <td>{product.category}</td>
      {!compact && <td className="text-end tabular">{money(product.unitPriceMinor)}</td>}
      <td className="text-end tabular fw-semibold">{units(product.currentStock)}<div className="small fw-normal text-secondary">Min. {units(product.lowStockThreshold)}</div></td>
      <td><StockBadge product={product} /></td>
      <td className="text-end"><Link className="btn btn-sm btn-light" to={`/products/${product.id}`} aria-label={`View ${product.name}`}>View <span aria-hidden="true">↗</span></Link></td>
    </tr>)}</tbody>
  </table></div>;
}
