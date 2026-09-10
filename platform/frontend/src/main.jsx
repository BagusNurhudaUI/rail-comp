import "@ant-design/v5-patch-for-react-19";
import "@fontsource-variable/plus-jakarta-sans";
import "./styles/app.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App as AntApp, ConfigProvider } from "antd";
import idID from "antd/locale/id_ID";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { antdTheme } from "./theme";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ConfigProvider theme={antdTheme} locale={idID}>
      <AntApp>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </StrictMode>,
);
