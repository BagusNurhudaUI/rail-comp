import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, App, Button, Card, Input, Select, Table, Tag } from "antd";
import { DownloadOutlined, SearchOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch, usePagedQuery } from "../hooks/useQuery";
import { num, text } from "../lib/format";
import { Cell, PageHead, StatusTag } from "../components/ui";

export default function ComponentsPage() {
  const [exporting, setExporting] = useState(false);
  const { message } = App.useApp();
  const navigate = useNavigate();

  const filterOptions = useFetch(() => api.filters(), []);
  const query = usePagedQuery(api.components, {
    search: "",
    name: "",
    year: "",
    status: "",
  });

  const options = filterOptions.data || { years: [], component_names: [] };

  const exportCsv = async () => {
    setExporting(true);

    try {
      const response = await api.exportComponents(query.filters);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = "equipment_components.csv";
      link.click();
      URL.revokeObjectURL(url);

      message.success("Export CSV diunduh");
    } catch (exception) {
      message.error(exception.message);
    } finally {
      setExporting(false);
    }
  };

  const columns = [
    {
      title: "Komponen",
      dataIndex: "component_name",
      width: 200,
      render: (value, row) => <Cell main={text(value)} sub={`No. ${text(row.component_no)}`} />,
    },
    { title: "Lokomotif", dataIndex: "lokomotif_no", width: 140, render: text, responsive: ["sm"] },
    {
      title: "Asal",
      dataIndex: "asal_kode_cetak",
      width: 168,
      render: (value, row) => (
        <Cell main={<span className="mono">{text(value)}</span>} sub={row.asal_no_manuf} />
      ),
    },
    {
      title: "Pengganti",
      dataIndex: "pengganti_kode_cetak",
      width: 168,
      responsive: ["md"],
      render: (value, row) => (
        <Cell main={<span className="mono">{text(value)}</span>} sub={row.pengganti_no_manuf} />
      ),
    },
    { title: "Tahun", dataIndex: "tahun_maintenance", width: 78, render: text, responsive: ["md"] },
    {
      title: "Status",
      dataIndex: "status",
      width: 140,
      render: (value) => <StatusTag value={value} />,
    },
    {
      title: "Keterangan",
      dataIndex: "keterangan",
      responsive: ["xl"],
      render: (value) => <span className="muted">{text(value)}</span>,
    },
    {
      title: "Sumber",
      dataIndex: "source_sheet",
      width: 170,
      responsive: ["xl"],
      render: (value, row) => (
        <span className="cell-sub">
          {text(value)} · blok {row.block_index}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHead
        title="Komponen"
        subtitle="Baris detail dari form perawatan; klik baris untuk menelusuri kode equipment-nya"
        extra={
          <>
            <Tag color="green">{num(query.total)} baris</Tag>
            <Button icon={<DownloadOutlined />} loading={exporting} onClick={exportCsv}>
              Export CSV
            </Button>
          </>
        }
      />

      {query.error && <Alert type="error" showIcon message={query.error} style={{ marginBottom: 14 }} />}

      <Card styles={{ body: { padding: 16 } }}>
        <div className="filters">
          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: "var(--ink-3)" }} />}
            placeholder="Cari kode cetak, no. manuf, atau nama…"
            style={{ width: 300 }}
            onChange={(event) => query.setFilter("search", event.target.value)}
          />

          <Select
            allowClear
            showSearch
            placeholder="Semua komponen"
            style={{ width: 220 }}
            options={options.component_names.map((value) => ({ value, label: value }))}
            onChange={(value) => query.setFilter("name", value || "")}
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
            style={{ width: 172 }}
            options={[
              { value: "diganti", label: "Diganti" },
              { value: "baru", label: "Pemasangan baru" },
              { value: "tetap", label: "Terpasang" },
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
          scroll={{ x: 1220 }}
          onRow={(row) => ({
            className: "row-link",
            onClick: () => {
              const code = row.asal_kode_cetak || row.pengganti_kode_cetak;
              if (code) navigate(`/riwayat-komponen?code=${encodeURIComponent(code)}`);
            },
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
    </>
  );
}
