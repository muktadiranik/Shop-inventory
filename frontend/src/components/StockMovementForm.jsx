import { useState } from 'react';
import { fieldError, graphqlRequest, mutationValue } from '../api/client.js';
import { ADJUST_STOCK, ISSUE_STOCK, RECEIVE_STOCK } from '../api/operations.js';
import useAction from '../hooks/useAction.js';
import { parseInteger } from '../utils/format.js';
import { ErrorAlert, Field } from './Feedback.jsx';

const operations = {
  RECEIVED: { query: RECEIVE_STOCK, name: 'receiveStock', label: 'Receive stock', reason: 'Stock received' },
  ISSUED: { query: ISSUE_STOCK, name: 'issueStock', label: 'Issue stock', reason: 'Stock issued' },
  ADJUSTMENT: { query: ADJUST_STOCK, name: 'adjustStock', label: 'Adjust stock', reason: '' },
};

export default function StockMovementForm({ product, onSuccess }) {
  const [kind, setKind] = useState('RECEIVED');
  const [quantity, setQuantity] = useState('');
  const [reason, setReason] = useState(operations.RECEIVED.reason);
  const { run, pending, error, clearError } = useAction();
  const adjustment = kind === 'ADJUSTMENT';
  const operation = operations[kind];
  function changeKind(event) {
    const value = event.target.value;
    setKind(value); setQuantity(''); setReason(operations[value].reason); clearError();
  }
  async function submit(event) {
    event.preventDefault();
    const result = await run(async () => {
      const input = { productId: product.id, reason: reason.trim() };
      input[adjustment ? 'countedQuantity' : 'quantity'] = parseInteger(quantity, adjustment ? 'countedQuantity' : 'quantity', adjustment ? 0 : 1);
      const data = await graphqlRequest(operation.query, { input });
      return mutationValue(data, operation.name);
    });
    if (result) { setQuantity(''); setReason(operation.reason); onSuccess(`${operation.label} saved. The stock balance and movement history have been updated.`); }
  }
  return <form onSubmit={submit} aria-busy={pending}>
    <ErrorAlert error={error} />
    <fieldset disabled={pending}>
      <legend className="h5">Record a stock movement</legend>
      <Field label="Movement type" name="movementType" as="select" value={kind} onChange={changeKind}>
        <option value="RECEIVED">Receive stock</option><option value="ISSUED">Issue stock</option><option value="ADJUSTMENT">Manual adjustment</option>
      </Field>
      <Field label={adjustment ? 'Counted quantity' : 'Quantity'} name="quantity" type="number" min={adjustment ? '0' : '1'} max="2147483647" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} required error={fieldError(error, adjustment ? 'countedQuantity' : 'quantity')} help={adjustment ? 'Enter the total units physically on hand, not the change. We calculate the difference.' : kind === 'ISSUED' ? `Currently available: ${product.currentStock} units. Negative stock is not allowed.` : 'Enter the number of units received.'} />
      <Field label="Reason" name="reason" as="textarea" rows={3} value={reason} onChange={(event) => setReason(event.target.value)} required maxLength={500} error={fieldError(error, 'reason')} placeholder={adjustment ? 'For example: physical count, damaged goods…' : ''} help="This explanation is kept permanently in the movement history." />
      <button className={`btn ${kind === 'ISSUED' ? 'btn-outline-danger' : 'btn-primary'} w-100`} type="submit">{pending ? 'Saving movement…' : operation.label}</button>
    </fieldset>
  </form>;
}
