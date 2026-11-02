import { useState } from 'react';
import { Link } from 'react-router';
import { fieldError } from '../api/client.js';
import useAction from '../hooks/useAction.js';
import { parseInteger, parsePrice, priceInput } from '../utils/format.js';
import { ErrorAlert, Field } from './Feedback.jsx';

export default function ProductForm({ product, categories, onSave }) {
  const [values, setValues] = useState({
    sku: product?.sku || '', name: product?.name || '', category: product?.category || '',
    price: product ? priceInput(product.unitPriceMinor) : '',
    threshold: String(product?.lowStockThreshold ?? 5), opening: '0',
  });
  const { run, pending, error } = useAction();
  const change = (event) => setValues({ ...values, [event.target.name]: event.target.value });
  async function submit(event) {
    event.preventDefault();
    await run(async () => {
      const input = {
        name: values.name.trim(), category: values.category.trim(),
        unitPriceMinor: parsePrice(values.price),
        lowStockThreshold: parseInteger(values.threshold, 'lowStockThreshold'),
      };
      if (product) input.id = product.id;
      else { input.sku = values.sku.trim(); input.openingQuantity = parseInteger(values.opening, 'openingQuantity'); }
      return onSave(input);
    });
  }
  return <form onSubmit={submit} aria-busy={pending}>
    <ErrorAlert error={error} />
    <fieldset disabled={pending}>
      <legend className="h5 mb-4">Product information</legend>
      <div className="row"><div className="col-md-5"><Field label="SKU" name="sku" value={values.sku} onChange={change} required maxLength={64} readOnly={Boolean(product)} autoComplete="off" error={fieldError(error, 'sku')} help={product ? 'SKUs cannot be changed or reused.' : 'A unique product code. Letters are saved in uppercase.'} /></div>
        <div className="col-md-7"><Field label="Product name" name="name" value={values.name} onChange={change} required maxLength={160} autoComplete="off" error={fieldError(error, 'name')} /></div></div>
      <Field label="Category" name="category" value={values.category} onChange={change} list="category-suggestions" required maxLength={80} error={fieldError(error, 'category')} help="Choose an existing category or enter a new one." />
      <datalist id="category-suggestions">{categories.map((category) => <option key={category} value={category} />)}</datalist>
      <div className="row"><div className="col-md-6"><Field label="Unit price" name="price" type="text" inputMode="decimal" value={values.price} onChange={change} placeholder="0.00" required error={fieldError(error, 'unitPriceMinor')} help="Your shop’s currency, with up to two decimal places." /></div>
        <div className="col-md-6"><Field label="Low-stock threshold" name="threshold" type="number" min="0" max="2147483647" step="1" value={values.threshold} onChange={change} required error={fieldError(error, 'lowStockThreshold')} help="An alert appears when stock reaches or falls below this number." /></div></div>
      {!product && <div className="opening-stock"><h2 className="h6">Start with an accurate count</h2><Field label="Opening stock" name="opening" type="number" min="0" max="2147483647" step="1" value={values.opening} onChange={change} required error={fieldError(error, 'openingQuantity')} help="Saved as the first movement. Use 0 if you have no stock yet." /></div>}
      <div className="d-flex gap-2 mt-4"><button className="btn btn-primary" type="submit">{pending ? 'Saving…' : product ? 'Save changes' : 'Create product'}</button><Link className="btn btn-outline-secondary" to={product ? `/products/${product.id}` : '/products'}>Cancel</Link></div>
    </fieldset>
  </form>;
}
