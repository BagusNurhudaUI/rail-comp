import { useState } from "react";
import { Alert, Card, Col, Drawer, Input, Row, Select, Table, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch, usePagedQuery } from "../hooks/useQuery";
import { date, loco, num, text } from "../lib/format";
import { DATA_COLORS } from "../theme";
import { DonutBreakdown, RankedBar } from "../components/charts";
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

export default function MasterComponents() {
  const [detail, setDetail] = useState(null);

  const summary = useFetch(() => api.masterSummary(), []);
  const filterOptions = useFetch(() => api.masterFilters(), []);
  const query = usePagedQuery(api.masterComponents, {
    search: "",
    group: "",
    status: "",
    terpasang: "",
  });

  const s = summary.data || {};
  const options = filterOptions.data || { component_groups: [], component_status: [] };

  const refreshAll = () => {
    summary.refetch();
    filterOptions.refetch();
    query.reload();
  };

  if (!summary.loading && !s.total_komponen) {
    return (
      <MasterEmpty
        title="Katalog komponen belum diimpor"
        target="components"
        onDone={refreshAll}
      />
    );
  }

  const columns = [
    {
      title: "No. KAI",
      dataIndex: "no_kai",
      width: 160,
      render: (value) => <span className="mono cell-strong">{text(value)}</span>,
    },
    { title: "Jenis", dataIndex: "component_group", width: 168, render: text, responsive: ["sm"] },
    {
      title: "Equipment",
      dataIndex: "equipment",
      width: 116,
      responsive: ["lg"],
      render: (value) => <span className="mono">{text(value)}</span>,
    },
    {
      title: "Terpasang di",
      dataIndex: "loco_no_kai",
      width: 140,
      responsive: ["md"],
      render: (value, row) =>
        value ? (
          <b>{value}</b>
        ) : (
          <span className="muted mono">{text(row.superord_equipment)}</span>
        ),
    },
    {
      title: "Posisi",
      dataIndex: "posisi_pasang",
      width: 168,
      render: (value) => <StatusTag value={value} />,
    },
    {
      title: "Status",
      dataIndex: "system_status",
      width: 104,
      render: (value) => <StatusTag value={value} />,
    },
    {
      title: "Lokasi",
      dataIndex: "functional_loc_desc",
      responsive: ["xl"],
      render: (value) => <span className="cell-sub">{text(value)}</span>,
    },
  ];

  return (
    <>
      <PageHead
        title="Katalog Komponen"
        subtitle="Master equipment SAP; relasi ke lokomotif bersifat lunak sehingga komponen gudang tetap tercatat"
        extra={
          <>
            <Tag color="green" style={{ alignSelf: "center" }}>
              {num(query.total)} baris
            </Tag>
            <MasterImport target="components" onDone={refreshAll} />
          </>
        }
      />

      <Row gutter={[14, 14]}>
        <Col xs={12} md={6}>
          <Stat label="Total Katalog" value={s.total_komponen} hint={`${s.jenis_komponen || 0} jenis komponen`} loading={summary.loading} />
        </Col>
        <Col xs={12} md={6}>
          <Stat label="Terpasang di Loko" value={s.komponen_terpasang_loko} hint="induknya lokomotif" loading={summary.loading} />
        </Col>
        <Col xs={12} md={6}>
          <Stat label="Terpasang di Rakitan" value={s.komponen_rakitan_lain} hint="induknya komponen lain" loading={summary.loading} />
        </Col>
        <Col xs={12} md={6}>
          <Stat label="Tidak Terpasang" value={s.komponen_tanpa_induk} hint="tanpa induk / di gudang" loading={summary.loading} />
        </Col>
      </Row>

      <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
        <Col xs={24} xl={14}>
          <Widget title="Katalog per jenis komponen">
            <RankedBar data={(s.per_group || []).slice(0, 12)} height={340} />
          </Widget>
        </Col>
        <Col xs={24} xl={10}>
          <Widget title="Status sistem SAP">
            <DonutBreakdown
              data={(s.per_status || []).map((item, index) => ({
                ...item,
                color: DATA_COLORS[index % DATA_COLORS.length],
              }))}
              height={200}
            />
          </Widget>
        </Col>
      </Row>

      {query.error && <Alert type="error" showIcon message={query.error} style={{ margin: "14px 0" }} />}

      <Card style={{ marginTop: 14 }} styles={{ body: { padding: 16 } }}>
        <div className="filters">
          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: "var(--ink-3)" }} />}
            placeholder="Cari no. KAI, equipment, atau serial…"
            style={{ width: 290 }}
            onChange={(event) => query.setFilter("search", event.target.value)}
          />

          <Select
            allowClear
            showSearch
            placeholder="Semua jenis"
            style={{ width: 210 }}
            options={options.component_groups.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("group", value || "")}
          />

          <Select
            allowClear
            placeholder="Semua status"
            style={{ width: 150 }}
            options={options.component_status.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("status", value || "")}
          />

          <Select
            allowClear
            placeholder="Semua posisi"
            style={{ width: 210 }}
            options={[
              { value: "loko", label: "Terpasang di lokomotif" },
              { value: "rakitan", label: "Terpasang di rakitan" },
              { value: "gudang", label: "Tidak terpasang" },
            ]}
            onChange={(value) => query.setFilter("terpasang", value || "")}
          />
        </div>

        <Table
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={query.items}
          loading={query.loading}
          scroll={{ x: 1160 }}
          onRow={(row) => ({ className: "row-link", onClick: () => setDetail(row.id) })}
          pagination={{
            current: query.page,
            pageSize: query.pageSize,
            total: query.total,
            showSizeChanger: true,
            pageSizeOptions: [25, 50, 100],
            showTotal: (total, range) => `${num(range[0])}–${num(range[1])} dari ${num(total)}`,
            onChange: (page, size) => {
              query.setPage(page);
              query.setPageSize(size);
            },
          }}
        />
      </Card>

      <ComponentDrawer id={detail} onClose={() => setDetail(null)} />
    </>
  );
}

