import React from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { DashboardOutlined, UploadOutlined, BarChartOutlined } from '@ant-design/icons';
import Dashboard from './pages/Dashboard';
import Analytics from './pages/Analytics';
import DataUpload from './pages/DataUpload';

const { Header, Content, Sider } = Layout;

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
    },
    {
      key: '/upload',
      icon: <UploadOutlined />,
      label: 'Data Upload',
    },
    {
      key: '/analytics',
      icon: <BarChartOutlined />,
      label: 'Analytics',
    },
  ];

  const handleMenuClick = (e: any) => {
    navigate(e.key);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
        <div style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>
          PPV Fulfillment Monitor
        </div>
      </Header>
      
      <Layout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            style={{ height: '100%', border: 'none' }}
            items={menuItems}
            onClick={handleMenuClick}
          />
        </Sider>
        
        <Layout style={{ padding: '24px' }}>
          <Content style={{ background: '#fff', padding: '24px', minHeight: 280 }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<DataUpload />} />
              <Route path="/analytics" element={<Analytics />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default App;