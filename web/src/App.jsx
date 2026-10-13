import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  BarChart3,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Copy,
  Database,
  ExternalLink,
  FileJson,
  Filter,
  Fingerprint,
  GitBranch,
  Globe2,
  Info,
  Layers3,
  LoaderCircle,
  Menu,
  Play,
  Radio,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
  X,
  AlertTriangle,
} from 'lucide-react';
import {
  Badge,
  BarChart,
  Button,
  countryNames,
  Donut,
  Empty,
  Flow,
  fmt,
  Modal,
  PanelHead,
  pct,
  shortId,
  stamp,
  Stat,
  Table,
  title,
} from './components.jsx';
import { exportUrl, request } from './api.js';
import SignalLens from './SignalLens.jsx';

const sections = [
  {
    id: 'overview',
    name: 'Pulse overview',
    icon: Activity,
    caption: 'A clear view of the system.',
  },
  { id: 'events', name: 'Event explorer', icon: Radio, caption: 'Every signal has a story.' },
  {
    id: 'quality',
    name: 'Quality lab',
    icon: ShieldCheck,
    caption: 'Trust starts with the details.',
  },
  {
    id: 'pipeline',
    name: 'Pipeline studio',
    icon: Workflow,
    caption: 'From raw signals to useful data.',
  },
  {
    id: 'markets',
    name: 'Market insights',
    icon: Globe2,
    caption: 'Five markets. One connected view.',
  },
  {
    id: 'products',
    name: 'Data products',
    icon: Layers3,
    caption: 'Data, ready for its next purpose.',
  },
];
const scenarioOptions = [
  {
    id: 'normal',
    title: 'Everyday activity',
    description: 'Create coherent customer, usage, mobile-money and credit events.',
    icon: Activity,
    color: 'blue',
  },
  {
    id: 'duplicates',
    title: 'Duplicate delivery',
    description: 'Replay existing event IDs. Watch deduplication protect the warehouse.',
    icon: Copy,
    color: 'purple',
  },
  {
    id: 'invalid',
    title: 'Quality incident',
    description: 'Inject a known timestamp error, then inspect and approve its correction.',
    icon: AlertTriangle,
    color: 'amber',
  },
  {
    id: 'late',
    title: 'Late arrival',
    description: 'Deliver events over 24 hours late. Preserve them with a freshness warning.',
    icon: Clock3,
    color: 'green',
  },
];
const eventLabels = {
  customer_registered: 'Identity',
  gsm_usage: 'GSM usage',
  mobile_money_transaction: 'Mobile money',
  device_signal: 'Device signal',
  loan_application: 'Application',
  loan_decision: 'Decision',
  repayment: 'Repayment',
};
const statusTone = {
  accepted: 'green',
  pending: 'blue',
  duplicate: 'neutral',
  quarantined: 'amber',
  replayed: 'purple',
  open: 'amber',
  resolved: 'green',
  repaired: 'green',
};
const relativePath = () =>
  window.location.pathname.replace(/^\/finpulse\/?/, '').split('/')[0] || 'overview';
const money = (value, currency) => `${currency || ''} ${fmt(value)}`;
const asParts = (types) => (types || []).map((item) => ({ name: item.type, count: item.count }));

function PulseMark({ small = false }) {
  return (
    <span className={`pulse-mark ${small ? 'small' : ''}`}>
      <Activity size={small ? 20 : 25} strokeWidth={2.3} />
    </span>
  );
}

function Trend({ data = [] }) {
  const [hover, setHover] = useState(null);
  const buckets = data.slice(-36);
  const max = Math.max(1, ...buckets.map((item) => item.count));
  const points = buckets.map((item, i) => [
    38 + (i * 610) / Math.max(buckets.length - 1, 1),
    175 - (item.count / max) * 130,
  ]);
  const line = points.map(([x, y], i) => `${i ? 'L' : 'M'}${x},${y}`).join(' ');
  return (
    <div className="trend-chart">
      <svg
        viewBox="0 0 680 216"
        role="img"
        aria-label="Actual accepted events by event-time minute"
      >
        <defs>
          <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3254e7" stopOpacity=".17" />
            <stop offset="100%" stopColor="#3254e7" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 0.5, 1].map((t) => (
          <g key={t}>
            <line
              x1="38"
              x2="650"
              y1={175 - t * 130}
              y2={175 - t * 130}
              stroke="#e6eaf0"
              strokeDasharray="4 5"
            />
            <text x="0" y={179 - t * 130}>
              {fmt(max * t)}
            </text>
          </g>
        ))}
        {points.length > 0 && (
          <>
            <path d={`${line} L${points.at(-1)[0]},175 L38,175 Z`} fill="url(#trend-fill)" />
            <path
              d={line}
              fill="none"
              stroke="#3254e7"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          </>
        )}
        {points.map(([x, y], i) => (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={hover === i ? 5 : 4}
            fill={hover === i ? '#173ddb' : '#fff'}
            stroke="#3254e7"
            strokeWidth="1.5"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <title>
              {stamp(buckets[i].time)} · {fmt(buckets[i].count)} events
            </title>
          </circle>
        ))}
        {buckets.length > 0 && (
          <>
            <text x="38" y="205">
              {stamp(buckets[0].time).slice(0, 5)}
            </text>
            <text x="648" y="205" textAnchor="end">
              {stamp(buckets.at(-1).time).slice(0, 5)}
            </text>
          </>
        )}
      </svg>
      <div className="chart-footnote">
        <span>
          <i />
          Accepted records · event-time minute buckets
        </span>
        <strong>
          {hover != null
            ? `${fmt(buckets[hover].count)} events at ${stamp(buckets[hover].time)}`
            : 'Hover a point to inspect'}
        </strong>
      </div>
    </div>
  );
}

