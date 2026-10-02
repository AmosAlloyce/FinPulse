import { useEffect, useRef } from 'react';
import {
  ArrowUpRight,
  X,
  LoaderCircle,
  ArrowRight,
  Check,
  AlertTriangle,
  Database,
} from 'lucide-react';

export const fmt = (value) =>
  new Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format(Number(value) || 0);
export const pct = (value) => `${Number(value || 0).toFixed(1)}%`;
export const title = (value) =>
  String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
export const countryNames = {
  KEN: 'Kenya',
  UGA: 'Uganda',
  GHA: 'Ghana',
  TZA: 'Tanzania',
  ZMB: 'Zambia',
};
export const currencyNames = { KEN: 'KES', UGA: 'UGX', GHA: 'GHS', TZA: 'TZS', ZMB: 'ZMW' };
export const shortId = (value) => (value ? String(value).slice(0, 8) : '—');
export const stamp = (value) =>
  value
    ? new Date(value).toLocaleTimeString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : '—';

export function Button({ children, secondary, quiet, busy, className = '', ...props }) {
  return (
    <button
      className={`button ${secondary ? 'secondary' : ''} ${quiet ? 'quiet' : ''} ${className}`}
      {...props}
      disabled={props.disabled || busy}
    >
      {busy && <LoaderCircle size={17} className="spin" />}
      {children}
    </button>
  );
}
export function Badge({ children, tone = 'blue' }) {
  return (
    <span className={`badge ${tone}`}>
      <i />
      {children}
    </span>
  );
}
export function PanelHead({ label, title: heading, children }) {
  return (
    <div className="panel-head">
      <div>
        {label && <span className="eyebrow">{label}</span>}
        <h2>{heading}</h2>
      </div>
      {children}
    </div>
  );
}
export function Stat({ label, value, unit, description, icon: Icon, tone = '' }) {
  return (
    <article className={`stat ${tone}`}>
      <div className="stat-label">
        {label}
        {Icon && <Icon size={19} />}
      </div>
      <div className="stat-value">
        {value}
        <span>{unit}</span>
      </div>
      <p>{description}</p>
    </article>
  );
}
export function Empty({ title: heading = 'Nothing here yet', children }) {
  return (
    <div className="empty">
      <Database size={30} />
      <h3>{heading}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Modal({ title: heading, kicker, close, children, wide = false }) {
  const ref = useRef(null);
  const before = useRef(null);
  useEffect(() => {
    before.current = document.activeElement;
    ref.current.showModal();
    return () => before.current?.focus();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? 'wide' : ''}`}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClick={(event) => {
        if (event.target === ref.current) close();
      }}
    >
      <div className="modal-head">
        <div>
          {kicker && <span className="eyebrow">{kicker}</span>}
          <h2>{heading}</h2>
        </div>
        <button className="icon-button" aria-label="Close dialog" onClick={close}>
          <X size={22} />
        </button>
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
export function Donut({ parts = [], total, label }) {
  const sum = total || parts.reduce((n, item) => n + Number(item.count || 0), 0);
  const colors = ['#254bdf', '#6194ed', '#9fbaf2', '#a0b4b8', '#d4dca7', '#eaac78', '#dde1e9'];
  let offset = 0;
  return (
    <div className="donut-layout">
      <div className="donut">
        <svg viewBox="0 0 180 180" role="img" aria-label={`${fmt(sum)} ${label}`}>
          <circle cx="90" cy="90" r="69" fill="none" stroke="#edf0f5" strokeWidth="19" />
          {parts.map((part, i) => {
            const portion = sum ? (Number(part.count) / sum) * 100 : 0;
            const start = offset;
            offset += portion;
            return (
              <circle
                key={part.name}
                cx="90"
                cy="90"
                r="69"
                fill="none"
                stroke={colors[i % colors.length]}
                strokeWidth="19"
                pathLength="100"
                strokeDasharray={`${Math.max(0, portion - 0.8)} ${100 - Math.max(0, portion - 0.8)}`}
                strokeDashoffset={-start}
                transform="rotate(-90 90 90)"
              >
                <title>
                  {title(part.name)}: {fmt(part.count)}
                </title>
              </circle>
            );
          })}
        </svg>
        <div>
          <strong>{fmt(sum)}</strong>
          <span>{label}</span>
        </div>
      </div>
      <div className="chart-legend">
        {parts.map((part, i) => (
          <div key={part.name}>
            <i style={{ background: colors[i % colors.length] }} />
            <span>{title(part.name)}</span>
            <strong>{fmt(part.count)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
export function BarChart({
  items,
  valueKey = 'count',
  labelKey = 'name',
  format = fmt,
  color = 'blue',
}) {
  const max = Math.max(1, ...items.map((item) => Number(item[valueKey]) || 0));
  return (
    <div className={`bar-chart ${color}`}>
      {items.map((item, index) => (
        <div className="bar-item" key={`${item[labelKey]}-${index}`}>
          <div>
            <span>{countryNames[item[labelKey]] || title(item[labelKey])}</span>
            <strong>{format(item[valueKey])}</strong>
          </div>
          <div className="bar-track">
            <div style={{ width: `${Math.max(0, (Number(item[valueKey] || 0) / max) * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
export function Flow({ steps, selected, onSelect, running = false }) {
  return (
    <div className={`flow ${running ? 'running' : ''}`}>
      {steps.map((step, i) => (
        <div className="flow-wrap" key={step.id || i}>
          <button
            className={`flow-node ${selected === i ? 'selected' : ''}`}
            onClick={() => onSelect(i)}
            aria-pressed={selected === i}
          >
            <div className="flow-node-top">
              <span>{String(i + 1).padStart(2, '0')}</span>
              {step.status === 'completed' ? (
                <Check size={17} />
              ) : step.status === 'warning' ? (
                <AlertTriangle size={17} />
              ) : (
                <span className="node-dot" />
              )}
            </div>
            <strong>{step.title || title(step.name)}</strong>
            <p>{step.subtitle || step.description}</p>
            <div className="flow-node-footer">
              <span>{step.count != null ? `${fmt(step.count)} records` : 'Inspect stage'}</span>
              <ArrowUpRight size={15} />
            </div>
          </button>
          {i < steps.length - 1 && <ArrowRight className="flow-arrow" size={22} />}
        </div>
      ))}
    </div>
  );
}
export function Table({ columns, rows, onRow, rowLabel, empty = 'No matching records.' }) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable data table">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.event_id || row.id || i}>
              {columns.map((column, j) => (
                <td key={column.key}>
                  {j === 0 && onRow ? (
                    <button
                      className="table-link"
                      onClick={() => onRow(row)}
                      aria-label={rowLabel?.(row)}
                    >
                      {column.render ? column.render(row) : row[column.key]}
                      <ArrowUpRight size={14} />
                    </button>
                  ) : column.render ? (
                    column.render(row)
                  ) : (
                    (row[column.key] ?? '—')
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <div className="table-empty">{empty}</div>}
    </div>
  );
}
