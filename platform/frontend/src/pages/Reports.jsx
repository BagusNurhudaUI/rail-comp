import { Card, Col, Row, Table, Tag } from "antd";

import { api } from "../lib/api";
import { useFetch } from "../hooks/useQuery";
import { loco, num, text } from "../lib/format";
import { DATA_COLORS } from "../theme";
import { GroupedBar } from "../components/charts";
import { PageHead, StatusTag, Widget } from "../components/ui";

/** Persentase kelengkapan diberi warna ambang supaya kolom yang bermasalah
 *  langsung terlihat tanpa harus membandingkan angka satu per satu. */
function PercentTag({ value }) {
  const number = Number(value || 0);
  const color = number >= 95 ? "green" : number >= 60 ? "gold" : "red";

  return <Tag color={color}>{number}%</Tag>;
}

export default function Reports() {
  const availability = useFetch(() => api.availability(), []);
  const anomalies = useFetch(() => api.anomalies(), []);
  const top = useFetch(() => api.topComponents({ limit: 15 }), []);

  const perYear = availability.data?.per_tahun || [];
  const dateSource = availability.data?.sumber_tanggal || [];

  return (
    <>
      <PageHead
        title="Laporan"
        subtitle="Cakupan data, kelengkapan metadata, dan anomali hasil parsing"
      />

      <Row gutter={[14, 14]}>
        <Col xs={24} xl={12}>
          <Widget title="Cakupan data per tahun">
            <GroupedBar
              data={perYear.map((row) => ({ ...row, label: row.source_year }))}
              series={[
                { key: "events", name: "Block terpakai", color: DATA_COLORS[0] },
                { key: "blocks_template", name: "Block template", color: DATA_COLORS[2] },
              ]}
              height={280}
            />
          </Widget>
        </Col>

        <Col xs={24} xl={12}>
          <Widget title="Asal tanggal perawatan">
            <GroupedBar
              data={dateSource.map((row) => ({ ...row, label: row.tahun }))}
              series={[
                { key: "masuk_excel", name: "Dari Excel", color: DATA_COLORS[0] },
                { key: "masuk_estimasi", name: "Dari program bulan", color: DATA_COLORS[2] },
                { key: "keluar_kosong", name: "Keluar kosong", color: DATA_COLORS[5] },
              ]}
              height={280}
            />
          </Widget>
        </Col>
      </Row>

      <Card title="Availability worksheet" style={{ marginTop: 14 }} styles={{ body: { padding: 16 } }}>
        <Table
          rowKey="source_year"
          size="middle"
          pagination={false}
          loading={availability.loading}
          dataSource={perYear}
          columns={[
            { title: "Tahun", dataIndex: "source_year", render: (value) => <b>{text(value)}</b> },
            { title: "Sheet", dataIndex: "sheets", align: "right", render: num },
            { title: "Sheet OK", dataIndex: "sheets_ok", align: "right", render: num },
            { title: "Block", dataIndex: "blocks", align: "right", render: num },
            {
              title: "Template (dibuang)",
              dataIndex: "blocks_template",
              align: "right",
              render: (value) => <Tag color="gold">{num(value)}</Tag>,
            },
            {
              title: "Perawatan",
              dataIndex: "events",
              align: "right",
              render: (value) => <b className="tabular">{num(value)}</b>,
            },
            { title: "Komponen", dataIndex: "komponen", align: "right", render: num },
          ]}
        />
      </Card>

      <Card title="Kelengkapan metadata" style={{ marginTop: 14 }} styles={{ body: { padding: 16 } }}>
        <Table
          rowKey="tahun"
          size="middle"
          pagination={false}
          loading={availability.loading}
          dataSource={availability.data?.kelengkapan || []}
          columns={[
            { title: "Tahun", dataIndex: "tahun", render: (value) => <b>{text(value)}</b> },
            { title: "Perawatan", dataIndex: "events", align: "right", render: num },
            { title: "Dipo", dataIndex: "dipo", render: (value) => <PercentTag value={value} /> },
            { title: "Jenis", dataIndex: "jenis", render: (value) => <PercentTag value={value} /> },
            { title: "Program bulan", dataIndex: "program", render: (value) => <PercentTag value={value} /> },
            { title: "Masuk", dataIndex: "masuk", render: (value) => <PercentTag value={value} /> },
            { title: "Keluar", dataIndex: "keluar", render: (value) => <PercentTag value={value} /> },
          ]}
        />
      </Card>

      <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
        <Col xs={24} xl={12}>
          <Card title="Komponen paling sering dicatat" styles={{ body: { padding: 16 } }}>
            <Table
              rowKey="label"
              size="small"
              loading={top.loading}
              pagination={{ pageSize: 10, size: "small", hideOnSinglePage: true }}
              dataSource={top.data?.items || []}
              columns={[
                { title: "Komponen", dataIndex: "label", render: (value) => <b>{text(value)}</b> },
                { title: "Baris", dataIndex: "total", align: "right", render: num },
                { title: "Lokomotif", dataIndex: "lokomotif", align: "right", render: num },
                { title: "Ada pengganti", dataIndex: "diganti", align: "right", render: num },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title="Anomali data" styles={{ body: { padding: 16 } }}>
            <div className="section-label" style={{ marginTop: 0 }}>
              Dipo tidak dikenal ({anomalies.data?.dipo_tidak_dikenal?.length || 0})
            </div>

            <Table
              rowKey="id"
              size="small"
              loading={anomalies.loading}
              pagination={false}
              locale={{ emptyText: "Tidak ada" }}
              dataSource={anomalies.data?.dipo_tidak_dikenal || []}
              columns={[
                { title: "Lokomotif", dataIndex: "lokomotif_no", render: loco },
                {
                  title: "Dipo",
                  dataIndex: "dipo_induk",
                  render: (value) => <Tag color="red">{text(value)}</Tag>,
                },
                { title: "Jenis", dataIndex: "jenis_perawatan", render: text },
                {
                  title: "Sumber",
                  dataIndex: "source_sheet",
                  render: (value, row) => (
                    <span className="cell-sub">
                      {text(value)} · blok {row.block_index}
                    </span>
                  ),
                },
              ]}
            />

            <div className="section-label">
              Sheet tanpa data ({availability.data?.sheet_bermasalah?.length || 0})
            </div>

            <Table
              rowKey={(row) => `${row.source_file}-${row.source_sheet}`}
              size="small"
              loading={availability.loading}
              pagination={{ pageSize: 6, size: "small", hideOnSinglePage: true }}
              dataSource={availability.data?.sheet_bermasalah || []}
              columns={[
                { title: "Tahun", dataIndex: "source_year", width: 70, render: text },
                { title: "Sheet", dataIndex: "source_sheet", render: text },
                {
                  title: "Status",
                  dataIndex: "status",
                  render: (value) => <StatusTag value={value} />,
                },
                {
                  title: "Keterangan",
                  dataIndex: "message",
                  render: (value) => <span className="muted">{text(value)}</span>,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </>
  );
}
