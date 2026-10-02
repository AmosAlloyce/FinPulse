import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, FileJson, Fingerprint, GitBranch } from 'lucide-react';
import { Badge, countryNames, shortId, title } from './components.jsx';
import './signal-lens.css';

export default function SignalLens({ data, inspect, simulate }) {
  const candidates = data.events.slice(0, 8);
  const [selected, setSelected] = useState('');
  const [stage, setStage] = useState(0);
  const ref = useRef(null);
  const event = candidates.find((row) => row.id === selected) || candidates[0];
  useEffect(() => {
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    let frame = 0;
    const read = () => {
      frame = 0;
      if (!ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const progress = motion.matches
        ? 0
        : Math.max(0, Math.min(1, -rect.top / Math.max(rect.height, 1)));
      ref.current.style.setProperty('--lens-scroll', String(progress));
    };
    const update = () => {
      if (!frame) frame = requestAnimationFrame(read);
    };
    addEventListener('scroll', update, { passive: true });
    motion.addEventListener('change', update);
    read();
    return () => {
      removeEventListener('scroll', update);
      motion.removeEventListener('change', update);
      cancelAnimationFrame(frame);
    };
  }, []);
  if (!event) return null;
  const accepted = event.status === 'accepted';
  const details = [
    {
      label: 'Source envelope',
      heading: 'A signal with an origin.',
      description:
        'The original delivery is retained before validation. Its identity stays attached throughout processing.',
      rows: [
        ['Event ID', event.eventId],
        ['Source', title(event.source)],
        ['Market', countryNames[event.countryCode]],
      ],
    },
    {
      label: 'Quality result',
      heading: 'A decision you can inspect.',
      description: accepted
        ? event.late
          ? 'Accepted with a freshness warning. Late input remains usable and its arrival is visible.'
          : 'This delivery passed the event contract and quality gates, including duplicate detection.'
        : 'The pipeline records a disposition for every delivery. Inspect the original to see the issues and any approved correction.',
      rows: [
        ['Disposition', title(event.status)],
        [
          'Freshness',
          event.status === 'pending'
            ? 'Awaiting validation'
            : event.late
              ? 'Late arrival'
              : 'No warning recorded',
        ],
        ['Reported issues', String(event.issues?.length || 0)],
      ],
    },
    {
      label: 'Published output',
      heading: accepted ? 'Ready for a data product.' : 'A visible quality boundary.',
      description: accepted
        ? 'Accepted events feed typed facts and SQL data products. Open the original envelope to inspect its lineage and related events.'
        : 'This delivery has not been published as a new accepted fact. Its raw evidence remains available in the event explorer.',
      rows: [
        ['Customer', event.customerId],
        ['Destination', accepted ? 'Validated event facts' : 'Delivery history'],
        ['Currency', event.currency || 'Not provided in this envelope'],
      ],
    },
  ];
  const current = details[stage];
  return (
    <section className="signal-lens" ref={ref} data-sc-act="flow" aria-label="Follow a real event">
      <div className="lens-intro">
        <span className="lens-label">
          <Fingerprint size={17} /> An event in your workspace
        </span>
        <h2>
          Follow one signal.
          <br />
          See what it becomes.
        </h2>
        <p>Move from the original delivery to its quality result and the data it feeds.</p>
        <button className="lens-create" onClick={simulate}>
          Create a scenario <ArrowUpRight size={17} />
        </button>
      </div>
      <div className="lens-object">
        <div className="lens-backplane" aria-hidden="true" />
        <div className="lens-document">
          <div className="lens-document-head">
            <span>
              <FileJson size={17} /> {shortId(event.eventId)}
            </span>
            <Badge tone={accepted ? 'green' : 'amber'}>{title(event.status)}</Badge>
          </div>
          <label className="lens-select">
            Trace an event
            <select
              aria-label="Trace an event"
              value={event.id}
              onChange={(e) => setSelected(e.target.value)}
            >
              {candidates.map((row) => (
                <option key={row.id} value={row.id}>
                  {shortId(row.eventId)} · {title(row.eventType)}
                </option>
              ))}
            </select>
          </label>
          <div
            className="lens-stages"
            role="group"
            aria-label="Trace stage"
            style={{ '--stage-progress': stage / 2 }}
          >
            {['Source', 'Quality', 'Output'].map((label, index) => (
              <button key={label} aria-pressed={stage === index} onClick={() => setStage(index)}>
                <span />
                {label}
              </button>
            ))}
          </div>
          <div className="lens-detail" aria-live="polite">
            <h3>{current.heading}</h3>
            <p>{current.description}</p>
            <dl>
              {current.rows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value || 'Not provided'}</dd>
                </div>
              ))}
            </dl>
          </div>
          <button className="lens-open" onClick={() => inspect(event)}>
            <GitBranch size={17} />
            Open original event <ArrowUpRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}
