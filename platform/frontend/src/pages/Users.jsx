import { useState } from "react";
import { App, Avatar, Button, Card, Form, Input, Modal, Select, Switch, Table, Tag } from "antd";
import { UserAddOutlined } from "@ant-design/icons";

import { api } from "../lib/api";
import { useFetch } from "../hooks/useQuery";
import { date, initials, text } from "../lib/format";
import { Cell, PageHead } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const ROLE_COLOR = { admin: "purple", supervisor: "blue", viewer: "default" };

export default function Users() {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const { message, modal } = App.useApp();
  const { user, can } = useAuth();

  const users = useFetch(() => api.users(), []);
  const isAdmin = can("admin");

  const submit = async (values) => {
    setSaving(true);

    try {
      await api.createUser(values);
      message.success("Pengguna ditambahkan");
      setOpen(false);
      form.resetFields();
      users.refetch();
    } catch (exception) {
      message.error(exception.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (row, active) => {
    try {
      await api.updateUser(row.id, { is_active: active });
      message.success(active ? "Pengguna diaktifkan" : "Pengguna dinonaktifkan");
      users.refetch();
    } catch (exception) {
      message.error(exception.message);
    }
  };

  const remove = (row) =>
    modal.confirm({
      title: `Hapus ${row.full_name}?`,
      content: "Akun akan dihapus permanen dan tidak bisa dipulihkan.",
      okText: "Hapus",
      okButtonProps: { danger: true },
      cancelText: "Batal",
      onOk: async () => {
        try {
          await api.deleteUser(row.id);
          message.success("Pengguna dihapus");
          users.refetch();
        } catch (exception) {
          message.error(exception.message);
        }
      },
    });

  const columns = [
    {
      title: "Nama",
      dataIndex: "full_name",
      render: (value, row) => (
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Avatar size={30} style={{ background: "var(--brand)", flex: "none" }}>
            {initials(value)}
          </Avatar>
          <Cell main={text(value)} sub={row.title} />
        </div>
      ),
    },
    {
      title: "Email",
      dataIndex: "email",
      responsive: ["md"],
      render: (value) => <span className="mono">{text(value)}</span>,
    },
    {
      title: "Peran",
      dataIndex: "role",
      width: 130,
      render: (value) => <Tag color={ROLE_COLOR[value] || "default"}>{value}</Tag>,
    },
    {
      title: "Status",
      dataIndex: "is_active",
      width: 118,
      render: (value, row) =>
        isAdmin && row.id !== user?.id ? (
          <Switch
            size="small"
            checked={Boolean(value)}
            onChange={(checked) => toggleActive(row, checked)}
          />
        ) : (
          <Tag color={value ? "green" : "default"}>{value ? "Aktif" : "Nonaktif"}</Tag>
        ),
    },
    {
      title: "Login terakhir",
      dataIndex: "last_login_at",
      width: 156,
      responsive: ["lg"],
      render: (value) => (value ? date(value) : <span className="muted">Belum pernah</span>),
    },
    {
      title: "",
      key: "actions",
      width: 90,
      render: (_, row) =>
        isAdmin && row.id !== user?.id ? (
          <Button size="small" danger type="text" onClick={() => remove(row)}>
            Hapus
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <PageHead
        title="Pengguna & Peran"
        subtitle="Peran menentukan akses import data dan manajemen akun"
        extra={
          isAdmin && (
            <Button type="primary" icon={<UserAddOutlined />} onClick={() => setOpen(true)}>
              Tambah pengguna
            </Button>
          )
        }
      />

      <Card styles={{ body: { padding: 16 } }}>
        <Table
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={users.data?.items || []}
          loading={users.loading}
          pagination={false}
          scroll={{ x: 900 }}
        />
      </Card>

      <Modal
        open={open}
        title="Tambah pengguna"
        okText="Simpan"
        cancelText="Batal"
        confirmLoading={saving}
        onOk={() => form.submit()}
        onCancel={() => setOpen(false)}
      >
        <Form form={form} layout="vertical" requiredMark={false} onFinish={submit}>
          <Form.Item
            name="full_name"
            label="Nama lengkap"
            rules={[{ required: true, message: "Nama wajib diisi" }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: "Email wajib diisi" },
              { type: "email", message: "Format email tidak valid" },
            ]}
          >
            <Input />
          </Form.Item>

          <Form.Item name="title" label="Jabatan">
            <Input placeholder="mis. Technician" />
          </Form.Item>

          <Form.Item name="role" label="Peran" initialValue="viewer">
            <Select
              options={(users.data?.roles || ["viewer", "supervisor", "admin"]).map((value) => ({
                value,
                label: value,
              }))}
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="Password"
            rules={[{ required: true, min: 6, message: "Minimal 6 karakter" }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
