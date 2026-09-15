import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Col, Empty, Row, Segmented, Skeleton, Alert } from "antd";
import {
  BlockOutlined,
  CheckCircleOutlined,
  DeploymentUnitOutlined,
  PlusCircleOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch } from "../hooks/useQuery";
import { date, fromNow, num } from "../lib/format";
import { DATA_COLORS } from "../theme";
import {
  DonutBreakdown,
  GroupedBar,
  RankedBar,
  TrendArea,
  useChartHeight,
} from "../components/charts";
import { PageHead, Stat, Widget } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const LEVEL_STATUS = { critical: "error", warning: "warning", info: "processing", success: "success" };

export default function Dashboard() {
  const { user } = useAuth();
  const [year, setYear] = useState("");

  // Tinggi grafik mengecil di layar sempit supaya kartu tidak menjulang.
  const tall = useChartHeight(302);
  const mid = useChartHeight(264);
  const donut = useChartHeight(210);

  const filters = useFetch(() => api.filters(), []);
  const summary = useFetch(() => api.summary(year ? { year } : {}), [year]);
  const charts = useFetch(() => api.charts(year ? { year } : {}), [year]);
  const alerts = useFetch(() => api.alerts(), []);
  const activity = useFetch(() => api.activity({ limit: 9 }), []);

  const years = filters.data?.years || [];
  const s = summary.data || {};
  const c = charts.data || {};

  const komposisi = c.status_komponen
    ? [
        { label: "Diganti", value: c.status_komponen.diganti, color: DATA_COLORS[0] },
        { label: "Terpasang", value: c.status_komponen.tetap, color: DATA_COLORS[1] },
        { label: "Pemasangan baru", value: c.status_komponen.baru, color: DATA_COLORS[2] },
        { label: "Catatan", value: c.status_komponen.lainnya, color: DATA_COLORS[5] },
      ]
    : [];

  return (
    <>
      <PageHead
        title="Dashboard"
        subtitle="Ringkasan perawatan lokomotif dan pergerakan komponen"
        extra={
          <Segmented
            value={year}
            onChange={setYear}
            options={[{ label: "Semua tahun", value: "" }, ...years.map((y) => ({ label: y, value: y }))]}
          />
        }
      />

      {summary.error && <Alert type="error" showIcon message={summary.error} style={{ marginBottom: 16 }} />}

      <div className="greeting" style={{ marginBottom: 16 }}>
        <div className="greeting__text">
          <div className="t-title">Halo, {user?.full_name?.split(" ")[0] || "rekan"}</div>
          <p style={{ margin: "4px 0 0", color: "var(--ink-3)", fontSize: 13 }}>
            {num(s.total_event)} catatan perawatan dari {num(s.total_lokomotif)} lokomotif,
            {" "}
            {num(s.total_komponen)} baris komponen tercatat.
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Link to="/lokomotif">
            <Button icon={<DeploymentUnitOutlined />}>Perawatan lokomotif</Button>
          </Link>
          <Link to="/komponen">
            <Button icon={<BlockOutlined />}>Cari komponen</Button>
          </Link>
          <Link to="/laporan">
            <Button type="primary">Laporan data</Button>
          </Link>
        </div>
      </div>

      <Row gutter={[14, 14]}>
        {[
          { icon: <DeploymentUnitOutlined />, label: "Total Lokomotif", value: s.total_lokomotif, hint: `${years.length} tahun data` },
          { icon: <BlockOutlined />, label: "Total Komponen", value: s.total_komponen, hint: "dismantle · refurbish · penambahan" },
          { icon: <CheckCircleOutlined />, label: "Terinstall", value: s.komponen_terinstall, hint: "ada part pengganti (swap + penambahan)" },
          { icon: <ThunderboltOutlined />, label: "Dismantle", value: s.komponen_dismantle, hint: "lama dilepas & diganti" },
          { icon: <SyncOutlined />, label: "Refurbish", value: s.komponen_refurbish, hint: "diperiksa, tetap dipakai" },
          { icon: <PlusCircleOutlined />, label: "Penambahan", value: s.komponen_penambahan, hint: "part baru tanpa gantian" },
          { icon: <SyncOutlined />, label: "Sedang Dirawat", value: s.berjalan, hint: "belum tercatat keluar" },
        ].map((item) => (
          <Col key={item.label} xs={12} md={8} xl={4}>
            <Stat {...item} loading={summary.loading} />
          </Col>
        ))}
      </Row>

      <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
        <Col xs={24} xl={9}>
          <Widget title="Status komponen">
            {charts.loading ? <Skeleton active /> : <DonutBreakdown data={komposisi} height={donut} />}
          </Widget>
        </Col>

        <Col xs={24} xl={15}>
          <Widget title="Perawatan per tahun">
            {charts.loading ? (
              <Skeleton active />
            ) : (
              <GroupedBar
                data={c.per_tahun || []}
                series={[
                  { key: "events", name: "Perawatan", color: DATA_COLORS[0] },
                  { key: "lokomotif", name: "Lokomotif unik", color: DATA_COLORS[1] },
                ]}
                height={tall}
              />
            )}
          </Widget>
        </Col>
      </Row>

      <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
        <Col xs={24} xl={16}>
          <Widget title="Tren perawatan bulanan">
            {charts.loading ? <Skeleton active /> : <TrendArea data={c.per_bulan || []} height={mid} />}
          </Widget>
        </Col>

        <Col xs={24} xl={8}>
          <Widget title="Sebaran dipo induk">
            {charts.loading ? <Skeleton active /> : <RankedBar data={(c.per_dipo || []).slice(0, 8)} height={mid} color={DATA_COLORS[1]} />}
          </Widget>
        </Col>
      </Row>

      <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
        <Col xs={24} xl={12}>
          <Widget title="Komponen paling sering dicatat">
            {charts.loading ? <Skeleton active /> : <RankedBar data={c.top_komponen || []} height={tall} />}
          </Widget>
        </Col>

        <Col xs={24} xl={12}>
          <Widget title="Perlu perhatian" extra={<Link to="/laporan">Laporan</Link>}>
            {alerts.loading ? (
              <Skeleton active />
            ) : alerts.data?.items?.length ? (
              <div>
                {alerts.data.items.slice(0, 7).map((item, index) => (
                  <div className="off-item" key={`${item.title}-${index}`}>
                    <Badge status={LEVEL_STATUS[item.level] || "default"} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="off-item__name">{item.title}</div>
                      <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{item.meta}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Tidak ada temuan" />
            )}
          </Widget>
        </Col>
      </Row>

      <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
        <Col span={24}>
          <Widget title="Aktivitas terbaru" extra={<Link to="/pengaturan">Riwayat import</Link>}>
            {activity.loading ? (
              <Skeleton active />
            ) : (
              (activity.data?.items || []).map((item, index) => (
                <div className="feed-item" key={`${item.at}-${index}`}>
                  <div className="feed-item__time">
                    <b>{date(item.at)}</b>
                    {fromNow(item.at)}
                  </div>
                  <div
                    className="feed-item__dot"
                    style={{
                      background:
                        item.level === "critical"
                          ? "var(--data-5)"
                          : item.level === "warning"
                            ? "var(--data-3)"
                            : "var(--brand)",
                    }}
                  />
                  <div className="feed-item__main">
                    <strong>{item.title}</strong>
                    <span>
                      {item.detail} {item.actor ? `· oleh ${item.actor}` : ""}
                    </span>
                  </div>
                </div>
              ))
            )}
          </Widget>
        </Col>
      </Row>
    </>
  );
}
