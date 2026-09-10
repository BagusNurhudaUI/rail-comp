import { useState } from "react";
import { Alert, App, Button, List, Modal, Progress, Tag, Upload } from "antd";
import { CloudUploadOutlined, InboxOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { num } from "../lib/format";
import { useAuth } from "../context/AuthContext";

/** Impor berkas Excel perawatan lewat unggahan.
 *
 *  Diletakkan di halaman Perawatan, bukan di Pengaturan: impor adalah cara
 *  data itu masuk, jadi tempatnya di sebelah data yang dihasilkannya. */
export default function MaintenanceImport({ onDone, type = "primary" }) {
  const { message } = App.useApp();
  const { can } = useAuth();

  const [open, setOpen] = useState(false);
  const [queue, setQueue] = useState(null);
  const [results, setResults] = useState([]);
  const [running, setRunning] = useState(false);

  if (!can("supervisor")) return null;

  /** Berkas diproses satu per satu supaya progres terbaca dan satu berkas
   *  gagal tidak menghentikan sisanya. */
  const run = async (files) => {
    setRunning(true);
    setResults([]);

    const collected = [];

    for (let index = 0; index < files.length; index += 1) {
      setQueue({ current: index + 1, total: files.length, name: files[index].name });

      try {
        const summary = await api.upload(files[index]);
        collected.push({ ok: true, name: files[index].name, summary });
      } catch (exception) {
        collected.push({ ok: false, name: files[index].name, error: exception.message });
      }

      setResults([...collected]);
    }

    setQueue(null);
    setRunning(false);

    const failed = collected.filter((item) => !item.ok).length;
    const events = collected.reduce((sum, item) => sum + (item.summary?.events || 0), 0);

    if (failed) {
      message.warning(`${collected.length - failed} berhasil, ${failed} gagal`);
    } else {
      message.success(`${num(events)} catatan perawatan diimpor`);
    }

    onDone?.();
  };

  const accept = (fileList) => {
    const files = Array.from(fileList).filter((file) => /\.(xlsx|xlsm)$/i.test(file.name));

    if (!files.length) {
      message.error("Hanya menerima berkas .xlsx atau .xlsm");
      return;
    }

    run(files);
  };

  return (
    <>
      <Button
        type={type}
        icon={<CloudUploadOutlined />}
        onClick={() => {
          setResults([]);
          setQueue(null);
          setOpen(true);
        }}
      >
        Impor data perawatan
      </Button>

      <Modal
        open={open}
        title="Impor data perawatan"
        width={560}
        onCancel={() => !running && setOpen(false)}
        maskClosable={!running}
        footer={
          <Button onClick={() => setOpen(false)} disabled={running}>
            {results.length ? "Tutup" : "Batal"}
          </Button>
        }
      >
        <Upload.Dragger
          multiple
          accept=".xlsx,.xlsm"
          showUploadList={false}
          disabled={running}
          beforeUpload={(file, fileList) => {
            // beforeUpload dipanggil sekali per berkas; kumpulkan di berkas
            // terakhir supaya seluruh pilihan masuk satu antrean.
            if (file === fileList[fileList.length - 1]) accept(fileList);
            return Upload.LIST_IGNORE;
          }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined style={{ color: "var(--brand)" }} />
          </p>
          <p className="ant-upload-text">Letakkan berkas di sini</p>
          <p className="ant-upload-hint">
            Bisa beberapa berkas sekaligus — format &ldquo;Daftar Nomor Equipment Lokomotif
            &lt;tahun&gt;.xlsx&rdquo;
          </p>
        </Upload.Dragger>

        <Alert
          type="info"
          showIcon
          style={{ marginTop: 12 }}
          message="Berkas yang sudah pernah diimpor akan ditulis ulang, bukan digandakan. Block template tanpa nomor lokomotif otomatis dibuang."
        />

        {running && queue && (
          <div style={{ marginTop: 14 }}>
            <Progress
              percent={Math.round(((queue.current - 1) / queue.total) * 100)}
              status="active"
              strokeColor="var(--brand)"
            />
            <p style={{ color: "var(--ink-3)", fontSize: 12.5, margin: 0 }}>
              Memproses berkas {queue.current} dari {queue.total}: <b>{queue.name}</b>
            </p>
          </div>
        )}

        {results.length > 0 && (
          <List
            style={{ marginTop: 14, maxHeight: 260, overflowY: "auto" }}
            size="small"
            dataSource={results}
            renderItem={(item) => (
              <List.Item>
                {item.ok ? (
                  <span style={{ fontSize: 12.8 }}>
                    <Tag color="green">OK</Tag>
                    <b>{item.name}</b> — {num(item.summary.events)} perawatan,{" "}
                    {num(item.summary.components)} komponen, {num(item.summary.templates)} block
                    template dibuang
                  </span>
                ) : (
                  <span style={{ fontSize: 12.8 }}>
                    <Tag color="red">Gagal</Tag>
                    <b>{item.name}</b> — {item.error}
                  </span>
                )}
              </List.Item>
            )}
          />
        )}
      </Modal>
    </>
  );
}
