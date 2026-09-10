import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Card, Drawer, Input, Select, Table, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch, usePagedQuery } from "../hooks/useQuery";
import { date, dateTime, duration, num, text } from "../lib/format";
import {
  Cell,
  KeyValue,
  PageHead,
  SectionLabel,
  StatusTag,
  useDrawerWidth,
} from "../components/ui";
import MaintenanceImport from "../components/MaintenanceImport";

/** Satu baris = satu catatan perawatan. Halaman yang sama melayani rute
 *  /lokomotif (menonjolkan lokomotifnya) dan /perawatan (menonjolkan
 *  kunjungannya) — datanya identik, penekanan kolomnya yang berbeda. */
export default function MaintenancePage({ variant = "lokomotif" }) {
  const [params, setParams] = useSearchParams();
  const [detailId, setDetailId] = useState(null);

  // Drawer riwayat lokomotif dikendalikan lewat URL supaya tautan dari
  // pencarian global bisa langsung membukanya, dan tombol back menutupnya.
  const locoKey = params.get("loco");

  const setLocoKey = (key) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);

      if (key) next.set("loco", key);
      else next.delete("loco");

      return next;
    });

  const filterOptions = useFetch(() => api.filters(), []);
  const importHistory = useFetch(() => api.importHistory(), [], { skip: variant !== "perawatan" });
  const query = usePagedQuery(api.maintenance, {
    search: params.get("search") || "",
    dipo: "",
    jenis: "",
    year: "",
    status: "",
  });

  const options = filterOptions.data || { dipo: [], jenis_perawatan: [], years: [] };
  const isPerawatan = variant === "perawatan";

  const columns = [
    {
      title: "Lokomotif",
      dataIndex: "lokomotif_no",
      width: 168,
      render: (value, row) => (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            setLocoKey(row.lokomotif_key);
          }}
          style={{
            border: 0,
            background: "none",
            padding: 0,
            cursor: "pointer",
            textAlign: "left",
            color: "var(--brand-ink)",
            fontWeight: 600,
          }}
        >
          {text(value)}
          <div className="cell-sub">lihat riwayat</div>
        </button>
      ),
    },
    { title: "Tahun", dataIndex: "tahun_maintenance", width: 82, render: text },
    { title: "Dipo", dataIndex: "dipo_induk", width: 86, render: text, responsive: ["md"] },
    {
      title: "Jenis",
      dataIndex: "jenis_perawatan",
      width: 116,
      responsive: ["lg"],
      render: (value) => (value ? <Tag>{value}</Tag> : "—"),
    },
    {
      title: "Masuk",
      dataIndex: "masuk",
      width: 148,
      render: (value, row) => (
        <span>
          {date(value)}
          {row.masuk_source === "program_bulan" && (
            <Tag color="gold" style={{ marginLeft: 6 }}>
              est
            </Tag>
          )}
        </span>
      ),
    },
    { title: "Keluar", dataIndex: "keluar", width: 116, render: date, responsive: ["sm"] },
    {
      title: "Durasi",
      dataIndex: "durasi_hari",
      width: 96,
      align: "right",
      responsive: ["lg"],
      render: (value) => (value === null ? "—" : `${num(value)} hari`),
    },
    {
      title: "Komponen",
      dataIndex: "component_count",
      width: 100,
      align: "right",
      responsive: ["md"],
      render: (value) => <span className="tabular cell-strong">{num(value)}</span>,
    },
    {
      title: "Status",
      dataIndex: "status",
      width: 104,
      render: (value) => <StatusTag value={value} />,
    },
    {
      title: "Sumber",
      dataIndex: "source_sheet",
      width: 190,
      responsive: ["xl"],
      render: (value, row) =>
        isPerawatan ? (
          <Cell main={text(row.source_file)} sub={`${text(value)} · blok ${row.block_index}`} />
        ) : (
          <span className="cell-sub">
            {text(value)} · blok {row.block_index}
          </span>
        ),
    },
  ];

  return (
    <>
      <PageHead
        title={isPerawatan ? "Perawatan" : "Lokomotif"}
        subtitle={
          isPerawatan
            ? "Setiap baris adalah satu kunjungan perawatan, lengkap dengan file sumbernya"
            : "Setiap baris adalah satu catatan perawatan; klik nomor lokomotif untuk riwayatnya"
        }
        extra={
          <>
            <Tag color="green" style={{ alignSelf: "center" }}>
              {num(query.total)} perawatan
            </Tag>
            {isPerawatan && (
              <MaintenanceImport
                onDone={() => {
                  query.reload();
                  importHistory.refetch();
                  filterOptions.refetch();
                }}
              />
            )}
          </>
        }
      />

      {query.error && <Alert type="error" showIcon message={query.error} style={{ marginBottom: 14 }} />}

      <Card styles={{ body: { padding: 16 } }}>
        <div className="filters">
          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: "var(--ink-3)" }} />}
            placeholder="Cari nomor lokomotif atau sheet…"
            style={{ width: 268 }}
            defaultValue={query.filters.search}
            onChange={(event) => query.setFilter("search", event.target.value)}
          />

          <Select
            allowClear
            placeholder="Semua dipo"
            style={{ width: 140 }}
            options={options.dipo.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("dipo", value || "")}
          />

          <Select
            allowClear
            placeholder="Semua jenis"
            style={{ width: 150 }}
            options={options.jenis_perawatan.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("jenis", value || "")}
          />

          <Select
            allowClear
            placeholder="Semua tahun"
            style={{ width: 132 }}
            options={options.years.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("year", value || "")}
          />

          <Select
            allowClear
            placeholder="Semua status"
            style={{ width: 158 }}
            options={[
              { value: "berjalan", label: "Berjalan" },
              { value: "selesai", label: "Selesai" },
              ...(isPerawatan ? [{ value: "estimasi", label: "Tanggal estimasi" }] : []),
            ]}
            onChange={(value) => query.setFilter("status", value || "")}
          />
        </div>

        <Table
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={query.items}
          loading={query.loading}
          scroll={{ x: 1180 }}
          onRow={(row) => ({
            className: "row-link",
            onClick: () => setDetailId(row.id),
          })}
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

      {isPerawatan && (
        <Card
          title="Riwayat impor"
          style={{ marginTop: 14 }}
          styles={{ body: { padding: 16 } }}
        >
          <Table
            rowKey="id"
            size="small"
            loading={importHistory.loading}
            scroll={{ x: 940 }}
            pagination={{ pageSize: 10, size: "small" }}
            locale={{ emptyText: "Belum ada berkas yang diimpor" }}
            dataSource={importHistory.data?.items || []}
            columns={[
              {
                title: "Berkas",
                dataIndex: "source_file",
                render: (value) => <b style={{ fontSize: 12.8 }}>{text(value)}</b>,
              },
              {
                title: "Mulai",
                dataIndex: "started_at",
                width: 176,
                responsive: ["lg"],
                render: (value) => <span className="mono">{dateTime(value)}</span>,
              },
              {
                title: "Durasi",
                key: "durasi",
                width: 96,
                render: (_, row) => (
                  <span className="muted">{duration(row.started_at, row.finished_at)}</span>
                ),
              },
              {
                title: "Perawatan",
                dataIndex: "event_count",
                align: "right",
                width: 96,
                render: num,
              },
              {
                title: "Komponen",
                dataIndex: "component_count",
                align: "right",
                width: 96,
                responsive: ["md"],
                render: num,
              },
              {
                title: "Status",
                dataIndex: "status",
                width: 104,
                render: (value) => <StatusTag value={value} />,
              },
              {
                title: "Pesan",
                dataIndex: "error_message",
                responsive: ["xl"],
                render: (value) => <span className="cell-sub">{text(value)}</span>,
              },
            ]}
          />
        </Card>
      )}

      <MaintenanceDrawer id={detailId} onClose={() => setDetailId(null)} />
      <LocomotiveDrawer locoKey={locoKey} onClose={() => setLocoKey(null)} />
    </>
  );
}

