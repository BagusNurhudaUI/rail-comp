/* Token antd disetel dari nilai yang sama dengan variabel CSS supaya
   komponen antd dan markup sendiri tidak pernah berbeda satu-dua piksel
   warna. */

export const BRAND = {
  brand: "#ff6e00",
  brandStrong: "#d65f00",
  brandSoft: "#fff3e8",
  brandInk: "#8e3f00",
  accent: "#201eff",
  accentSoft: "#e8eaff",
  accentInk: "#01008e",
  ground: "#faf7f4",
  surface: "#ffffff",
  surface2: "#f4efe9",
  ink: "#21160f",
  ink2: "#57493e",
  ink3: "#6b5b4e",
  line: "#ece3da",
  lineStrong: "#d8cabb",
};

/* Palet data: oranye dan biru bergantian.
 *
 * Urutannya sengaja diselang-seling, bukan gelap-ke-terang dalam satu hue.
 * Dua kategori bertetangga di grafik hampir selalu perlu dibedakan, dan
 * lompatan hue jauh lebih mudah dilihat daripada perbedaan kepekatan. */
export const DATA_COLORS = [
  "#ff6e00",
  "#201eff",
  "#d65f00",
  "#6766ff",
  "#8e3f00",
  "#0100b2",
  "#ffa966",
  "#8a99ff",
];

/* Untuk skala berurutan (mis. intensitas), satu hue saja lebih tepat
   karena urutannya harus terbaca sebagai tingkatan. */
export const SEQUENTIAL_ORANGE = [
  "#ffdcc2",
  "#ffbd89",
  "#ffa966",
  "#ff9542",
  "#ff6e00",
  "#d65f00",
  "#b24f00",
];

export const antdTheme = {
  token: {
    colorPrimary: BRAND.brand,
    // Tautan memakai oranye tua, bukan oranye murni: pada teks berukuran
    // kecil #ff6e00 hanya mencapai sekitar 3:1 di atas putih.
    colorLink: BRAND.brandInk,
    colorLinkHover: BRAND.brandStrong,
    colorSuccess: "#0f7a4a",
    colorWarning: "#d68a00",
    colorError: "#b23200",
    colorInfo: BRAND.accent,
    colorBgLayout: BRAND.ground,
    colorBgContainer: BRAND.surface,
    colorBorder: BRAND.line,
    colorBorderSecondary: BRAND.line,
    colorText: BRAND.ink,
    colorTextSecondary: BRAND.ink2,
    colorTextTertiary: BRAND.ink3,
    colorTextDescription: BRAND.ink3,
    borderRadius: 8,
    borderRadiusLG: 10,
    borderRadiusSM: 6,
    fontFamily:
      "'Plus Jakarta Sans Variable', 'Plus Jakarta Sans', 'Segoe UI', system-ui, sans-serif",
    fontSize: 13.5,
    controlHeight: 36,
    wireframe: false,
  },
  components: {
    Layout: {
      headerBg: BRAND.surface,
      headerHeight: 54,
      headerPadding: "0 8px",
      siderBg: BRAND.surface,
      bodyBg: BRAND.ground,
    },
    Menu: {
      itemBg: "transparent",
      itemSelectedBg: BRAND.brandSoft,
      itemSelectedColor: BRAND.brandInk,
      itemHoverBg: BRAND.surface2,
      itemColor: BRAND.ink2,
      itemHeight: 36,
      itemMarginInline: 8,
      iconSize: 15,
      groupTitleFontSize: 11,
      groupTitleColor: BRAND.ink3,
    },
    Table: {
      headerBg: BRAND.surface2,
      headerColor: BRAND.ink3,
      rowHoverBg: BRAND.brandSoft,
      cellPaddingBlock: 10,
      cellPaddingInline: 14,
      borderColor: BRAND.line,
    },
    Card: { headerFontSize: 13.5, headerHeight: 44, paddingLG: 16 },
    Statistic: { contentFontSize: 27, titleFontSize: 12 },
    Tag: { defaultBg: BRAND.surface2, defaultColor: BRAND.ink2 },
    Segmented: {
      itemSelectedBg: BRAND.brandSoft,
      itemSelectedColor: BRAND.brandInk,
    },
    Drawer: { paddingLG: 20 },
    Progress: { defaultColor: BRAND.brand },
  },
};
