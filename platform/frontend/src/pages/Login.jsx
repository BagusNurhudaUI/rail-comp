import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Alert, Button, Checkbox, Form, Input } from "antd";
import { LockOutlined, MailOutlined } from "@ant-design/icons";

import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { user, login } = useAuth();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  if (user) return <Navigate to="/" replace />;

  const onFinish = async ({ email, password }) => {
    setLoading(true);
    setError(null);

    try {
      await login(email.trim(), password);
      navigate("/", { replace: true });
    } catch (exception) {
      setError(exception.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="login">
      <div className="login__box">
        <div className="login__card">
          <header className="login__brand">
            <span className="login__mark">RC</span>
            <div>
              <div className="login__name">Rail Comp Tracker</div>
              <p className="login__tagline">Pelacakan komponen dan perawatan lokomotif</p>
            </div>
          </header>

          <h1 className="t-title">Masuk</h1>
          <p className="login__lead">Gunakan akun yang terdaftar untuk melanjutkan.</p>

          {error && (
            <Alert
              type="error"
              showIcon
              message={error}
              style={{ marginBottom: 16 }}
            />
          )}

          <Form
            layout="vertical"
            requiredMark={false}
            initialValues={{ remember: true }}
            onFinish={onFinish}
          >
            <Form.Item
              name="email"
              label="Email"
              rules={[
                { required: true, message: "Email wajib diisi" },
                { type: "email", message: "Format email tidak valid" },
              ]}
            >
              <Input
                size="large"
                autoFocus
                prefix={<MailOutlined style={{ color: "var(--ink-3)" }} />}
                autoComplete="username"
                placeholder="nama@kai.id"
              />
            </Form.Item>

            <Form.Item
              name="password"
              label="Password"
              rules={[{ required: true, message: "Password wajib diisi" }]}
            >
              {/* Placeholder ditulis sebagai kata, bukan titik-titik — deretan
                  titik membuat kolom terlihat sudah terisi. */}
              <Input.Password
                size="large"
                prefix={<LockOutlined style={{ color: "var(--ink-3)" }} />}
                autoComplete="current-password"
                placeholder="Masukkan password"
              />
            </Form.Item>

            <Form.Item name="remember" valuePropName="checked" style={{ marginBottom: 18 }}>
              <Checkbox>Biarkan saya tetap masuk</Checkbox>
            </Form.Item>

            <Button type="primary" size="large" htmlType="submit" block loading={loading}>
              Masuk
            </Button>
          </Form>
        </div>

        <p className="login__foot">
          Hubungi administrator bila Anda belum memiliki akses.
        </p>
      </div>
    </main>
  );
}