function MaintenanceDrawer({ id, onClose }) {
  const width = useDrawerWidth(720);
  const { data, loading } = useFetch(() => api.maintenanceDetail(id), [id], { skip: !id });

  const event = data?.event || {};

  return (
    <Drawer
      open={Boolean(id)}
      onClose={onClose}
      width={width}
      title={event.lokomotif_no || "Detail perawatan"}
      loading={loading}
    >
      <KeyValue
        items={[
          ["No. seri (mentah)", <span className="mono">{text(event.no_seri_lokomotif)}</span>],
          ["Dipo induk", text(event.dipo_induk)],
          ["Jenis perawatan", text(event.jenis_perawatan)],
          [
            "Masuk",
            <>
              {date(event.masuk)}
              {event.masuk_source === "program_bulan" && <Tag color="gold" style={{ marginLeft: 6 }}>estimasi</Tag>}
            </>,
          ],
          [
            "Keluar",
            <>
              {date(event.keluar)}
              {event.keluar_source === "program_bulan" && <Tag color="gold" style={{ marginLeft: 6 }}>estimasi</Tag>}
            </>,
          ],
          ["Program bulan", text(event.program_bulan)],
          ["Tahun maintenance", text(event.tahun_maintenance)],
          ["File sumber", <span className="mono">{text(event.source_file)}</span>],
          ["Sheet / blok", <span className="mono">{text(event.source_sheet)} · blok {text(event.block_index)}</span>],
        ]}
      />

      <SectionLabel>Daftar komponen ({data?.components?.length || 0})</SectionLabel>

      <Table
        rowKey="id"
        size="small"
        dataSource={data?.components || []}
        pagination={{ pageSize: 20, size: "small", hideOnSinglePage: true }}
        columns={[
          { title: "No", dataIndex: "component_no", width: 56, render: text },
          { title: "Nama", dataIndex: "component_name", render: (value) => <b>{text(value)}</b> },
          {
            title: "Asal",
            dataIndex: "asal_kode_cetak",
            render: (value, row) => <Cell main={<span className="mono">{text(value)}</span>} sub={row.asal_no_manuf} />,
          },
          {
            title: "Pengganti",
            dataIndex: "pengganti_kode_cetak",
            render: (value, row) => (
              <Cell main={<span className="mono">{text(value)}</span>} sub={row.pengganti_no_manuf} />
            ),
          },
          { title: "Ket.", dataIndex: "keterangan", render: (value) => <span className="muted">{text(value)}</span> },
        ]}
      />
    </Drawer>
  );
}