function Overview({ data, navigate, simulate, inspect }) {
  const stats = data.stats;
  const markets = data.analytics.byCountry;
  const lastRun = data.runs[0];
  const columns = [
    {
      key: 'eventId',
      label: 'Event',
      render: (row) => <span className="mono">{shortId(row.eventId)}</span>,
    },
    {
      key: 'eventType',
      label: 'Source signal',
      render: (row) => (
        <span className="type-label">
          <span className={`type-dot ${row.source}`} />
          {eventLabels[row.eventType] || title(row.eventType)}
        </span>
      ),
    },
    { key: 'countryCode', label: 'Market', render: (row) => countryNames[row.countryCode] },
    {
      key: 'status',
      label: 'Status',
      render: (row) => <Badge tone={statusTone[row.status]}>{title(row.status)}</Badge>,
    },
  ];
  return (
    <>
      <SignalLens data={data} inspect={inspect} simulate={simulate} />
      <div className="section-kicker">
        <span>WORKSPACE HEALTH</span>
        <span>
          Calculated from your isolated sample warehouse <CircleHelp size={14} />
        </span>
      </div>
      <div className="stats-grid">
        <Stat
          label="Events curated"
          value={fmt(stats.accepted)}
          description={`${fmt(stats.received)} deliveries received`}
          icon={Database}
        />
        <Stat
          label="Data acceptance"
          value={Number(stats.qualityScore).toFixed(1)}
          unit="%"
          description="Duplicates excluded from denominator"
          icon={ShieldCheck}
          tone="green"
        />
        <Stat
          label="Quality exceptions"
          value={fmt(stats.openQuarantine)}
          description="Open records ready for investigation"
          icon={Filter}
          tone="amber"
        />
        <Stat
          label="Connected markets"
          value={stats.countries}
          unit="/ 5"
          description={`${fmt(stats.customers)} fictional customer profiles`}
          icon={Globe2}
        />
      </div>
      <div className="overview-grid">
        <section className="panel">
          <PanelHead label="SIGNAL VOLUME" title="The shape of your data">
            <Badge tone="neutral">Actual records</Badge>
          </PanelHead>
          <Trend data={data.analytics.timeline} />
        </section>
        <section className="panel market-mini">
          <PanelHead label="ACROSS BORDERS" title="Market activity">
            <button
              className="icon-button"
              aria-label="Explore markets"
              onClick={() => navigate('markets')}
            >
              <ArrowUpRight size={19} />
            </button>
          </PanelHead>
          <div className="market-list">
            {markets.map((item) => (
              <button key={item.countryCode} onClick={() => navigate('markets', item.countryCode)}>
                <span className="country-token">{item.countryCode.slice(0, 2)}</span>
                <span>
                  <strong>{item.country}</strong>
                  <small>
                    {item.currency} · {fmt(item.customers)} profiles
                  </small>
                </span>
                <b>
                  {fmt(item.events)}
                  <small>events</small>
                </b>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
        </section>
      </div>
      <div className="overview-grid lower">
        <section className="panel">
          <PanelHead label="THE LATEST ARRIVALS" title="Signals, with context">
            <Button quiet onClick={() => navigate('events')}>
              All events <ArrowRight size={16} />
            </Button>
          </PanelHead>
          <Table
            rows={data.events.slice(0, 6)}
            columns={columns}
            onRow={inspect}
            rowLabel={(row) => `Inspect event ${shortId(row.eventId)}`}
          />
          <div className="panel-footer">
            <Fingerprint size={15} />
            Every record has an event ID, source, and trace.
          </div>
        </section>
        <section className="pipeline-summary">
          <span className="eyebrow">FROM BRONZE TO GOLD</span>
          <h2>
            A path you
            <br />
            can <em>inspect.</em>
          </h2>
          <div className="mini-lineage">
            {['Receive', 'Validate', 'Curate', 'Publish'].map((item, i) => (
              <div key={item}>
                <span>{i + 1}</span>
                <strong>{item}</strong>
                <Check size={15} />
              </div>
            ))}
          </div>
          <p>
            {lastRun
              ? `Last run completed in ${fmt(lastRun.durationMs)} ms. ${fmt(stats.pending)} events are waiting for the next run.`
              : 'Stage a scenario and follow each processing step.'}
          </p>
          <Button secondary onClick={() => navigate('pipeline')}>
            Open pipeline studio <ArrowUpRight size={16} />
          </Button>
        </section>
      </div>
    </>
  );
}

function Events({ data, country, inspect, simulate, notify }) {
  const [filters, setFilters] = useState({ status: '', type: '', search: '', offset: 0 });
  const [listing, setListing] = useState({ events: [], total: 0 });
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    const params = new URLSearchParams({ limit: '25', offset: String(filters.offset) });
    if (country !== 'all') params.set('country', country);
    if (filters.status) params.set('status', filters.status);
    if (filters.type) params.set('type', filters.type);
    request(`/events?${params}`)
      .then((result) => {
        if (active) setListing(result);
      })
      .catch((error) => {
        if (active) notify(error.message, 'error');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters.status, filters.type, filters.offset, country, data.workspace.revision]);
  const rows = listing.events.filter((row) =>
    `${row.eventId} ${row.customerId} ${row.source}`
      .toLowerCase()
      .includes(filters.search.toLowerCase()),
  );
  const change = (key, value) =>
    setFilters((previous) => ({ ...previous, [key]: value, offset: 0 }));
  return (
    <>
      <div className="page-lead">
        <div>
          <span className="eyebrow">THE COMPLETE DELIVERY TRAIL</span>
          <h2>
            Look closer.
            <br />
            <em>Nothing gets lost.</em>
          </h2>
          <p>
            Accepted, duplicate, quarantined, or still waiting. Inspect the original payload and its
            path through the platform.
          </p>
        </div>
        <div className="lead-number">
          <strong>{fmt(data.stats.received)}</strong>
          <span>deliveries in your workspace</span>
        </div>
      </div>
      <section className="panel">
        <div className="table-toolbar">
          <label className="search-field">
            <Search size={18} />
            <input
              aria-label="Find on this page"
              placeholder="Find an ID on this page…"
              value={filters.search}
              onChange={(event) => change('search', event.target.value)}
            />
          </label>
          <div>
            <select
              aria-label="Delivery status"
              value={filters.status}
              onChange={(event) => change('status', event.target.value)}
            >
              <option value="">All statuses</option>
              {['accepted', 'pending', 'quarantined', 'duplicate', 'replayed'].map((value) => (
                <option key={value} value={value}>
                  {title(value)}
                </option>
              ))}
            </select>
            <select
              aria-label="Event type"
              value={filters.type}
              onChange={(event) => change('type', event.target.value)}
            >
              <option value="">All event types</option>
              {Object.entries(eventLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
        {loading ? (
          <div className="inline-loading">
            <LoaderCircle className="spin" /> Reading deliveries…
          </div>
        ) : (
          <Table
            rows={rows}
            columns={[
              {
                key: 'eventId',
                label: 'Event ID',
                render: (row) => <span className="mono">{shortId(row.eventId)}</span>,
              },
              {
                key: 'eventType',
                label: 'Event type',
                render: (row) => (
                  <span className="type-label">
                    <span className={`type-dot ${row.source}`} />
                    {eventLabels[row.eventType]}
                  </span>
                ),
              },
              {
                key: 'countryCode',
                label: 'Market',
                render: (row) => countryNames[row.countryCode],
              },
              {
                key: 'ingestedAt',
                label: 'Ingested',
                render: (row) => <span className="mono muted">{stamp(row.ingestedAt)}</span>,
              },
              {
                key: 'status',
                label: 'Disposition',
                render: (row) => (
                  <Badge tone={statusTone[row.status]}>
                    {row.late && row.status === 'accepted' ? 'Accepted · late' : title(row.status)}
                  </Badge>
                ),
              },
            ]}
            onRow={inspect}
            rowLabel={(row) => `Inspect event ${shortId(row.eventId)}`}
          />
        )}
        <div className="pagination">
          <span>{fmt(listing.total)} matching deliveries · 25 per page</span>
          <div>
            <button
              className="icon-button"
              aria-label="Previous page"
              disabled={!filters.offset || loading}
              onClick={() =>
                setFilters((previous) => ({
                  ...previous,
                  offset: Math.max(0, previous.offset - 25),
                }))
              }
            >
              <ChevronLeft size={19} />
            </button>
            <span>
              {Math.floor(filters.offset / 25) + 1} / {Math.max(1, Math.ceil(listing.total / 25))}
            </span>
            <button
              className="icon-button"
              aria-label="Next page"
              disabled={filters.offset + 25 >= listing.total || loading}
              onClick={() =>
                setFilters((previous) => ({ ...previous, offset: previous.offset + 25 }))
              }
            >
              <ChevronRight size={19} />
            </button>
          </div>
        </div>
      </section>
      <div className="hint-strip">
        <Radio size={20} />
        <div>
          <strong>Change the input. See what happens.</strong>
          <p>Generate a new batch, introduce duplicates, or test a late-arrival scenario.</p>
        </div>
        <Button secondary onClick={simulate}>
          Generate events <ArrowRight size={16} />
        </Button>
      </div>
    </>
  );
}

function Quality({ data, review, simulate, inspect }) {
  const [status, setStatus] = useState('open');
  const rows = data.quarantine.filter((row) => status === 'all' || row.status === status);
  return (
    <>
      <div className="page-lead">
        <div>
          <span className="eyebrow">QUALITY IS A PROCESS</span>
          <h2>
            Good data.
            <br />
            <em>With the evidence.</em>
          </h2>
          <p>
            Failures stay visible. Known corrections require your review, and the original delivery
            remains in the audit trail.
          </p>
        </div>
        <div className="quality-seal">
          <ShieldCheck size={31} />
          <strong>{pct(data.stats.qualityScore)}</strong>
          <span>data acceptance</span>
        </div>
      </div>
      <div className="quality-summary">
        <div>
          <span className="number amber-text">{data.stats.openQuarantine}</span>
          <span>open exceptions</span>
        </div>
        <div>
          <span className="number">{data.stats.duplicates}</span>
          <span>duplicates suppressed</span>
        </div>
        <div>
          <span className="number blue-text">{data.stats.late}</span>
          <span>late arrivals retained</span>
        </div>
        <p>
          Duplicates are a delivery characteristic. Late records are accepted with a warning;
          structurally invalid records are quarantined.
        </p>
      </div>
      <section className="panel">
        <PanelHead label="INVESTIGATE & RESOLVE" title="Quarantine queue">
          <select
            aria-label="Quarantine filter"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="open">Open exceptions</option>
            <option value="all">All records</option>
          </select>
        </PanelHead>
        <Table
          rows={rows}
          columns={[
            {
              key: 'eventId',
              label: 'Event',
              render: (row) => <span className="mono">{shortId(row.eventId)}</span>,
            },
            {
              key: 'rule',
              label: 'Failed rule',
              render: (row) => (
                <span className="rule-name">
                  {title(row.rule)}
                  <small>
                    {eventLabels[row.eventType]} · {countryNames[row.countryCode]}
                  </small>
                </span>
              ),
            },
            {
              key: 'status',
              label: 'Status',
              render: (row) => (
                <Badge tone={statusTone[row.status] || 'green'}>{title(row.status)}</Badge>
              ),
            },
            {
              key: 'action',
              label: 'Next step',
              render: (row) =>
                row.status === 'open' && row.canReplay ? (
                  <Button quiet onClick={() => review(row)}>
                    Review correction <ArrowUpRight size={16} />
                  </Button>
                ) : (
                  <Button quiet onClick={() => inspect(row)}>
                    View trace <ArrowUpRight size={16} />
                  </Button>
                ),
            },
          ]}
          onRow={inspect}
          empty="No open exceptions. Generate a quality incident to explore the review flow."
        />
      </section>
      <section className="rules-section">
        <PanelHead label="THE QUALITY CONTRACT" title="Rules, not guesswork">
          <span className="muted">Executed by the original Python engine</span>
        </PanelHead>
        <div className="rules-grid">
          {data.qualityRules.map((rule, i) => (
            <article key={rule.id}>
              <span className="rule-index">{String(i + 1).padStart(2, '0')}</span>
              <h3>{rule.label}</h3>
              <p>{rule.description}</p>
              <div>
                <Badge tone={rule.severity === 'warning' ? 'amber' : 'green'}>
                  {rule.severity === 'warning'
                    ? 'Warn & retain'
                    : rule.severity === 'info'
                      ? 'Suppress repeat delivery'
                      : 'Block & quarantine'}
                </Badge>
                <code>{rule.id}</code>
              </div>
            </article>
          ))}
        </div>
      </section>
      <div className="hint-strip">
        <AlertTriangle size={21} />
        <div>
          <strong>Try a controlled incident.</strong>
          <p>Inject a timestamp fault and see the same rules catch it.</p>
        </div>
        <Button secondary onClick={() => simulate('invalid')}>
          Create an incident <ArrowRight size={16} />
        </Button>
      </div>
    </>
  );
}

function Pipeline({ data, mutate, busy, simulate }) {
  const [selected, setSelected] = useState(0);
  const [runId, setRunId] = useState(null);
  const run = data.runs.find((item) => item.id === runId) || data.runs[0];
  const steps = (run?.steps || []).map((step) => ({
    ...step,
    title: step.label,
    subtitle: step.detail,
    status: step.status === 'complete' ? 'completed' : step.status,
  }));
  const active = steps[Math.min(selected, steps.length - 1)];
  return (
    <>
      <div className="page-lead">
        <div>
          <span className="eyebrow">THE ENGINE, MADE VISIBLE</span>
          <h2>
            Follow every stage.
            <br />
            <em>Trust every handoff.</em>
          </h2>
          <p>
            Stage an event batch, run the original validation and loading code, then inspect its
            counts and outcomes.
          </p>
        </div>
        <div className="pipeline-actions">
          <Badge tone={data.stats.pending ? 'amber' : 'green'}>
            {fmt(data.stats.pending)} events waiting
          </Badge>
          <Button
            busy={busy}
            disabled={!data.stats.pending}
            onClick={() => {
              setRunId(null);
              mutate(
                '/pipeline/run',
                {},
                'Pipeline completed. Open any stage to inspect its result.',
              );
            }}
          >
            <Play size={16} />
            Run pipeline
          </Button>
        </div>
      </div>
      <section className="pipeline-canvas">
        <div className="canvas-topline">
          <span>
            <Workflow size={17} /> EVENT-TO-INSIGHT PIPELINE
          </span>
          <Badge tone="neutral">Original Python tools · SQLite serving</Badge>
        </div>
        <Flow steps={steps} selected={selected} onSelect={setSelected} running={busy} />
        {active && (
          <div className="step-inspector">
            <div className="step-inspector-title">
              <span className="step-number">{String(selected + 1).padStart(2, '0')}</span>
              <div>
                <span className="eyebrow">SELECTED STEP</span>
                <h3>{active.title}</h3>
              </div>
              <Badge tone="green">Executed</Badge>
            </div>
            <p>{active.detail}</p>
            <div className="step-metrics">
              <div>
                <span>Records examined</span>
                <strong>{fmt(active.count)}</strong>
              </div>
              <div>
                <span>Execution time</span>
                <strong>
                  {fmt(active.durationMs)} <small>ms</small>
                </strong>
              </div>
              <div>
                <span>Run reference</span>
                <code>{run?.id}</code>
              </div>
            </div>
          </div>
        )}
        <div className="canvas-footer">
          <span>
            <Info size={16} /> These results come from executed tools. Spark and Kafka are
            documented in the full deployment architecture.
          </span>
          <Button quiet onClick={simulate}>
            Stage another batch <ArrowRight size={16} />
          </Button>
        </div>
      </section>
      <div className="overview-grid lower">
        <section className="panel">
          <PanelHead label="REPEATABLE BY DESIGN" title="Run history">
            <span className="muted">{data.runs.length} runs</span>
          </PanelHead>
          <div className="run-list">
            {data.runs.slice(0, 8).map((item) => (
              <button
                key={item.id}
                className={run?.id === item.id ? 'active' : ''}
                onClick={() => {
                  setRunId(item.id);
                  setSelected(0);
                }}
              >
                <span className="run-check">
                  <Check size={17} />
                </span>
                <span>
                  <strong>{title(item.trigger)}</strong>
                  <small>
                    {stamp(item.createdAt)} · {fmt(item.counts.received)} deliveries
                  </small>
                </span>
                <span>
                  {fmt(item.durationMs)} ms
                  <ChevronRight size={16} />
                </span>
              </button>
            ))}
          </div>
        </section>
        <section className="panel">
          <PanelHead label="ACCOUNTABILITY" title="Activity trail" />
          <div className="audit-list">
            {data.audit.slice(0, 6).map((event) => (
              <div key={event.id}>
                <span className="audit-dot" />
                <div>
                  <strong>{event.action}</strong>
                  <p>{event.detail}</p>
                  <time>{stamp(event.createdAt)}</time>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function Markets({ data, country }) {
  const rows = data.analytics.byCountry;
  const [metric, setMetric] = useState('applications');
  const totals = rows.reduce(
    (acc, item) => ({
      applications: acc.applications + item.applications,
      decisions: acc.decisions + item.decisions,
      approvals: acc.approvals + item.approvals,
    }),
    { applications: 0, decisions: 0, approvals: 0 },
  );
  return (
    <>
      <div className="page-lead">
        <div>
          <span className="eyebrow">A REGIONAL PERSPECTIVE</span>
          <h2>
            See the whole picture.
            <br />
            <em>Keep the local context.</em>
          </h2>
          <p>
            Explore synthetic credit and mobile-money activity across five African markets. Currency
            boundaries stay explicit.
          </p>
        </div>
        <Badge tone="neutral">
          {country === 'all' ? 'All markets' : countryNames[country]} · fictional records
        </Badge>
      </div>
      <div className="stats-grid three">
        <Stat
          label="Applications"
          value={fmt(totals.applications)}
          description="One row per application"
          icon={FileJson}
        />
        <Stat
          label="Decisions observed"
          value={fmt(totals.decisions)}
          description="Latest known decision per application"
          icon={GitBranch}
        />
        <Stat
          label="Sample approval rate"
          value={
            totals.decisions ? ((totals.approvals / totals.decisions) * 100).toFixed(1) : '0.0'
          }
          unit="%"
          description="Approved / decided applications"
          icon={BarChart3}
        />
      </div>
      <div className="overview-grid">
        <section className="panel">
          <PanelHead label="COMPARE MARKETS" title="Activity across the region">
            <select
              aria-label="Comparison metric"
              value={metric}
              onChange={(event) => setMetric(event.target.value)}
            >
              <option value="applications">Applications</option>
              <option value="events">Accepted events</option>
              <option value="transactions">Money transactions</option>
              <option value="approvalRate">Approval rate</option>
            </select>
          </PanelHead>
          <BarChart
            items={rows.map((row) => ({ ...row, name: row.countryCode }))}
            valueKey={metric}
            format={metric === 'approvalRate' ? pct : fmt}
          />
        </section>
        <section className="panel">
          <PanelHead label="FROM INTEREST TO REPAYMENT" title="The credit journey" />
          <div className="funnel">
            {data.analytics.funnel.map((item, i) => (
              <div key={item.label}>
                <span>{String(i + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{item.label}</strong>
                  <div className="funnel-track">
                    <i
                      style={{
                        width: `${Math.max(2, (item.value / Math.max(1, data.analytics.funnel[0]?.value || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <b>{fmt(item.value)}</b>
              </div>
            ))}
          </div>
          <p className="panel-note">
            Sample events, not a lending recommendation. Settled payments are payment records, not
            unique loans.
          </p>
        </section>
      </div>
      <section className="panel market-table">
        <PanelHead label="CURRENCY-AWARE BY DESIGN" title="Market performance">
          <a
            className="button secondary"
            href={`${exportUrl}?dataset=countries${country === 'all' ? '' : `&country=${country}`}`}
          >
            <ArrowDownToLine size={17} />
            Export markets
          </a>
        </PanelHead>
        <Table
          rows={rows}
          columns={[
            {
              key: 'country',
              label: 'Market',
              render: (row) => (
                <strong>
                  {row.country}
                  <small className="table-sub">{row.currency}</small>
                </strong>
              ),
            },
            { key: 'applications', label: 'Applications', render: (row) => fmt(row.applications) },
            { key: 'approvalRate', label: 'Approval rate', render: (row) => pct(row.approvalRate) },
            {
              key: 'par30',
              label: 'Observed PAR30',
              render: (row) => (row.par30 == null ? 'No repayments' : pct(row.par30)),
            },
            {
              key: 'approvedValue',
              label: 'Approved value',
              render: (row) => money(row.approvedValue, row.currency),
            },
            {
              key: 'transactionValue',
              label: 'Mobile-money volume',
              render: (row) => money(row.transactionValue, row.currency),
            },
          ]}
        />
        <div className="panel-footer">
          <Info size={16} />
          Values use local currencies and are never added across markets. PAR30 reflects repayment
          observations, not a production exposure-weighted risk calculation.
        </div>
      </section>
    </>
  );
}

function Products({ data, country }) {
  const [selectedId, setSelectedId] = useState(data.products[0]?.id);
  const [tab, setTab] = useState('preview');
  const product = data.products.find((item) => item.id === selectedId) || data.products[0];
  const dataset = product?.exportDataset || 'portfolio';
  return (
    <>
      <div className="page-lead">
        <div>
          <span className="eyebrow">BUILT FOR REUSE</span>
          <h2>
            From raw material
            <br />
            to <em>data products.</em>
          </h2>
          <p>
            Explore the schema, grain and lineage behind each curated dataset. Download the same
            synthetic data that powers the workspace.
          </p>
        </div>
        <Layers3 size={52} strokeWidth={1.15} className="lead-icon" />
      </div>
      <div className="product-layout">
        <div className="product-list">
          {data.products.map((item) => (
            <button
              key={item.id}
              className={item.id === product?.id ? 'active' : ''}
              onClick={() => {
                setSelectedId(item.id);
                setTab('preview');
              }}
            >
              <span className={`product-tier ${item.tier}`}>
                <Database size={18} />
              </span>
              <span>
                <strong>{item.name}</strong>
                <small>
                  {title(item.tier)} · {fmt(item.rows)} rows
                </small>
              </span>
              <ChevronRight size={17} />
            </button>
          ))}
        </div>
        {product && (
          <section className="panel product-detail">
            <PanelHead label={`${product.tier?.toUpperCase()} LAYER`} title={product.name}>
              <Badge tone="green">Queryable</Badge>
            </PanelHead>
            <p className="product-description">{product.description}</p>
            <div className="product-facts">
              <span>
                <Database size={15} />
                {fmt(product.rows)} rows
              </span>
              <span>
                <Layers3 size={15} />
                {product.columns.length} columns
              </span>
              <span>
                <Clock3 size={15} />
                Updated {stamp(product.updatedAt)}
              </span>
            </div>
            <div className="tabs" role="tablist" aria-label="Data product details">
              {['preview', 'schema', 'lineage'].map((item) => (
                <button
                  key={item}
                  role="tab"
                  aria-selected={tab === item}
                  onClick={() => setTab(item)}
                >
                  {title(item)}
                </button>
              ))}
            </div>
            {tab === 'schema' ? (
              <div className="schema-list">
                {product.columns.map((column, i) => (
                  <div key={column}>
                    <span>{String(i + 1).padStart(2, '0')}</span>
                    <code>{column}</code>
                    <Badge tone="neutral">
                      {column.endsWith('_id')
                        ? 'identifier'
                        : typeof product.preview?.find(row => row[column] != null)?.[column] === 'number'
                          ? 'numeric'
                          : 'field'}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : tab === 'lineage' ? (
              <div className="product-lineage">
                <p>Trace the dataset through its source and transformations.</p>
                {product.lineage.map((node, i) => (
                  <div key={node}>
                    <span>{i + 1}</span>
                    <strong>
                      {data.lineage.nodes.find((item) => item.id === node)?.label || title(node)}
                    </strong>
                    <ArrowRight size={17} />
                  </div>
                ))}
                <p className="muted">
                  The web demo executes original contracts, quality rules and SQL marts in SQLite.
                  Distributed infrastructure remains available in the repository.
                </p>
              </div>
            ) : (
              <Table
                rows={product.preview || []}
                columns={product.columns.map(column => ({
                  key: column,
                  label: title(column),
                  render: row => {
                    const value = row[column];
                    if (value == null) return <span className="muted">—</span>;
                    if (column.endsWith('_id')) return <code title={String(value)}>{shortId(value)}</code>;
                    if (typeof value === 'number') return fmt(value);
                    return <span title={String(value)}>{String(value).slice(0, 52)}</span>;
                  },
                }))}
              />
            )}
            <div className="product-download">
              <span>
                <Info size={15} />
                Preview is limited; the CSV includes the selected dataset.
              </span>
              <a
                className="button secondary"
                href={`${exportUrl}?dataset=${dataset}${country === 'all' ? '' : `&country=${country}`}`}
              >
                <ArrowDownToLine size={17} />
                Download CSV
              </a>
            </div>
          </section>
        )}
      </div>
      <div className="hint-strip">
        <BookOpen size={23} />
        <div>
          <strong>Explore the engineering behind it.</strong>
          <p>Event contracts, Spark, dbt, Airflow, infrastructure, and the interactive demo.</p>
        </div>
        <a
          className="button secondary"
          href="https://github.com/AmosAlloyce/FinPulse"
          target="_blank"
          rel="noreferrer"
        >
          View source <ArrowUpRight size={16} />
        </a>
      </div>
    </>
  );
}

function EventModal({ detail, close, inspectRelated }) {
  const [tab, setTab] = useState('trace');
  const [copied, setCopied] = useState(false);
  return (
    <Modal
      close={close}
      title={eventLabels[detail.event.eventType] || 'Event detail'}
      kicker={`DELIVERY ${shortId(detail.event.id)}`}
      wide
    >
      <div className="detail-summary">
        <Badge tone={statusTone[detail.event.status]}>{title(detail.event.status)}</Badge>
        <span>{countryNames[detail.event.countryCode]}</span>
        <span>{stamp(detail.event.ingestedAt)}</span>
      </div>
      <dl className="event-facts">
        <div>
          <dt>Canonical event ID</dt>
          <dd>{detail.event.eventId}</dd>
        </div>
        <div>
          <dt>Customer token</dt>
          <dd>{detail.event.customerId}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{title(detail.event.source)}</dd>
        </div>
        <div>
          <dt>Currency / amount</dt>
          <dd>
            {detail.event.amount != null
              ? money(detail.event.amount, detail.event.currency)
              : 'Not a monetary event'}
          </dd>
        </div>
      </dl>
      <div className="tabs" role="tablist" aria-label="Event detail view">
        {['trace', 'payload'].map((item) => (
          <button role="tab" key={item} aria-selected={item === tab} onClick={() => setTab(item)}>
            {item === 'trace' ? 'Processing trace' : 'Original payload'}
          </button>
        ))}
      </div>
      {tab === 'payload' ? (
        <div className="code-panel">
          <button
            className="copy-button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(JSON.stringify(detail.raw, null, 2));
                setCopied(true);
              } catch {
                setCopied(false);
              }
            }}
          >
            <Copy size={16} />
            {copied ? 'Copied' : 'Copy JSON'}
          </button>
          <pre>{JSON.stringify(detail.raw, null, 2)}</pre>
        </div>
      ) : (
        <div className="detail-trace">
          <div className="trace-row">
            <Radio size={20} />
            <div>
              <strong>Received from {title(detail.event.source)}</strong>
              <p>Original delivery preserved with a unique trace and event identifier.</p>
            </div>
            <Check size={17} />
          </div>
          <div className="trace-row">
            <ShieldCheck size={20} />
            <div>
              <strong>Contract and business-rule validation</strong>
              <p>
                {detail.issues?.length
                  ? detail.issues.map((issue) => issue.message).join(' ')
                  : 'No errors recorded for this delivery.'}
              </p>
            </div>
            {detail.issues?.some((issue) => issue.severity === 'error') ? (
              <AlertTriangle size={18} />
            ) : (
              <Check size={17} />
            )}
          </div>
          <div className="trace-row">
            <Database size={20} />
            <div>
              <strong>
                {detail.event.status === 'accepted'
                  ? 'Published to the curated warehouse'
                  : `Disposition: ${title(detail.event.status)}`}
              </strong>
              <p>
                {detail.event.status === 'duplicate'
                  ? 'The canonical ID already exists. Its value was not counted twice.'
                  : detail.event.status === 'pending'
                    ? 'Waiting for the next pipeline run.'
                    : detail.event.status === 'quarantined'
                      ? 'Excluded from curated data until a known correction is reviewed.'
                      : 'The original record remains traceable.'}
              </p>
            </div>
          </div>
          {detail.related?.length > 0 && (
            <>
              <h3>Related customer signals</h3>
              <div className="related-events">
                {detail.related.slice(0, 6).map((row) => (
                  <button key={row.id} onClick={() => inspectRelated(row)}>
                    <span>{eventLabels[row.eventType]}</span>
                    <code>{shortId(row.eventId)}</code>
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function App() {
  const [page, setPage] = useState(() =>
    sections.some((item) => item.id === relativePath()) ? relativePath() : 'overview',
  );
  const [country, setCountry] = useState('all');
  const [data, setData] = useState(null);
  const [failure, setFailure] = useState('');
  const [busy, setBusy] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [toast, setToast] = useState(null);
  const [modal, setModal] = useState(null);
  const [scenario, setScenario] = useState('normal');
  const [batch, setBatch] = useState(20);
  const [search, setSearch] = useState('');
  const timer = useRef(null);
  const notify = useCallback((message, tone = 'success') => {
    setToast({ message, tone });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 6500);
  }, []);
  const refresh = useCallback(async () => {
    const result = await request(`/workspace${country === 'all' ? '' : `?country=${country}`}`);
    setData(result);
    setFailure('');
    return result;
  }, [country]);
  useEffect(() => {
    let active = true;
    request(`/workspace${country === 'all' ? '' : `?country=${country}`}`)
      .then((result) => {
        if (active) {
          setData(result);
          setFailure('');
        }
      })
      .catch((error) => {
        if (active) setFailure(error.message);
      });
    return () => {
      active = false;
    };
  }, [country]);
  useEffect(() => {
    const pop = () =>
      setPage(sections.some((item) => item.id === relativePath()) ? relativePath() : 'overview');
    const key = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault();
        setModal({ type: 'search' });
      }
    };
    window.addEventListener('popstate', pop);
    window.addEventListener('keydown', key);
    return () => {
      window.removeEventListener('popstate', pop);
      window.removeEventListener('keydown', key);
      clearTimeout(timer.current);
    };
  }, []);
  function navigate(next, market) {
    setPage(next);
    setMobileMenu(false);
    setModal(null);
    if (market) setCountry(market);
    history.pushState({}, '', `${import.meta.env.BASE_URL}${next === 'overview' ? '' : next}`);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
  async function mutate(path, body, message) {
    setBusy(true);
    try {
      const result = await request(path, body);
      if (country === 'all') setData(result);
      else await refresh();
      setModal(null);
      notify(message);
      return result;
    } catch (error) {
      notify(error.message, 'error');
      return null;
    } finally {
      setBusy(false);
    }
  }
  function simulate(next = 'normal') {
    setScenario(typeof next === 'string' ? next : 'normal');
    setModal({ type: 'simulate' });
  }
  async function inspect(row) {
    try {
      const result = await request(`/events/${row.id}`);
      setModal({ type: 'event', detail: result });
    } catch (error) {
      notify(error.message, 'error');
    }
  }
  const current = sections.find((item) => item.id === page);
  return (
    <div className="finpulse">
      <a className="skip-link" href="#main-content">
        Skip to workspace
      </a>
      {mobileMenu && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <aside className={`sidebar ${mobileMenu ? 'open' : ''}`}>
        <a
          href={import.meta.env.BASE_URL}
          className="brand"
          onClick={(event) => {
            event.preventDefault();
            navigate('overview');
          }}
        >
          <PulseMark />
          <span>
            finpulse<span>THE CREDIT DATA WORKSPACE</span>
          </span>
        </a>
        <div className="workspace-switch">
          <span className="workspace-avatar">AA</span>
          <span>
            <strong>Alloyce’s workspace</strong>
            <small>Interactive portfolio</small>
          </span>
          <Badge tone="neutral">DEMO</Badge>
        </div>
        <p className="nav-label">EXPLORE THE SYSTEM</p>
        <nav aria-label="Workspace navigation">
          {sections.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? 'active' : ''}
              aria-current={page === item.id ? 'page' : undefined}
              onClick={() => navigate(item.id)}
            >
              <item.icon size={20} />
              <span>{item.name}</span>
              {item.id === 'quality' && data?.stats.openQuarantine > 0 ? (
                <b>{data.stats.openQuarantine}</b>
              ) : item.id === page ? (
                <span className="nav-dot" />
              ) : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sandbox-note">
            <span className="status-dot" />
            <strong>Your own sandbox</strong>
            <p>
              Fictional data. Real processing.
              <br />
              Changes stay in your session.
            </p>
          </div>
          <button className="sidebar-link" onClick={() => setModal({ type: 'guide' })}>
            <CircleHelp size={18} />A quick orientation
            <ArrowUpRight size={15} />
          </button>
          <button className="sidebar-link" onClick={() => { setMobileMenu(false); setModal({ type: 'demo' }); }}>
            <Play size={18} />Watch the walkthrough
            <span className="demo-length" aria-hidden="true">1:53</span>
          </button>
          <a className="sidebar-link" href="/">
            <ArrowLeft size={18} />
            Alloyce’s portfolio
          </a>
          <div className="sidebar-credit">
            <span>Built by Alloyce Amos</span>
            <a
              href="https://github.com/AmosAlloyce/FinPulse"
              target="_blank"
              rel="noreferrer"
              aria-label="FinPulse source code"
            >
              <ExternalLink size={15} />
            </a>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-toggle"
              aria-label="Open navigation"
              onClick={() => setMobileMenu(true)}
            >
              <Menu size={23} />
            </button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={15} />
              <strong>{current.name}</strong>
            </span>
          </div>
          <div className="topbar-actions">
            <a
              href="tests.html"
              className="quick-search"
              style={{ textDecoration: 'none', color: '#27c997', borderColor: 'rgba(39, 201, 151, 0.4)', gap: '6px' }}
              title="Automated Selenium E2E Test Suite (28/28 Pass)"
            >
              <Check size={16} />
              <span>28/28 E2E Pass</span>
            </a>
            <button
              className="quick-search"
              onClick={() => {
                setSearch('');
                setModal({ type: 'search' });
              }}
            >
              <Search size={17} />
              <span>Jump to…</span>
              <kbd>⌘ K</kbd>
            </button>
            <button
              className="icon-button"
              aria-label="Reset demo"
              onClick={() => setModal({ type: 'reset' })}
            >
              <RotateCcw size={18} />
            </button>
            <span className="avatar">AA</span>
          </div>
        </header>
        <main id="main-content">
          <div className="workspace-heading">
            <div>
              <span className="eyebrow">
                FINPULSE / {String(sections.indexOf(current) + 1).padStart(2, '0')}
              </span>
              <h1>{current.name}</h1>
              <p>{current.caption}</p>
            </div>
            <div className="workspace-actions">
              <label className="country-select">
                <Globe2 size={17} />
                <select
                  aria-label="Market filter"
                  value={country}
                  onChange={(event) => setCountry(event.target.value)}
                >
                  <option value="all">All markets</option>
                  {Object.entries(countryNames).map(([code, name]) => (
                    <option key={code} value={code}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <Button secondary onClick={() => simulate()}>
                <Radio size={17} />
                Generate events
              </Button>
            </div>
          </div>
          {failure ? (
            <div className="error-panel">
              <AlertTriangle size={30} />
              <h2>Let’s reconnect.</h2>
              <p>{failure}</p>
              <Button onClick={() => refresh().catch((error) => setFailure(error.message))}>
                Try again
              </Button>
            </div>
          ) : !data ? (
            <div className="loading-screen">
              <PulseMark />
              <h2>Connecting the signals…</h2>
              <p>Preparing your own synthetic data workspace.</p>
              <LoaderCircle className="spin" size={24} />
            </div>
          ) : (
            <>
              {country !== 'all' && (
                <div className="filter-notice">
                  <Filter size={16} />
                  Showing {countryNames[country]} in event and market analytics. Pipeline health
                  counts cover the whole workspace.
                  <button onClick={() => setCountry('all')}>
                    Clear filter <X size={14} />
                  </button>
                </div>
              )}
              {page === 'overview' && (
                <Overview data={data} navigate={navigate} simulate={simulate} inspect={inspect} />
              )}{' '}
              {page === 'events' && (
                <Events
                  data={data}
                  country={country}
                  inspect={inspect}
                  simulate={simulate}
                  notify={notify}
                />
              )}{' '}
              {page === 'quality' && (
                <Quality
                  data={data}
                  review={(row) => setModal({ type: 'review', record: row })}
                  simulate={simulate}
                  inspect={inspect}
                />
              )}{' '}
              {page === 'pipeline' && (
                <Pipeline data={data} mutate={mutate} busy={busy} simulate={simulate} />
              )}{' '}
              {page === 'markets' && <Markets data={data} country={country} />}{' '}
              {page === 'products' && <Products data={data} country={country} />}
            </>
          )}
          <footer className="workspace-footer">
            <span>
              <span className="status-dot" />
              Synthetic data · Original processing engine
            </span>
            <span>
              Designed & engineered by{' '}
              <a href="/">
                Alloyce Amos <ArrowUpRight size={13} />
              </a>
            </span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className={`toast ${toast.tone}`} role="status">
          {toast.tone === 'error' ? <AlertTriangle size={19} /> : <Check size={19} />}
          <span>{toast.message}</span>
          <button aria-label="Dismiss notification" onClick={() => setToast(null)}>
            <X size={16} />
          </button>
        </div>
      )}
      {modal?.type === 'simulate' && (
        <Modal
          title="Change the signal."
          kicker="SCENARIO LAB"
          close={() => !busy && setModal(null)}
          wide
        >
          <p className="modal-intro">
            Choose an input condition. Your batch lands in bronze first; run the pipeline to see how
            it is handled.
          </p>
          <div className="scenario-grid">
            {scenarioOptions.map((item) => (
              <button
                className={`scenario ${scenario === item.id ? 'selected' : ''}`}
                key={item.id}
                aria-pressed={scenario === item.id}
                onClick={() => setScenario(item.id)}
              >
                <span className={`scenario-icon ${item.color}`}>
                  <item.icon size={23} />
                </span>
                <strong>{item.title}</strong>
                <p>{item.description}</p>
                {scenario === item.id && <Check className="scenario-check" size={17} />}
              </button>
            ))}
          </div>
          <div className="batch-control">
            <label htmlFor="batch-size">
              Batch size <strong>{batch} deliveries</strong>
            </label>
            <input
              id="batch-size"
              type="range"
              min="5"
              max="50"
              step="5"
              value={batch}
              onChange={(event) => setBatch(Number(event.target.value))}
            />
            <div>
              <span>5 events</span>
              <span>50 events</span>
            </div>
          </div>
          <div className="modal-actions">
            <span>
              <ShieldCheck size={17} />
              Synthetic records, isolated to your session.
            </span>
            <Button
              busy={busy}
              onClick={async () => {
                const result = await mutate(
                  '/simulate',
                  { scenario, count: batch },
                  `${batch} deliveries staged. Run the pipeline to process them.`,
                );
                if (result) navigate('pipeline');
              }}
            >
              <Radio size={17} />
              Stage events
            </Button>
          </div>
        </Modal>
      )}
      {modal?.type === 'review' && (
        <Modal
          title="A correction you can verify."
          kicker="HUMAN REVIEW"
          close={() => !busy && setModal(null)}
        >
          <Badge tone="amber">{title(modal.record.rule)}</Badge>
          <p className="modal-intro">
            {modal.record.correction?.description} This uses the saved original value from the
            synthetic source.
          </p>
          <div className="correction">
            <span className="eyebrow">{modal.record.correction?.field}</span>
            <div>
              <small>RECEIVED</small>
              <code>{String(modal.record.correction?.before)}</code>
            </div>
            <ArrowDownToLine size={20} />
            <div className="after">
              <small>PROPOSED CORRECTION</small>
              <code>{String(modal.record.correction?.after)}</code>
            </div>
          </div>
          <p className="review-note">
            <Fingerprint size={19} />
            Approval revalidates and loads the corrected record. The original delivery and an audit
            event remain available.
          </p>
          <div className="modal-actions">
            <Button secondary disabled={busy} onClick={() => setModal(null)}>
              Keep in quarantine
            </Button>
            <Button
              busy={busy}
              onClick={() =>
                mutate(
                  `/quarantine/${modal.record.id}/replay`,
                  { decision: 'approve' },
                  'Correction approved, revalidated, and published. The audit trail has been updated.',
                )
              }
            >
              <Check size={17} />
              Approve replay
            </Button>
          </div>
        </Modal>
      )}
      {modal?.type === 'event' && (
        <EventModal detail={modal.detail} close={() => setModal(null)} inspectRelated={inspect} />
      )}
      {modal?.type === 'demo' && (
        <Modal title="Follow the signal." kicker="FINPULSE · THE WALKTHROUGH" close={() => setModal(null)} wide>
          <video className="demo-player" controls playsInline preload="metadata" poster={`${import.meta.env.BASE_URL}demo/poster.jpg`}>
            <source src={`${import.meta.env.BASE_URL}demo/finpulse-demo.mp4`} type="video/mp4" />
            <track kind="captions" src={`${import.meta.env.BASE_URL}demo/finpulse-demo.vtt`} srcLang="en" label="English" default />
          </video>
          <p className="demo-description">A real session through event generation, validation, human-approved replay and reusable data products. Synthetic data · AI-generated narration · English captions.</p>
        </Modal>
      )}
      {modal?.type === 'reset' && (
        <Modal
          title="Start a fresh exploration?"
          kicker="YOUR SANDBOX"
          close={() => !busy && setModal(null)}
        >
          <p className="modal-intro">
            This replaces your sample events, runs and review history with a new starter dataset.
            Other visitors keep their workspaces.
          </p>
          <div className="modal-actions">
            <Button secondary onClick={() => setModal(null)}>
              Keep exploring
            </Button>
            <Button
              busy={busy}
              onClick={() =>
                mutate('/reset', {}, 'Your sample workspace is ready for a fresh exploration.')
              }
            >
              <RotateCcw size={17} />
              Reset my workspace
            </Button>
          </div>
        </Modal>
      )}
      {modal?.type === 'search' && (
        <Modal
          title="Where would you like to go?"
          kicker="QUICK NAVIGATION"
          close={() => setModal(null)}
        >
          <label className="search-field command-search">
            <Search size={19} />
            <input
              autoFocus
              placeholder="Search sections…"
              aria-label="Search sections"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="command-results">
            {sections
              .filter((item) =>
                `${item.name} ${item.caption}`.toLowerCase().includes(search.toLowerCase()),
              )
              .map((item) => (
                <button key={item.id} onClick={() => navigate(item.id)}>
                  <item.icon size={21} />
                  <span>
                    <strong>{item.name}</strong>
                    <small>{item.caption}</small>
                  </span>
                  <ArrowRight size={17} />
                </button>
              ))}
          </div>
        </Modal>
      )}
      {modal?.type === 'guide' && (
        <Modal
          title="A few minutes. A complete data journey."
          kicker="WELCOME TO FINPULSE"
          close={() => setModal(null)}
        >
          <p className="modal-intro">
            This is a working demonstration of Alloyce’s credit data platform, using fictional
            records in your own session.
          </p>
          <ol className="guide-steps">
            <li>
              <strong>Generate a scenario.</strong>
              <p>
                Choose an everyday batch, duplicate delivery, quality incident, or late arrival.
              </p>
            </li>
            <li>
              <strong>Run the pipeline.</strong>
              <p>
                Inspect the real contract checks, validation, deduplication and warehouse loading.
              </p>
            </li>
            <li>
              <strong>Review the exception.</strong>
              <p>Approve a known correction in the Quality lab and follow its audit trace.</p>
            </li>
            <li>
              <strong>Explore the result.</strong>
              <p>
                Compare markets, inspect data products and export the underlying sample records.
              </p>
            </li>
          </ol>
          <div className="modal-actions">
            <a
              className="button secondary"
              href="https://github.com/AmosAlloyce/FinPulse"
              target="_blank"
              rel="noreferrer"
            >
              View the source <ArrowUpRight size={16} />
            </a>
            <Button onClick={() => simulate()}>
              Start a scenario <ArrowRight size={16} />
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
