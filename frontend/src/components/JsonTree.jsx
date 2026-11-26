import { useState } from "react";

// Collapsible JSON viewer. Objects/arrays can be folded; empty values are dimmed.

function Value({ value }) {
  if (value === null) return <span className="json-null">null</span>;
  if (typeof value === "string") return <span className="json-string">"{value}"</span>;
  if (typeof value === "number") return <span className="json-number">{value}</span>;
  if (typeof value === "boolean") return <span className="json-boolean">{String(value)}</span>;
  return null;
}

function Node({ name, value, depth }) {
  const isArray = Array.isArray(value);
  const isObject = value !== null && typeof value === "object";
  const [open, setOpen] = useState(depth < 2);

  const label = name !== undefined && <span className="json-key">{name}: </span>;

  if (!isObject) {
    return <div className="json-row">{label}<Value value={value} /></div>;
  }

  const entries = isArray ? value.map((v, i) => [i, v]) : Object.entries(value);
  const [openBr, closeBr] = isArray ? ["[", "]"] : ["{", "}"];

  if (entries.length === 0) {
    return <div className="json-row">{label}<span className="json-null">{openBr}{closeBr}</span></div>;
  }

  return (
    <div className="json-node">
      <div className="json-row json-toggle" onClick={() => setOpen(!open)}>
        <span className="json-caret">{open ? "▾" : "▸"}</span>
        {label}
        {open ? openBr : <span className="json-summary">{openBr} {entries.length} {isArray ? "items" : "fields"} {closeBr}</span>}
      </div>
      {open && (
        <div className="json-children">
          {entries.map(([k, v]) => <Node key={k} name={k} value={v} depth={depth + 1} />)}
          <div className="json-row">{closeBr}</div>
        </div>
      )}
    </div>
  );
}

export default function JsonTree({ data }) {
  return <div className="json-tree"><Node value={data} depth={0} /></div>;
}
