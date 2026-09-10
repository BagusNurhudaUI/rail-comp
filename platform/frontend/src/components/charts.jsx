import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Empty, Grid } from "antd";

import { DATA_COLORS } from "../theme";
import { num, percent, shorten } from "../lib/format";

const AXIS = { stroke: "var(--line)", tick: { fill: "var(--ink-3)", fontSize: 11 } };

const TOOLTIP_STYLE = {
  contentStyle: {
    borderRadius: 8,
    border: "1px solid var(--line)",
    boxShadow: "0 6px 24px rgb(22 33 28 / 10%)",
    fontSize: 12.5,
  },
  labelStyle: { color: "var(--ink-3)", fontSize: 11.5, marginBottom: 4 },
};

/** Grafik dipersingkat di layar kecil supaya kartu tidak mendorong isi
 *  lain jauh ke bawah lipatan. */
export function useChartHeight(desktop) {
  const screens = Grid.useBreakpoint();

  if (!screens.sm) return Math.round(desktop * 0.72);
  if (!screens.lg) return Math.round(desktop * 0.86);

  return desktop;
}

function NoData({ height = 220 }) {
  return (
    <div style={{ height, display: "grid", placeItems: "center" }}>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Belum ada data" />
    </div>
  );
}

/** Batang horizontal — pilihan tepat saat labelnya panjang, karena teks
 *  tetap terbaca mendatar alih-alih dimiringkan. */
export function RankedBar({ data, height = 300, color = DATA_COLORS[0], nameKey = "label" }) {
  if (!data?.length) return <NoData height={height} />;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 28, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke="var(--line)" />
        <XAxis type="number" {...AXIS} tickFormatter={num} />
        <YAxis
          type="category"
          dataKey={nameKey}
          width={148}
          {...AXIS}
          tickFormatter={(value) => shorten(value, 20)}
        />
        <Tooltip {...TOOLTIP_STYLE} formatter={(value) => [num(value), "Jumlah"]} cursor={{ fill: "var(--surface-2)" }} />
        <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Batang berkelompok untuk membandingkan dua-tiga seri per periode. */
export function GroupedBar({ data, series, height = 280, xKey = "label" }) {
  if (!data?.length) return <NoData height={height} />;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="var(--line)" />
        <XAxis dataKey={xKey} {...AXIS} />
        <YAxis {...AXIS} tickFormatter={num} width={46} />
        <Tooltip {...TOOLTIP_STYLE} formatter={(value) => num(value)} cursor={{ fill: "var(--surface-2)" }} />
        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 6 }} iconType="circle" iconSize={8} />
        {series.map((serie, index) => (
          <Bar
            key={serie.key}
            dataKey={serie.key}
            name={serie.name}
            fill={serie.color || DATA_COLORS[index % DATA_COLORS.length]}
            radius={[3, 3, 0, 0]}
            maxBarSize={26}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Tren waktu. Area diberi gradien tipis agar arah tren terbaca tanpa
 *  menutupi garis grid. */
export function TrendArea({ data, height = 250, xKey = "label", color = DATA_COLORS[0] }) {
  if (!data?.length) return <NoData height={height} />;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 4 }}>
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.26} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="var(--line)" />
        <XAxis dataKey={xKey} {...AXIS} minTickGap={22} />
        <YAxis {...AXIS} tickFormatter={num} width={46} />
        <Tooltip {...TOOLTIP_STYLE} formatter={(value) => [num(value), "Perawatan"]} />
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill="url(#trendFill)"
          dot={{ r: 2.5, strokeWidth: 2, fill: "#fff" }}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Donat + legenda bernilai. Persentase ditulis eksplisit karena mata
 *  buruk dalam membandingkan sudut. */
export function DonutBreakdown({ data, height = 210 }) {
  const rows = (data || []).filter((item) => Number(item.value) > 0);

  if (!rows.length) return <NoData height={height} />;

  const total = rows.reduce((sum, item) => sum + Number(item.value), 0);

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={rows}
            dataKey="value"
            nameKey="label"
            innerRadius="58%"
            outerRadius="86%"
            paddingAngle={1.5}
            stroke="none"
          >
            {rows.map((item, index) => (
              <Cell key={item.label} fill={item.color || DATA_COLORS[index % DATA_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(value, name) => [`${num(value)} (${percent(value, total)})`, name]}
          />
        </PieChart>
      </ResponsiveContainer>

      <div style={{ marginTop: 8 }}>
        <div className="legend legend--total">
          <span className="legend__label" style={{ fontWeight: 600, color: "var(--ink)" }}>
            Total
          </span>
          <span className="legend__value">{num(total)}</span>
          <span className="legend__pct">100%</span>
        </div>

        {rows.map((item, index) => (
          <div className="legend" key={item.label}>
            <span
              className="legend__swatch"
              style={{ background: item.color || DATA_COLORS[index % DATA_COLORS.length] }}
            />
            <span className="legend__label">{item.label}</span>
            <span className="legend__value">{num(item.value)}</span>
            <span className="legend__pct">{percent(item.value, total)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Bar bertumpuk satu baris — komposisi ringkas tanpa memakan tinggi kartu. */
export function StackedShare({ data }) {
  const rows = (data || []).filter((item) => Number(item.value) > 0);
  const total = rows.reduce((sum, item) => sum + Number(item.value), 0);

  if (!total) return <NoData height={80} />;

  return (
    <div>
      <div className="stacked-bar">
        {rows.map((item, index) => (
          <div
            key={item.label}
            title={`${item.label}: ${num(item.value)}`}
            style={{
              width: `${(item.value / total) * 100}%`,
              background: item.color || DATA_COLORS[index % DATA_COLORS.length],
            }}
          />
        ))}
      </div>

      {rows.map((item, index) => (
        <div className="legend" key={item.label}>
          <span
            className="legend__swatch"
            style={{ background: item.color || DATA_COLORS[index % DATA_COLORS.length] }}
          />
          <span className="legend__label">{item.label}</span>
          <span className="legend__value">{num(item.value)}</span>
          <span className="legend__pct">{percent(item.value, total)}</span>
        </div>
      ))}
    </div>
  );
}
