import { Link } from 'react-router';
import { timestamp, units } from '../utils/format.js';
import { EmptyState } from './Feedback.jsx';

export const movementLabels = { OPENING: 'Opening stock', RECEIVED: 'Received', ISSUED: 'Issued', ADJUSTMENT: 'Adjustment' };

export default function MovementTable({ movements, showProduct = true }) {
  if (!movements.length) return <EmptyState title="No movements found">Stock changes will appear here with their reason and timestamp.</EmptyState>;
  return <div className="table-responsive" tabIndex={0} role="region" aria-label="Stock movement history; scroll horizontally for more columns"><table className="table align-middle mb-0">
    <caption className="visually-hidden">Stock movement history, newest first</caption>
    <thead><tr><th scope="col">Date & time</th>{showProduct && <th scope="col">Product</th>}<th scope="col">Movement</th><th scope="col" className="text-end">Change</th><th scope="col">Reason</th></tr></thead>
    <tbody>{movements.map((movement) => <tr key={movement.id}>
      <td className="small text-nowrap"><time dateTime={movement.createdAt}>{timestamp(movement.createdAt)}</time></td>
      {showProduct && <td><Link className="product-name" to={`/products/${movement.productId}`}>{movement.productName}</Link><div className="sku">{movement.productSku}</div></td>}
      <td><span className="movement-label">{movementLabels[movement.movementType]}</span></td>
      <td className={`text-end tabular fw-bold ${movement.quantityChange < 0 ? 'text-danger' : 'text-success'}`}>{movement.quantityChange > 0 ? '+' : ''}{units(movement.quantityChange)}</td>
      <td className="reason-cell">{movement.reason}</td>
    </tr>)}</tbody>
  </table></div>;
}
