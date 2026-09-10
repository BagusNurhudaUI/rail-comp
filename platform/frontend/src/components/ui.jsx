import { Grid, Skeleton, Tag } from "antd";

import { num } from "../lib/format";

/** Judul halaman + deskripsi singkat + aksi di kanan. */
export function PageHead({ title, subtitle, extra }) {
  return (
    <div className="page__head">
      <div>
        <h1 className="t-display">{title}</h1>
        {subtitle && <p className="page__sub">{subtitle}</p>}
      </div>
      {extra && <div style={{ display: "flex", gap: 8 }}>{extra}</div>}
    </div>
  );
}

/** Angka utama. Ikon diberi latar hijau lembut, bukan blok warna penuh —
 *  warna kuat disimpan untuk data di grafik. */
export function Stat({ icon, label, value, hint, loading }) {
  return (
    <div className="stat">
      <div className="stat__top">
        {icon && <span className="stat__icon">{icon}</span>}
        <span className="label-xs">{label}</span>
      </div>

      {loading ? (
        <Skeleton.Input active size="small" style={{ width: 90, height: 30 }} />
      ) : (
        <div className="t-figure">{num(value)}</div>
      )}

      {hint && <div className="stat__hint">{hint}</div>}
    </div>
  );
}

/** Kartu grafik dengan tinggi penuh supaya baris grid rata. */
export function Widget({ title, extra, footer, children }) {
  return (
    <div className="widget">
      <div className="widget__head">
        <span className="widget__title">{title}</span>
        {extra}
      </div>
      <div className="widget__body">{children}</div>
      {footer && <div className="widget__foot">{footer}</div>}
    </div>
  );
}

export function KeyValue({ items }) {
  return (
    <dl className="kv-grid">
      {items
        .filter(Boolean)
        .map(([key, value]) => (
          <div key={key} style={{ display: "contents" }}>
            <dt>{key}</dt>
            <dd>{value}</dd>
          </div>
        ))}
    </dl>
  );
}

export function SectionLabel({ children }) {
  return <div className="section-label">{children}</div>;
}

const STATUS_TONE = {
  Selesai: "green",
  Operasional: "green",
  Berjalan: "gold",
  "Dalam perawatan": "gold",
  Diganti: "blue",
  "Pemasangan baru": "purple",
  Terpasang: "default",
  Catatan: "default",
  Dilepas: "gold",
  Dipasang: "green",
  SUCCESS: "green",
  FAILED: "red",
  FLUSHED: "gold",
  OK: "green",
  NO_BLOCK: "default",
  TEMPLATE_ONLY: "gold",
  ERROR: "red",
  INST: "green",
  AVLB: "blue",
  ASEQ: "default",
  "Terpasang di lokomotif": "green",
  "Terpasang di rakitan": "blue",
  "Tidak terpasang": "default",
};

export function StatusTag({ value }) {
  if (!value) return <span className="muted">—</span>;

  return <Tag color={STATUS_TONE[value] || "default"}>{value}</Tag>;
}

/** Sel dua baris: nilai utama + keterangan kecil di bawahnya. */
export function Cell({ main, sub }) {
  return (
    <div>
      <div className="cell-strong">{main}</div>
      {sub && <div className="cell-sub">{sub}</div>}
    </div>
  );
}

/** Drawer detail memuat tabel; di layar sempit ia harus memakai lebar penuh
 *  agar kolomnya tidak langsung terpotong begitu dibuka. */
export function useDrawerWidth(desktop = 720) {
  const screens = Grid.useBreakpoint();

  if (!screens.sm) return "100%";
  if (!screens.lg) return "92%";

  return desktop;
}
