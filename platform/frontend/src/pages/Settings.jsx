import { useState } from "react";
import { Alert, App, Button, Card, Col, Form, Input, Modal, Row, Select, Tag } from "antd";

import { api } from "../lib/api";
import { useFetch } from "../hooks/useQuery";
import { dateTime, num, text } from "../lib/format";
import { KeyValue, PageHead } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const SCOPES = [
  {
    value: "all",
    label: "Semua data",
    detail: "Perawatan, komponen, master lokomotif, katalog komponen, dan seluruh catatan log.",
  },
  {
    value: "maintenance",
    label: "Data perawatan saja",
    detail: "Perawatan, komponen, dan availability worksheet. Master data tidak tersentuh.",
  },
  {
    value: "master",
    label: "Master data saja",
    detail: "Master lokomotif dan katalog komponen. Data perawatan tidak tersentuh.",
  },
];

export default function Settings() {
  const { message } = App.useApp();
  const { can } = useAuth();

  const health = useFetch(() => api.health(), []);

  const [flushOpen, setFlushOpen] = useState(false);
  const [scope, setScope] = useState("all");
  const [confirm, setConfirm] = useState("");
  const [flushing, setFlushing] = useState(false);

  const isAdmin = can("admin");
  const h = health.data || { tables: {} };
  const activeScope = SCOPES.find((item) => item.value === scope);

  const runFlush = async () => {
    setFlushing(true);

    try {
      const result = await api.flush({ confirm: confirm.trim(), scope });

      message.success(`${num(result.total)} baris dihapus dari ${result.scope_label}`);
      setFlushOpen(false);
      setConfirm("");
      health.refetch();
    } catch (exception) {
      message.error(exception.message);
    } finally {
      setFlushing(false);
    }
  };

  const changePassword = async (values, form) => {
    try {
      await api.changePassword(values.current_password, values.new_password);
      message.success("Password diperbarui");
      form.resetFields();
    } catch (exception) {
      message.error(exception.message);
    }
  };

  const [passwordForm] = Form.useForm();

  return (
    <>
      <PageHead
        title="Pengaturan"
        subtitle="Status sistem, akun, dan pemeliharaan data"
      />

      {h.code_stale && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 14 }}
          message="Server menjalankan kode lama"
          description={`Berkas backend terakhir diubah ${dateTime(h.code_modified_at)}, sedangkan proses server berjalan sejak ${dateTime(h.server_started_at)}. Hentikan server (Ctrl+C) lalu jalankan run.bat lagi.`}
        />
      )}

      <Row gutter={[14, 14]}>
        <Col xs={24} lg={14}>
          <Card title="Status sistem" styles={{ body: { padding: 16 } }}>
            <KeyValue
              items={[
                ["Aplikasi", `${text(h.app)} v${text(h.version)}`],
                [
                  "Database",
                  <span className="mono" style={{ wordBreak: "break-all" }}>
                    {text(h.database)}
                  </span>,
                ],
                ["Perawatan", num(h.tables?.maintenance_events)],
                ["Komponen perawatan", num(h.tables?.equipment_components)],
                ["Worksheet terscan", num(h.tables?.sheet_availability)],
                ["Pengguna", num(h.tables?.app_users)],
                ["Server sejak", dateTime(h.server_started_at)],
                [
                  "Kode diubah",
                  <>
                    {dateTime(h.code_modified_at)}{" "}
                    <Tag color={h.code_stale ? "red" : "green"}>
                      {h.code_stale ? "perlu restart" : "terbaru"}
                    </Tag>
                  </>,
                ],
              ]}
            />

            <Alert
              type="info"
              showIcon
              style={{ marginTop: 16 }}
              message="Impor data kini ada di halamannya masing-masing"
              description="Berkas perawatan diimpor dari halaman Perawatan, master lokomotif dan katalog komponen dari halaman Master Data."
            />
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card title="Ubah password" styles={{ body: { padding: 16 } }}>
            <Form
              form={passwordForm}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => changePassword(values, passwordForm)}
            >
              <Form.Item
                name="current_password"
                label="Password saat ini"
                rules={[{ required: true, message: "Wajib diisi" }]}
              >
                <Input.Password autoComplete="current-password" />
              </Form.Item>

              <Form.Item
                name="new_password"
                label="Password baru"
                rules={[{ required: true, min: 6, message: "Minimal 6 karakter" }]}
              >
                <Input.Password autoComplete="new-password" />
              </Form.Item>

              <Button htmlType="submit" block>
                Simpan password
              </Button>
            </Form>
          </Card>

          {isAdmin && (
            <Card
              title={<span style={{ color: "var(--danger)" }}>Kosongkan data</span>}
              style={{ marginTop: 14, borderColor: "#e7c9c4" }}
              styles={{ body: { padding: 16 } }}
            >
              <p style={{ color: "var(--ink-3)", fontSize: 12.8, lineHeight: 1.6, marginTop: 0 }}>
                Menghapus isi tabel data supaya bisa diimpor ulang dari awal.
                <b> Akun pengguna tidak pernah ikut terhapus.</b>
              </p>

              <Select
                style={{ width: "100%", marginBottom: 8 }}
                value={scope}
                onChange={setScope}
                options={SCOPES.map(({ value, label }) => ({ value, label }))}
              />

              <p style={{ color: "var(--ink-3)", fontSize: 12, marginTop: 0, marginBottom: 12 }}>
                {activeScope.detail}
              </p>

              <Button danger block onClick={() => setFlushOpen(true)}>
                Kosongkan data
              </Button>
            </Card>
          )}
        </Col>
      </Row>

      <Modal
        open={flushOpen}
        title="Kosongkan data"
        okText="Ya, kosongkan"
        okButtonProps={{ danger: true, disabled: confirm.trim() !== "HAPUS" }}
        confirmLoading={flushing}
        cancelText="Batal"
        onOk={runFlush}
        onCancel={() => setFlushOpen(false)}
      >
        <p style={{ lineHeight: 1.6 }}>
          Target: <b>{activeScope.label}</b>. {activeScope.detail} Tindakan ini tidak bisa
          dibatalkan.
        </p>

        <Alert
          type="info"
          showIcon
          style={{ margin: "12px 0" }}
          message="Akun pengguna tetap disimpan, jadi Anda tidak akan terkunci dari aplikasi."
        />

        <label style={{ fontSize: 12.5, fontWeight: 600 }}>
          Ketik <b>HAPUS</b> untuk konfirmasi
        </label>
        <Input
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          placeholder="HAPUS"
          style={{ marginTop: 6 }}
        />
      </Modal>
    </>
  );
}
