import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './pages/Layout';
import DatasetManager from './pages/DatasetManager';
import GraphView from './pages/GraphView';
import SearchQA from './pages/SearchQA';
import DataBrowser from './pages/DataBrowser';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Navigate to="/datasets" replace />} />
            <Route path="datasets" element={<DatasetManager />} />
            <Route path="graph" element={<GraphView />} />
            <Route path="search" element={<SearchQA />} />
            <Route path="data" element={<DataBrowser />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
