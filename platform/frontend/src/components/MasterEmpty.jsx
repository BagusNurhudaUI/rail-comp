import { App, Button, Card, Empty, Typography } from "antd";
import { FolderOpenOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { num } from "../lib/format";
import { useFetch } from "../hooks/useQuery";
import { useAuth } from "../context/AuthContext";
import MasterImport from "./MasterImport";

/** Layar kosong untuk tabel master.
 *
 *  Jalur utamanya unggah berkas. Impor dari folder server hanya ditawarkan
 *  bila foldernya memang ada — pada deployment yang filesystem-nya sementara
 *  folder itu tidak pernah tersedia dan tombolnya akan menyesatkan. */
export default function MasterEmpty({ title, target, onDone }) {
  const { message } = App.useApp();
  const { can } = useAuth();
  const files = useFetch(() => api.masterFiles(), [], { skip: !can("supervisor") });

  const folderReady = files.data?.exists && (files.data?.items?.length || 0) > 0;

  const importFromFolder = async () => {
    const key = "master-folder";
    message.open({ key, type: "loading", content: "Membaca folder component/…", duration: 0 });

    try {
      const result = await api.masterImport();
      message.open({
        key,
        type: "success",
        content: `${num(result.locomotives)} lokomotif dan ${num(result.components)} komponen diimpor`,
      });
      onDone?.();
    } catch (exception) {
      message.open({ key, type: "error", content: exception.message });
    }
  };

  return (
    <Card>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div style={{ maxWidth: 460, margin: "0 auto" }}>
            <div className="t-title" style={{ marginBottom: 6 }}>
              {title}
            </div>

            <Typography.Paragraph type="secondary" style={{ fontSize: 13 }}>
              Unggah berkas ekspor SAP untuk mengisinya. Berkas diproses langsung di
              peramban ini — tidak perlu menyiapkan folder apa pun di server.
            </Typography.Paragraph>

            <div
              style={{
                display: "flex",
                gap: 8,
                justifyContent: "center",
                flexWrap: "wrap",
                marginTop: 16,
              }}
            >
              <MasterImport target={target} type="primary" onDone={onDone} />

              {folderReady && (
                <Button icon={<FolderOpenOutlined />} onClick={importFromFolder}>
                  Impor dari folder server ({files.data.items.length} berkas)
                </Button>
              )}
            </div>
          </div>
        }
      />
    </Card>
  );
}
