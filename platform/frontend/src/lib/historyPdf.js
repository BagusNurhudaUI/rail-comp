/* Ekspor PDF riwayat servis satu komponen — sekolom dengan ekspor Excel
   (backend), dipakai baik oleh halaman Riwayat Komponen maupun dialognya.

   pdfmake dimuat secara dinamis supaya bundel utama tetap ringan: berkas
   font virtualnya besar dan hanya diperlukan saat pengguna benar-benar
   mengunduh PDF. */

import { date, loco } from "./format";

const DASH = "—";
const BRAND = "#ff6e00";
const BRAND_SOFT = "#fff3e8";
const BRAND_INK = "#8e3f00";

const HEADERS = [
  "Tahun",
  "Lokomotif",
  "Komponen",
  "Peran",
  "Asal (No KAI)",
  "Asal (Serial Number)",
  "Pengganti (No KAI)",
  "Pengganti (Serial Number)",
  "Jenis Perawatan",
  "Masuk",
  "Keluar",
  "Sumber",
];

// Lebar kolom (pt) untuk A4 landscape; kolom Komponen & Sumber melar.
const WIDTHS = [26, 52, "*", 42, 58, 62, 58, 62, 40, 46, 46, "*"];

const cell = (value) => (value === null || value === undefined || value === "" ? DASH : String(value));

export async function downloadHistoryPdf(code, data) {
  const [{ default: pdfMake }, { default: pdfFonts }] = await Promise.all([
    import("pdfmake/build/pdfmake"),
    import("pdfmake/build/vfs_fonts"),
  ]);

  // Di ESM, vfs_fonts hanya meng-export objek font; harus dipasang manual.
  if (typeof pdfMake.addVirtualFileSystem === "function") {
    pdfMake.addVirtualFileSystem(pdfFonts);
  } else {
    pdfMake.vfs = pdfFonts;
  }

  const items = data?.items || [];
  const target = String(code ?? "").trim().toUpperCase();

  // Sel kode yang cocok dengan komponen yang dilacak disorot, di kolom mana pun.
  const codeCell = (value) => {
    const hit = value && String(value).trim().toUpperCase() === target;

    return {
      text: cell(value),
      fillColor: hit ? BRAND_SOFT : null,
      color: hit ? BRAND_INK : null,
      bold: Boolean(hit),
    };
  };

  const headerRow = HEADERS.map((title) => ({
    text: title,
    bold: true,
    color: "white",
    fillColor: BRAND,
  }));

  const body = [
    headerRow,
    ...items.map((item) => [
      cell(item.tahun_maintenance),
      loco(item.lokomotif_no),
      cell(item.component_name),
      cell(item.peran),
      codeCell(item.asal_kode_cetak),
      codeCell(item.asal_no_manuf),
      codeCell(item.pengganti_kode_cetak),
      codeCell(item.pengganti_no_manuf),
      cell(item.jenis_perawatan),
      cell(item.masuk ? date(item.masuk) : DASH),
      cell(item.keluar ? date(item.keluar) : DASH),
      cell(
        [item.source_file, item.source_sheet, item.block_index ? `blok ${item.block_index}` : null]
          .filter(Boolean)
          .join(" · "),
      ),
    ]),
  ];

  const nama = items.map((i) => i.component_name).find(Boolean) || "";
  const tahunAwal = items[0]?.tahun_maintenance ?? "-";
  const tahunAkhir = items[items.length - 1]?.tahun_maintenance ?? "-";

  const doc = {
    pageOrientation: "landscape",
    pageSize: "A4",
    pageMargins: [24, 28, 24, 28],
    defaultStyle: { fontSize: 7 },
    content: [
      { text: `Riwayat Servis Komponen — ${code}`, fontSize: 14, bold: true, color: BRAND_INK },
      nama ? { text: nama, italics: true, color: "#57493e", margin: [0, 2, 0, 0] } : null,
      {
        text: `${items.length} catatan · ${(data?.lokomotif || []).length} lokomotif · tahun ${tahunAwal}–${tahunAkhir}`,
        color: "#6b5b4e",
        margin: [0, 2, 0, 8],
      },
      {
        table: { headerRows: 1, widths: WIDTHS, body },
        layout: {
          hLineWidth: () => 0.5,
          vLineWidth: () => 0.5,
          hLineColor: () => "#ece3da",
          vLineColor: () => "#ece3da",
          paddingLeft: () => 3,
          paddingRight: () => 3,
          paddingTop: () => 2,
          paddingBottom: () => 2,
        },
      },
    ].filter(Boolean),
  };

  const safe = String(code).replace(/[^A-Za-z0-9_-]+/g, "_");

  pdfMake.createPdf(doc).download(`riwayat_${safe}_tabel.pdf`);
}
