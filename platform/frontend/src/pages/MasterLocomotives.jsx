import { useState } from "react";
import { Alert, Card, Col, Drawer, Input, Row, Select, Table, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch, usePagedQuery } from "../hooks/useQuery";
import { date, num, text } from "../lib/format";
import { DATA_COLORS } from "../theme";
import { RankedBar } from "../components/charts";
import {
  Cell,
  KeyValue,
  PageHead,
  SectionLabel,
  Stat,
  StatusTag,
  useDrawerWidth,
  Widget,
} from "../components/ui";
import MasterEmpty from "../components/MasterEmpty";
import MasterImport from "../components/MasterImport";

export default function MasterLocomotives() {
  const [detail, setDetail] = useState(null);

  const summary = useFetch(() => api.masterSummary(), []);
  const filterOptions = useFetch(() => api.masterFilters(), []);
  const query = usePagedQuery(api.masterLocomotives, { search: "", status: "", dipo: "" });

  const s = summary.data || {};
  const options = filterOptions.data || { loco_status: [], loco_dipo: [] };

  const refreshAll = () => {
    summary.refetch();
    filterOptions.refetch();
    query.reload();
  };

  if (!summary.loading && !s.total_lokomotif) {
    return (
      <MasterEmpty
        title="Master lokomotif belum diimpor"
        target="locomotives"
        onDone={refreshAll}
      />
    );
  }

  const columns = [
    {
      title: "No. KAI",
      dataIndex: "no_kai",
      width: 150,
      render: (value, row) => <Cell main={text(value)} sub={row.manuf_serial_no} />,
    },
    {
      title: "Equipment",
      dataIndex: "equipment",
      width: 116,
      responsive: ["lg"],
      render: (value) => <span className="mono">{text(value)}</span>,
    },
    { title: "Dipo", dataIndex: "functional_loc_desc", width: 230, render: text, responsive: ["md"] },
    {
      title: "Status",
      dataIndex: "system_status",
      width: 104,
      render: (value) => <StatusTag value={value} />,
    },
    { title: "Kapasitas", dataIndex: "kapasitas", width: 100, render: text, responsive: ["xl"] },
    {
      title: "Komponen",
      dataIndex: "komponen_terpasang",
      width: 104,
      align: "right",
      render: (value) => <span className="tabular cell-strong">{num(value)}</span>,
    },
    {
      title: "Perawatan",
      dataIndex: "riwayat_perawatan",
      width: 104,
      align: "right",
      render: (value) => (value ? <Tag color="green">{num(value)}</Tag> : <span className="muted">—</span>),
    },
    { title: "Diubah", dataIndex: "changed_on", width: 120, render: date, responsive: ["xl"] },
  ];

  return (
    <>
      <PageHead
        title="Master Lokomotif"
        subtitle="Data induk lokomotif dari SAP (00 Loco.xlsx)"
        extra={
          <>
            <Tag color="green" style={{ alignSelf: "center" }}>
              {num(query.total)} lokomotif
            </Tag>
            <MasterImport target="locomotives" onDone={refreshAll} />
          </>
        }
      />

      <Row gutter={[14, 14]}>
        <Col xs={12} md={6}>
          <Stat label="Total Lokomotif" value={s.total_lokomotif} hint="dari 00 Loco.xlsx" loading={summary.loading} />
        </Col>
        <Col xs={12} md={6}>
          <Stat label="Komponen Terpasang" value={s.komponen_terpasang_loko} hint="langsung di lokomotif" loading={summary.loading} />
        </Col>
        <Col xs={12} md={6}>
          <Stat label="Jenis Komponen" value={s.jenis_komponen} hint="kategori katalog" loading={summary.loading} />
        </Col>
        <Col xs={12} md={6}>
          <Stat label="Total Katalog" value={s.total_komponen} hint="baris master komponen" loading={summary.loading} />
        </Col>
      </Row>

      <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
        <Col xs={24} xl={12}>
          <Widget title="Sebaran lokomotif per dipo">
            <RankedBar data={s.loco_per_dipo || []} height={300} />
          </Widget>
        </Col>
        <Col xs={24} xl={12}>
          <Widget title="Katalog per jenis komponen">
            <RankedBar data={(s.per_group || []).slice(0, 10)} height={300} color={DATA_COLORS[3]} />
          </Widget>
        </Col>
      </Row>

      {query.error && <Alert type="error" showIcon message={query.error} style={{ margin: "14px 0" }} />}

      <Card style={{ marginTop: 14 }} styles={{ body: { padding: 16 } }}>
        <div className="filters">
          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: "var(--ink-3)" }} />}
            placeholder="Cari no. KAI, equipment, atau seri…"
            style={{ width: 290 }}
            onChange={(event) => query.setFilter("search", event.target.value)}
          />

          <Select
            allowClear
            placeholder="Semua status"
            style={{ width: 150 }}
            options={options.loco_status.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("status", value || "")}
          />

          <Select
            allowClear
            showSearch
            placeholder="Semua dipo"
            style={{ width: 260 }}
            options={options.loco_dipo.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("dipo", value || "")}
          />
        </div>

        <Table
          rowKey="equipment"
          size="middle"
          columns={columns}
          dataSource={query.items}
          loading={query.loading}
          scroll={{ x: 1140 }}
          onRow={(row) => ({ className: "row-link", onClick: () => setDetail(row.equipment) })}
          pagination={{
            current: query.page,
            pageSize: query.pageSize,
            total: query.total,
            showSizeChanger: true,
            showTotal: (total, range) => `${num(range[0])}–${num(range[1])} dari ${num(total)}`,
            onChange: (page, size) => {
              query.setPage(page);
              query.setPageSize(size);
            },
          }}
        />
      </Card>

      <LocoDrawer equipment={detail} onClose={() => setDetail(null)} />
    </>
  );
}

