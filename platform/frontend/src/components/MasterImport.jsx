import { useState } from "react";
import { App, Alert, Button, List, Modal, Progress, Tag, Upload } from "antd";
import { CloudUploadOutlined, InboxOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { num } from "../lib/format";
import { useAuth } from "../context/AuthContext";

const COPY = {
  locomotives: {
    button: "Impor master lokomotif",
    title: "Impor master lokomotif",
    hint: 'Berkas ekspor SAP berisi kolom "Equipment" dan "No. K A I" — biasanya 00 Loco.xlsx.',
    note: "Baris dicocokkan pada nomor Equipment, jadi mengunggah ulang memperbarui data yang ada, bukan menggandakannya.",
    multiple: false,
  },
  components: {
    button: "Impor katalog komponen",
    title: "Impor katalog komponen",
    hint: "Satu berkas per jenis komponen. Beberapa berkas bisa diunggah sekaligus.",
    // Nama berkas menentukan pengelompokan, jadi perlu disebut eksplisit —
    // pengguna yang menamai ulang berkasnya akan mengubah nama jenis komponen.
    note: "Nama berkas dipakai sebagai nama jenis komponen. Mengunggah ulang berkas dengan nama sama akan menimpa isinya.",
    multiple: true,
  },
};

/** Impor master lewat unggahan berkas.
 *
 *  Sengaja tidak membaca folder di server: dengan begini aplikasi bisa
 *  dijalankan di mana saja tanpa menyiapkan direktori data lebih dulu. */
export default function MasterImport({ target, onDone, type = "default", block = false }) {
  const copy = COPY[target];
  const { message } = App.useApp();
  const { can } = useAuth();

  const [open, setOpen] = useState(false);
  const [queue, setQueue] = useState(null);
  const [results, setResults] = useState([]);
  const [running, setRunning] = useState(false);

  if (!can("supervisor")) return null;

  const reset = () => {
    setQueue(null);
    setResults([]);
  };

  /** Diproses satu per satu supaya progres terbaca dan satu berkas gagal
   *  tidak menghentikan sisanya. */
  const run = async (files) => {
    setRunning(true);
    setResults([]);

    const collected = [];

    for (let index = 0; index < files.length; index += 1) {
      setQueue({ current: index + 1, total: files.length, name: files[index].name });

      try {
        const summary = await api.masterUpload(target, files[index]);
        collected.push({ ok: true, name: files[index].name, summary });
      } catch (exception) {
        collected.push({ ok: false, name: files[index].name, error: exception.message });
      }

      setResults([...collected]);
    }

    setQueue(null);
    setRunning(false);

    const failed = collected.filter((item) => !item.ok).length;
    const rows = collected.reduce((sum, item) => sum + (item.summary?.rows || 0), 0);

    if (failed) {
      message.warning(`${collected.length - failed} berhasil, ${failed} gagal`);
    } else {
      message.success(`${num(rows)} baris master diimpor`);
    }

    onDone?.();
  };

  const accept = (fileList) => {
    const files = Array.from(fileList).filter((file) => /\.(xlsx|xlsm)$/i.test(file.name));

    if (!files.length) {
      message.error("Hanya menerima berkas .xlsx atau .xlsm");
      return;
    }

    run(copy.multiple ? files : files.slice(0, 1));
  };

  return (
    <>
      <Button
        type={type}
        block={block}
        icon={<CloudUploadOutlined />}
        onClick={() => {
          reset();
          setOpen(true);
        }}
      >
        {copy.button}
      </Button>

      <Modal
        open={open}
        title={copy.title}
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
          multiple={copy.multiple}
          accept=".xlsx,.xlsm"
          showUploadList={false}
          disabled={running}
          beforeUpload={(file, fileList) => {
            // beforeUpload dipanggil sekali per berkas; kumpulkan di berkas
            // terakhir supaya seluruh pilihan diproses dalam satu antrean.
            if (file === fileList[fileList.length - 1]) accept(fileList);
            return Upload.LIST_IGNORE;
          }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined style={{ color: "var(--brand)" }} />
          </p>
          <p className="ant-upload-text">
            {copy.multiple ? "Letakkan berkas di sini" : "Letakkan satu berkas di sini"}
          </p>
          <p className="ant-upload-hint">{copy.hint}</p>
        </Upload.Dragger>

        <Alert
          type="info"
          showIcon
          style={{ marginTop: 12 }}
          message={copy.note}
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
                    <b>{item.name}</b> — {num(item.summary.rows)} baris
                    {item.summary.group ? ` · ${item.summary.group}` : ""}
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
