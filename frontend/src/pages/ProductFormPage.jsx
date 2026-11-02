import { Link, useNavigate, useParams } from 'react-router';
import { graphqlRequest, mutationValue } from '../api/client.js';
import { CATEGORIES, CREATE_PRODUCT, PRODUCT_EDITOR, UPDATE_PRODUCT } from '../api/operations.js';
import { EmptyState, ErrorAlert, LoadingState } from '../components/Feedback.jsx';
import ProductForm from '../components/ProductForm.jsx';
import useQuery from '../hooks/useQuery.js';

export default function ProductFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useQuery(id ? PRODUCT_EDITOR : CATEGORIES, id ? { id } : {});
  async function save(input) {
    const name = id ? 'updateProduct' : 'createProduct';
    const result = mutationValue(await graphqlRequest(id ? UPDATE_PRODUCT : CREATE_PRODUCT, { input }), name);
    navigate(`/products/${result.product.id}`, { state: { notice: id ? 'Product changes saved.' : 'Product created. Opening stock has been recorded.' }, replace: true });
    return result;
  }
  return <>
    <Link className="back-link" to={id ? `/products/${id}` : '/products'}>← Back to {id ? 'product' : 'products'}</Link>
    <div className="page-heading"><div><div className="eyebrow">PRODUCT DETAILS</div><h1>{id ? 'Edit product' : 'Add a product'}</h1><p>{id ? 'Update the details. Stock changes are recorded separately.' : 'Create a product and record its opening stock.'}</p></div></div>
    <ErrorAlert error={error} onRetry={refetch} />
    {loading && <LoadingState />}
    {data && (id && !data.product ? <EmptyState title="Product not found"><Link to="/products">Back to products</Link></EmptyState> : data.product?.archivedAt ? <div className="alert alert-secondary">Archived products are read-only.</div> : <section className="panel form-panel"><ProductForm key={id || 'new'} product={data.product} categories={data.categories} onSave={save} /></section>)}
  </>;
}
