import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AutoComplete, Input, Spin } from "antd";
import { SearchOutlined } from "@ant-design/icons";

import { api } from "../lib/api";

/** Pencarian lintas entitas: lokomotif dan kode komponen sekaligus. */
export default function GlobalSearch() {
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);
  const navigate = useNavigate();

  const search = useMemo(
    () => (term) => {
      clearTimeout(timer.current);

      if (term.trim().length < 2) {
        setOptions([]);
        return;
      }

      timer.current = setTimeout(async () => {
        setLoading(true);

        try {
          const [locos, comps] = await Promise.all([
            api.maintenance({ search: term, page_size: 5 }),
            api.components({ search: term, page_size: 5 }),
          ]);

          const groups = [];

          if (locos.items.length) {
            groups.push({
              label: "Perawatan lokomotif",
              options: locos.items.map((item) => ({
                value: `loco:${item.lokomotif_key}`,
                label: (
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: 600 }}>{item.lokomotif_no}</span>
                    <span style={{ color: "var(--ink-3)", fontSize: 12 }}>
                      {item.tahun_maintenance} · {item.dipo_induk || "—"}
                    </span>
                  </div>
                ),
              })),
            });
          }

          if (comps.items.length) {
            groups.push({
              label: "Kode komponen",
              options: comps.items
                .filter((item) => item.asal_kode_cetak || item.pengganti_kode_cetak)
                .map((item, index) => ({
                  value: `code:${item.asal_kode_cetak || item.pengganti_kode_cetak}:${index}`,
                  label: (
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontWeight: 600 }}>
                        {item.asal_kode_cetak || item.pengganti_kode_cetak}
                      </span>
                      <span style={{ color: "var(--ink-3)", fontSize: 12 }}>
                        {item.component_name}
                      </span>
                    </div>
                  ),
                })),
            });
          }

          setOptions(groups);
        } catch {
          setOptions([]);
        } finally {
          setLoading(false);
        }
      }, 300);
    },
    [],
  );

  const handleSelect = (value) => {
    const [kind, payload] = value.split(":");

    if (kind === "loco") {
      navigate(`/lokomotif?loco=${encodeURIComponent(payload)}`);
    } else {
      navigate(`/riwayat-komponen?code=${encodeURIComponent(payload)}`);
    }

    setOptions([]);
  };

  return (
    <AutoComplete
      options={options}
      onSearch={search}
      onSelect={handleSelect}
      style={{ width: "100%" }}
      popupMatchSelectWidth={420}
      notFoundContent={loading ? <Spin size="small" /> : null}
    >
      <Input
        allowClear
        prefix={<SearchOutlined style={{ color: "var(--ink-3)" }} />}
        placeholder="Cari lokomotif atau kode equipment…"
      />
    </AutoComplete>
  );
}