/** Kolom non-baku disimpan sebagai JSON; berkas sumber tidak selalu rapi
 *  sehingga isi yang rusak diabaikan alih-alih menggagalkan drawer. */
function parseExtra(raw) {
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function ComponentDrawer({ id, onClose }) {
  const width = useDrawerWidth(760);
  const { data, loading } = useFetch(() => api.masterComponent(id), [id], { skip: !id });

  const component = data?.component || {};

  const extra = parseExtra(component.extra_json);

  const parent = data?.induk;

  return (
    <Drawer
      open={Boolean(id)}
      onClose={onClose}
      width={width}
      loading={loading}
      title={component.no_kai || "Detail komponen"}
    >
      <KeyValue
        items={[
          ["Equipment", <span className="mono">{text(component.equipment)}</span>],
          ["Jenis", text(component.component_group)],
          ["Deskripsi", text(component.description)],
          [
            "Manufaktur",
            `${text(component.manufacturer)}${component.manuf_serial_no ? ` · ${component.manuf_serial_no}` : ""}`,
          ],
          ["Status sistem", <StatusTag value={component.system_status} />],
          ["Kapasitas", text(component.kapasitas)],
          ["Kritikalitas", text(component.criticality)],
          [
            "Induk",
            parent ? (
              <>
                <b>{text(parent.no_kai || parent.equipment)}</b>{" "}
                <span className="muted">{text(parent.description)}</span>
              </>
            ) : component.superord_equipment ? (
              <>
                <span className="mono">{component.superord_equipment}</span>{" "}
                <Tag color="gold">induk tidak ada di master</Tag>
              </>
            ) : (
              <Tag>tidak terpasang</Tag>
            ),
          ],
          ["Lokasi", text(component.functional_loc_desc)],
          ["Functional Loc.", <span className="mono">{text(component.functional_loc)}</span>],
          ["Model", text(component.model_number)],
          ["Diubah", `${date(component.changed_on)} oleh ${text(component.changed_by)}`],
          [
            "Sumber",
            <span className="cell-sub">
              {text(component.source_file)} · baris {text(component.source_row)}
            </span>,
          ],
        ]}
      />

      {extra && (
        <>
          <SectionLabel>Kolom tambahan di berkas sumber</SectionLabel>
          <KeyValue items={Object.entries(extra)} />
        </>
      )}

      <SectionLabel>Riwayat pemakaian (dicocokkan lewat kode cetak)</SectionLabel>

      <Table
        rowKey="id"
        size="small"
        dataSource={data?.riwayat || []}
        locale={{
          emptyText: `Kode ${component.no_kai || "-"} belum pernah tercatat di file perawatan`,
        }}
        pagination={{ pageSize: 10, size: "small", hideOnSinglePage: true }}
        columns={[
          { title: "Tahun", dataIndex: "tahun_maintenance", width: 72, render: text },
          { title: "Lokomotif", dataIndex: "lokomotif_no", width: 130, render: loco },
          {
            title: "Peran",
            dataIndex: "peran",
            width: 100,
            render: (value) => <StatusTag value={value} />,
          },
          { title: "Masuk", dataIndex: "masuk", width: 116, render: date },
          {
            title: "Ket.",
            dataIndex: "keterangan",
            render: (value) => <span className="muted">{text(value)}</span>,
          },
        ]}
      />
    </Drawer>
  );
}