function LocoDrawer({ equipment, onClose }) {
  const width = useDrawerWidth(760);
  const { data, loading } = useFetch(() => api.masterLocomotive(equipment), [equipment], {
    skip: !equipment,
  });

  const loco = data?.locomotive || {};

  return (
    <Drawer
      open={Boolean(equipment)}
      onClose={onClose}
      width={width}
      loading={loading}
      title={loco.no_kai || "Detail lokomotif"}
    >
      <KeyValue
        items={[
          ["Equipment", <span className="mono">{text(loco.equipment)}</span>],
          ["Nomor seri", <span className="mono">{text(loco.manuf_serial_no)}</span>],
          ["Manufaktur", text(loco.manufacturer)],
          ["Status sistem", <StatusTag value={loco.system_status} />],
          ["Kapasitas", text(loco.kapasitas)],
          ["Kritikalitas", text(loco.criticality)],
          ["Dipo / lokasi", text(loco.functional_loc_desc)],
          ["Functional Loc.", <span className="mono">{text(loco.functional_loc)}</span>],
          ["Maint. plant", `${text(loco.maint_plant)} · ${text(loco.planning_plant)}`],
          ["Work center", text(loco.main_work_ctr)],
          ["Diubah", `${date(loco.changed_on)} oleh ${text(loco.changed_by)}`],
        ]}
      />

      <SectionLabel>Komponen terpasang ({data?.komponen?.length || 0})</SectionLabel>

      <Table
        rowKey="id"
        size="small"
        dataSource={data?.komponen || []}
        pagination={{ pageSize: 10, size: "small", hideOnSinglePage: true }}
        columns={[
          { title: "Jenis", dataIndex: "component_group", render: (value) => <b>{text(value)}</b> },
          {
            title: "No. KAI",
            dataIndex: "no_kai",
            render: (value) => <span className="mono">{text(value)}</span>,
          },
          {
            title: "Status",
            dataIndex: "system_status",
            width: 96,
            render: (value) => <StatusTag value={value} />,
          },
          {
            title: "Lokasi",
            dataIndex: "functional_loc_desc",
            render: (value) => <span className="cell-sub">{text(value)}</span>,
          },
        ]}
      />

      <SectionLabel>Riwayat perawatan (dari file perawatan Excel)</SectionLabel>

      <Table
        rowKey="id"
        size="small"
        dataSource={data?.riwayat || []}
        locale={{ emptyText: "Lokomotif ini tidak muncul di file perawatan 2019–2026" }}
        pagination={{ pageSize: 10, size: "small", hideOnSinglePage: true }}
        columns={[
          { title: "Tahun", dataIndex: "tahun_maintenance", width: 72, render: text },
          { title: "Dipo", dataIndex: "dipo_induk", width: 76, render: text },
          { title: "Jenis", dataIndex: "jenis_perawatan", width: 100, render: text },
          { title: "Masuk", dataIndex: "masuk", render: date },
          { title: "Keluar", dataIndex: "keluar", render: date },
          { title: "Komp.", dataIndex: "component_count", align: "right", width: 74, render: num },
        ]}
      />
    </Drawer>
  );
}
