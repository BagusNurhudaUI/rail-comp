import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Avatar,
  Badge,
  Button,
  Drawer,
  Dropdown,
  Empty,
  Grid,
  Layout,
  List,
  Menu,
  Tag,
  Tooltip,
} from "antd";
import {
  AppstoreOutlined,
  BellOutlined,
  BlockOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  FileTextOutlined,
  HistoryOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  TeamOutlined,
  ToolOutlined,
} from "@ant-design/icons";

import { api } from "../lib/api";
import { initials } from "../lib/format";
import { useAuth } from "../context/AuthContext";
import GlobalSearch from "./GlobalSearch";

const { Sider, Header, Content } = Layout;

const NAV_ITEMS = [
  {
    type: "group",
    label: "Operasional",
    children: [
      { key: "/", icon: <AppstoreOutlined />, label: "Dashboard" },
      { key: "/lokomotif", icon: <DeploymentUnitOutlined />, label: "Lokomotif" },
      { key: "/komponen", icon: <BlockOutlined />, label: "Komponen" },
      { key: "/riwayat-komponen", icon: <HistoryOutlined />, label: "Riwayat Komponen" },
      { key: "/perawatan", icon: <ToolOutlined />, label: "Perawatan" },
    ],
  },
  {
    type: "group",
    label: "Master Data",
    children: [
      { key: "/master/lokomotif", icon: <DatabaseOutlined />, label: "Master Lokomotif" },
      { key: "/master/komponen", icon: <DatabaseOutlined />, label: "Katalog Komponen" },
    ],
  },
  {
    type: "group",
    label: "Manajemen",
    children: [
      { key: "/laporan", icon: <FileTextOutlined />, label: "Laporan" },
      { key: "/pengguna", icon: <TeamOutlined />, label: "Pengguna & Peran" },
      { key: "/pengaturan", icon: <SettingOutlined />, label: "Pengaturan" },
    ],
  },
];

const LEVEL_COLOR = { critical: "error", warning: "warning", info: "processing" };

function BrandMark({ compact }) {
  return (
    <Link to="/" className="brandmark">
      <span className="brandmark__dot">RC</span>
      {!compact && <span>Rail Comp</span>}
    </Link>
  );
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);

  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const screens = Grid.useBreakpoint();

  // Di bawah `md` sidebar rail hanya menyisakan ikon tanpa label; drawer
  // penuh jauh lebih mudah dipakai di layar sentuh.
  const isMobile = !screens.md;

  useEffect(() => {
    api
      .alerts()
      .then((data) => setAlerts(data.items || []))
      .catch(() => setAlerts([]));
  }, []);

  const selectedKey = useMemo(() => {
    const path = location.pathname;
    const keys = NAV_ITEMS.flatMap((group) => group.children.map((item) => item.key));

    // Cocokkan path terpanjang supaya rute bersarang menyorot induknya.
    return (
      keys
        .filter((key) => key !== "/" && path.startsWith(key))
        .sort((a, b) => b.length - a.length)[0] || "/"
    );
  }, [location.pathname]);

  const go = (key) => {
    navigate(key);
    setNavOpen(false);
  };

  const navMenu = (
    <Menu
      mode="inline"
      items={NAV_ITEMS}
      selectedKeys={[selectedKey]}
      onClick={({ key }) => go(key)}
      inlineIndent={14}
    />
  );

  return (
    <Layout hasSider={!isMobile}>
      {!isMobile && (
        <Sider
          className="app-sider"
          theme="light"
          width={228}
          collapsible
          collapsed={collapsed}
          trigger={null}
        >
          <div className="sider-head">
            <BrandMark compact={collapsed} />
          </div>

          <div className="sider-nav">{navMenu}</div>

          {!collapsed && (
            <div className="sider-foot">
              Rail Comp Tracker
              <br />
              Data perawatan lokomotif 2019–2026
            </div>
          )}
        </Sider>
      )}

      <Layout>
        <Header className="app-header">
          {isMobile ? (
            <>
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setNavOpen(true)}
                aria-label="Buka menu"
              />
              <BrandMark compact />
            </>
          ) : (
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed((value) => !value)}
              aria-label={collapsed ? "Buka menu" : "Tutup menu"}
            />
          )}

          <div className="app-header__search">
            <GlobalSearch />
          </div>

          <div className="app-header__spacer" />

          <Tooltip title="Perlu perhatian">
            <Badge count={alerts.length} size="small" offset={[-2, 4]}>
              <Button
                type="text"
                icon={<BellOutlined />}
                onClick={() => setAlertsOpen(true)}
                aria-label="Notifikasi"
              />
            </Badge>
          </Tooltip>

          <Dropdown
            trigger={["click"]}
            menu={{
              items: [
                {
                  key: "profile",
                  label: (
                    <div style={{ padding: "4px 0" }}>
                      <div style={{ fontWeight: 600 }}>{user?.full_name}</div>
                      <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{user?.email}</div>
                      <Tag color="orange" style={{ marginTop: 6 }}>
                        {user?.role}
                      </Tag>
                    </div>
                  ),
                },
                { type: "divider" },
                {
                  key: "settings",
                  icon: <SettingOutlined />,
                  label: "Pengaturan",
                  onClick: () => navigate("/pengaturan"),
                },
                {
                  key: "logout",
                  icon: <LogoutOutlined />,
                  label: "Keluar",
                  danger: true,
                  onClick: logout,
                },
              ],
            }}
          >
            <button className="company-chip" type="button">
              <Avatar size={26} style={{ background: "var(--brand)" }}>
                {initials(user?.full_name)}
              </Avatar>
              <span>{user?.full_name}</span>
            </button>
          </Dropdown>
        </Header>

        <Content>
          <div className="page">
            <Outlet />
          </div>
        </Content>
      </Layout>

      <Drawer
        placement="left"
        open={navOpen}
        onClose={() => setNavOpen(false)}
        width={252}
        styles={{ body: { padding: 0 } }}
        title={<BrandMark />}
      >
        {navMenu}
      </Drawer>

      <Drawer
        title="Perlu perhatian"
        open={alertsOpen}
        onClose={() => setAlertsOpen(false)}
        width={isMobile ? "100%" : 460}
      >
        {alerts.length ? (
          <List
            dataSource={alerts}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  avatar={<Badge status={LEVEL_COLOR[item.level] || "default"} />}
                  title={<span style={{ fontSize: 13.5 }}>{item.title}</span>}
                  description={
                    <span style={{ fontSize: 12 }}>
                      {item.meta} {item.context ? `— ${item.context}` : ""}
                    </span>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="Tidak ada temuan" />
        )}
      </Drawer>
    </Layout>
  );
}
