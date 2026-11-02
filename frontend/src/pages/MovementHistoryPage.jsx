import { useState } from 'react';
import { HISTORY } from '../api/operations.js';
import { ErrorAlert, Field, LoadingState, Pagination } from '../components/Feedback.jsx';
import MovementTable, { movementLabels } from '../components/MovementTable.jsx';
import useQuery from '../hooks/useQuery.js';

const LIMIT = 20;
const initial = { search: '', movementType: '', fromDate: '', toDate: '' };

export default function MovementHistoryPage() {
  const [values, setValues] = useState(initial);
  const [filter, setFilter] = useState({});
  const [offset, setOffset] = useState(0);
  const { data, loading, error, refetch } = useQuery(HISTORY, { filter, limit: LIMIT, offset });
  const change = (event) => setValues({ ...values, [event.target.name]: event.target.value });
  function submit(event) { event.preventDefault(); setOffset(0); setFilter(Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '').map(([key, value]) => [key, value.trim()]))); }
  return <>
    <div className="page-heading"><div><div className="eyebrow">A COMPLETE AUDIT TRAIL</div><h1>Movement history</h1><p>Follow every unit, from opening stock to the latest adjustment.</p></div></div>
    <ErrorAlert error={error} onRetry={refetch} />
    <section className="panel"><form className="history-filters" onSubmit={submit}>
      <div className="row g-3 align-items-end"><div className="col-md-6 col-xl-3"><Field label="Product SKU or name" name="search" type="search" value={values.search} onChange={change} maxLength={160} placeholder="Search products…" /></div>
        <div className="col-md-6 col-xl-3"><Field label="Movement type" name="movementType" as="select" value={values.movementType} onChange={change}><option value="">All movements</option>{Object.entries(movementLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Field></div>
        <div className="col-md-6 col-xl-3"><Field label="From date (UTC)" name="fromDate" type="date" value={values.fromDate} onChange={change} /></div>
        <div className="col-md-6 col-xl-3"><Field label="To date (UTC)" name="toDate" type="date" value={values.toDate} onChange={change} /></div>
      </div><div className="d-flex gap-2"><button type="submit" className="btn btn-primary btn-sm">Apply filters</button><button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => { setValues(initial); setFilter({}); setOffset(0); }}>Clear filters</button></div>
    </form>
      {loading && <LoadingState />}
      {data && <><MovementTable movements={data.stockMovements.items} /><Pagination total={data.stockMovements.totalCount} offset={offset} limit={LIMIT} onChange={setOffset} /></>}
    </section>
  </>;
}
