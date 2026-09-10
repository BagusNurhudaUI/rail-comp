import { useMemo, useState } from "react";
import { App, Button, Col, Dropdown, Empty, Grid, Modal, Row, Spin, Table } from "antd";
import { DownOutlined, FileExcelOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch } from "../hooks/useQuery";
import { date, text } from "../lib/format";
import { DATA_COLORS } from "../theme";
import { GroupedBar } from "./charts";
import { Stat, StatusTag, Widget } from "./ui";

/** Dialog besar berisi riwayat servis satu kode komponen — isi yang sama dengan
 *  halaman Riwayat Komponen, tapi muncul sebagai modal supaya bisa dibuka dari
 *  mana saja (mis. daftar komponen di detail perawatan) tanpa pindah halaman.
 *
 *  Menerima `code` (kode cetak / no. manuf). Modal terbuka selama `code` terisi. */
export default function ComponentHistoryDialog({ code, onClose }) {
  const screens = Grid.useBreakpoint();
  const width = !screens.sm ? "100%" : !screens.lg ? "94%" : 1040;
  const { message } = App.useApp();
  const [downloading, setDownloading] = useState(false);

  const { data, loading, error } = useFetch(
    () => api.componentHistory(code),
    [code],
    { skip: !code },
  );

  const exportExcel = async (layout) => {
    setDownloading(true);

    try {
      const response = await api.exportComponentHistory(code, layout);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = `riwayat_${code}_${layout}.xlsx`;
      link.click();
      URL.revokeObjectURL(url);

      message.success("Excel diunduh");
    } catch (exception) {
      message.error(exception.message);
    } finally {
      setDownloading(false);
    }
  };

  const perYear = useMemo(() => {
    const counts = {};

    (data?.items || []).forEach((item) => {
      const key = item.tahun_maintenance ?? "—";
      counts[key] = (counts[key] || 0) + 1;
    });

    return Object.entries(counts).map(([label, value]) => ({ label, value }));
  }, [data]);

  const items = data?.items || [];

  // Sel kode yang cocok dengan kode yang sedang dilacak disorot, di kolom mana
  // pun ia berada — jadi terlihat jelas di baris mana komponen ini muncul dan
  // apakah ia sebagai asal (dilepas) atau pengganti (dipasang).
  const norm = (value) => String(value ?? "").trim().toUpperCase();
  const target = norm(code);

  const codeCell = (value) => {
    if (!value) return <span className="muted">—</span>;

    const hit = norm(value) === target;
    return <span className={hit ? "mono code-hit" : "mono"}>{value}</span>;
  };

  return (
    <Modal
      open={Boolean(code)}
      onCancel={onClose}
      footer={null}
      width={width}
      style={{ top: 24 }}
      title={
        <span>
          Riwayat servis komponen{" "}
          <span className="mono" style={{ color: "var(--brand-ink)" }}>
            {text(code)}
          </span>
        </span>
      }
    >
      {loading && (
        <div style={{ padding: 48, textAlign: "center" }}>
          <Spin />
        </div>
      )}

      {!loading && error && (
        <Empty description={error} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}

      {!loading && !error && items.length === 0 && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={`Kode ${text(code)} belum pernah tercatat pada perawatan`}
        />
      )}

      {!loading && !error && items.length > 0 && (
        <>
          <Row gutter={[12, 12]}>
            <Col xs={12} md={6}>
              <Stat label="Kemunculan" value={data.total} hint="baris tercatat" />
            </Col>
            <Col xs={12} md={6}>
              <Stat label="Lokomotif" value={data.lokomotif.length} hint="unit berbeda" />
            </Col>
            <Col xs={12} md={6}>
              <Stat label="Tahun pertama" value={items[0]?.tahun_maintenance} />
            </Col>
            <Col xs={12} md={6}>
              <Stat label="Tahun terakhir" value={items[items.length - 1]?.tahun_maintenance} />
            </Col>
          </Row>

          <div style={{ marginTop: 14 }}>
            <Widget title="Sebaran kemunculan per tahun">
              <GroupedBar
                data={perYear}
                series={[{ key: "value", name: "Kemunculan", color: DATA_COLORS[0] }]}
                height={200}
              />
            </Widget>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              margin: "20px 0 10px",
            }}
          >
            <span className="section-label" style={{ margin: 0 }}>
              Jejak lengkap
            </span>

            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  { key: "table", label: "Tabel lengkap" },
                  { key: "wide", label: "Ringkas (per komponen, melebar)" },
                ],
                onClick: ({ key }) => exportExcel(key),
              }}
            >
              <Button icon={<FileExcelOutlined />} loading={downloading} size="small">
                Export Excel <DownOutlined />
              </Button>
            </Dropdown>
          </div>

          <Table
            rowKey="id"
            size="small"
            dataSource={items}
            scroll={{ x: 980 }}
            pagination={{ pageSize: 15, showSizeChanger: true, size: "small" }}
            columns={[
              { title: "Tahun", dataIndex: "tahun_maintenance", width: 74, render: text },
              { title: "Lokomotif", dataIndex: "lokomotif_no", width: 132, render: text },
              {
                title: "Komponen",
                dataIndex: "component_name",
                width: 170,
                responsive: ["md"],
                render: text,
              },
              {
                title: "Peran",
                dataIndex: "peran",
                width: 104,
                render: (value) => <StatusTag value={value} />,
              },
              {
                title: "Asal",
                dataIndex: "asal_kode_cetak",
                width: 140,
                render: codeCell,
              },
              {
                title: "Pengganti",
                dataIndex: "pengganti_kode_cetak",
                width: 140,
                render: codeCell,
              },
              { title: "Masuk", dataIndex: "masuk", width: 112, responsive: ["md"], render: date },
              { title: "Keluar", dataIndex: "keluar", width: 112, responsive: ["lg"], render: date },
              {
                title: "Sumber",
                dataIndex: "source_sheet",
                responsive: ["xl"],
                render: (value, row) => (
                  <span className="cell-sub">
                    {text(value)} · blok {row.block_index}
                  </span>
                ),
              },
            ]}
          />
        </>
      )}
    </Modal>
  );
}