function LocomotiveDrawer({ locoKey, onClose }) {
  const width = useDrawerWidth(720);
  const { data, loading } = useFetch(() => api.locomotive(locoKey), [locoKey], {
    skip: !locoKey,
  });

  const header = data?.header || {};

  return (
    <Drawer
      open={Boolean(locoKey)}
      onClose={onClose}
      width={width}
      title={header.lokomotif_no || "Riwayat lokomotif"}
      loading={loading}
    >
      <KeyValue
        items={[
          ["Total perawatan", num(header.total_perawatan)],
          ["Total komponen", num(header.total_komponen)],
          ["Pertama masuk", date(header.pertama_masuk)],
          ["Terakhir masuk", date(header.terakhir_masuk)],
        ]}
      />

      <SectionLabel>Komponen paling sering diganti</SectionLabel>

      <Table
        rowKey="label"
        size="small"
        pagination={false}
        dataSource={(data?.komponen_teratas || []).slice(0, 10)}
        columns={[
          { title: "Komponen", dataIndex: "label", render: (value) => <b>{text(value)}</b> },
          { title: "Jumlah", dataIndex: "value", align: "right", width: 90, render: num },
        ]}
      />

      <SectionLabel>Riwayat perawatan</SectionLabel>

      <Table
        rowKey="id"
        size="small"
        dataSource={data?.riwayat || []}
        pagination={{ pageSize: 10, size: "small", hideOnSinglePage: true }}
        columns={[
          { title: "Tahun", dataIndex: "tahun_maintenance", width: 70, render: text },
          { title: "Dipo", dataIndex: "dipo_induk", width: 76, render: text },
          { title: "Jenis", dataIndex: "jenis_perawatan", width: 96, render: text },
          { title: "Masuk", dataIndex: "masuk", render: date },
          { title: "Keluar", dataIndex: "keluar", render: date },
          { title: "Komp.", dataIndex: "component_count", align: "right", width: 74, render: num },
        ]}
      />
    </Drawer>
  );
}
