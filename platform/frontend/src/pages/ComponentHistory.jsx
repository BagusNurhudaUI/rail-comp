import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, App, Button, Card, Col, Dropdown, Empty, Input, Row, Space, Table } from "antd";
import { DownOutlined, FileExcelOutlined, FilePdfOutlined, SearchOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch } from "../hooks/useQuery";
import { date, loco, text } from "../lib/format";
import { downloadHistoryPdf } from "../lib/historyPdf";
import { DATA_COLORS } from "../theme";
import { GroupedBar } from "../components/charts";
import { PageHead, Stat, StatusTag, Widget } from "../components/ui";

/** Menelusuri satu nomor equipment: di lokomotif mana saja pernah dipakai
 *  dan kapan berpindah. */
export default function ComponentHistory() {
  const [params, setParams] = useSearchParams();

  // Kode yang sedang ditelusuri disimpan di URL; kotak input hanya menyimpan
  // ketikan sementara sampai pengguna menekan Telusuri.
  const term = params.get("code") || "";
  const [code, setCode] = useState(term);

  const { data, loading, error } = useFetch(() => api.componentHistory(term), [term], {
    skip: !term,
  });

  const { message } = App.useApp();
  const [downloading, setDownloading] = useState(false);

  const trace = () => {
    const next = code.trim();

    if (next) setParams({ code: next });
  };

  const exportExcel = async (layout) => {
    setDownloading(true);

    try {
      const response = await api.exportComponentHistory(term, layout);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = `riwayat_${term}_${layout}.xlsx`;
      link.click();
      URL.revokeObjectURL(url);

      message.success("Excel diunduh");
    } catch (exception) {
      message.error(exception.message);
    } finally {
      setDownloading(false);
    }
  };

  const exportPdf = async () => {
    setDownloading(true);

    try {
      await downloadHistoryPdf(term, data);
      message.success("PDF diunduh");
    } catch (exception) {
      message.error(exception.message);
    } finally {
      setDownloading(false);
    }
  };

  const exportMenu = (
    <Space>
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
          Excel <DownOutlined />
        </Button>
      </Dropdown>

      <Button icon={<FilePdfOutlined />} loading={downloading} size="small" onClick={exportPdf}>
        PDF
      </Button>
    </Space>
  );

  const perYear = useMemo(() => {
    const counts = {};

    (data?.items || []).forEach((item) => {
      const key = item.tahun_maintenance ?? "—";
      counts[key] = (counts[key] || 0) + 1;
    });

    return Object.entries(counts).map(([label, value]) => ({ label, value }));
  }, [data]);

  // Sel kode yang cocok dengan kode yang sedang dilacak disorot di kolom mana pun.
  const target = String(term ?? "").trim().toUpperCase();
  const codeCell = (value) => {
    if (!value) return <span className="muted">—</span>;

    const hit = String(value).trim().toUpperCase() === target;
    return <span className={hit ? "mono code-hit" : "mono"}>{value}</span>;
  };

  return (
    <>
      <PageHead
        title="Riwayat Komponen"
        subtitle="Lacak satu kode cetak atau nomor manufaktur melintasi tahun dan lokomotif"
      />

      <Card styles={{ body: { padding: 16 } }} style={{ marginBottom: 14 }}>
        <div className="filters" style={{ marginBottom: 0 }}>
          <Input
            allowClear
            value={code}
            onChange={(event) => setCode(event.target.value)}
            onPressEnter={trace}
            prefix={<SearchOutlined style={{ color: "var(--ink-3)" }} />}
            placeholder="Contoh: MD-1151907 atau TC-1400600"
            style={{ width: 340 }}
          />
          <Button type="primary" loading={loading} onClick={trace}>
            Telusuri
          </Button>
        </div>
      </Card>

      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 14 }} />}

      {!data && !loading && (
        <Card>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="Masukkan kode equipment untuk melihat perpindahannya antar lokomotif"
          />
        </Card>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <Empty description={`Kode "${data.code}" tidak ditemukan di database`} />
        </Card>
      )}

      {data && data.items.length > 0 && (
        <>
          <Row gutter={[14, 14]}>
            <Col xs={12} md={6}>
              <Stat label="Kemunculan" value={data.total} hint="baris tercatat" />
            </Col>
            <Col xs={12} md={6}>
              <Stat label="Lokomotif" value={data.lokomotif.length} hint="unit berbeda" />
            </Col>
            <Col xs={12} md={6}>
              <Stat label="Tahun pertama" value={data.items[0]?.tahun_maintenance} />
            </Col>
            <Col xs={12} md={6}>
              <Stat
                label="Tahun terakhir"
                value={data.items[data.items.length - 1]?.tahun_maintenance}
              />
            </Col>
          </Row>

          <Row gutter={[14, 14]} style={{ marginTop: 14 }}>
            <Col span={24}>
              <Widget title="Sebaran kemunculan per tahun">
                <GroupedBar
                  data={perYear}
                  series={[{ key: "value", name: "Kemunculan", color: DATA_COLORS[0] }]}
                  height={210}
                />
              </Widget>
            </Col>
          </Row>

          <Card
            style={{ marginTop: 14 }}
            styles={{ body: { padding: 16 } }}
            title="Jejak lengkap"
            extra={exportMenu}
          >
            <Table
              rowKey="id"
              size="middle"
              dataSource={data.items}
              scroll={{ x: 1480 }}
              pagination={{ pageSize: 25, showSizeChanger: true }}
              columns={[
                { title: "Tahun", dataIndex: "tahun_maintenance", width: 72, render: text },
                {
                  title: "Lokomotif",
                  dataIndex: "lokomotif_no",
                  width: 128,
                  render: (value) => <span className="mono">{loco(value)}</span>,
                },
                { title: "Komponen", dataIndex: "component_name", width: 170, render: text },
                {
                  title: "Peran",
                  dataIndex: "peran",
                  width: 104,
                  render: (value) => <StatusTag value={value} />,
                },
                {
                  title: "Asal (No KAI)",
                  dataIndex: "asal_kode_cetak",
                  width: 132,
                  render: (value) => codeCell(value),
                },
                {
                  title: "Asal (Serial Number)",
                  dataIndex: "asal_no_manuf",
                  width: 148,
                  render: (value) => codeCell(value),
                },
                {
                  title: "Pengganti (No KAI)",
                  dataIndex: "pengganti_kode_cetak",
                  width: 148,
                  render: (value) => codeCell(value),
                },
                {
                  title: "Pengganti (Serial Number)",
                  dataIndex: "pengganti_no_manuf",
                  width: 164,
                  render: (value) => codeCell(value),
                },
                {
                  title: "Jenis Perawatan",
                  dataIndex: "jenis_perawatan",
                  width: 118,
                  render: text,
                },
                { title: "Masuk", dataIndex: "masuk", width: 116, render: date },
                { title: "Keluar", dataIndex: "keluar", width: 116, render: date },
                {
                  title: "Sumber",
                  dataIndex: "source_file",
                  render: (value, row) => (
                    <span className="cell-sub">
                      {text(value)}
                      <br />
                      {text(row.source_sheet)} · blok {row.block_index}
                    </span>
                  ),
                },
              ]}
            />
          </Card>
        </>
      )}
    </>
  );
}
