import React from 'react';
import { Card, Button } from 'antd';
import { UploadOutlined } from '@ant-design/icons';

const DataUpload: React.FC = () => {
  return (
    <div>
      <h1>Data Upload</h1>
      <p>Upload your data files for analysis and visualization.</p>
      
      <Card style={{ marginTop: '24px' }}>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <UploadOutlined style={{ fontSize: '48px', color: '#1890ff', marginBottom: '16px' }} />
          <h3>Drop files here or click to upload</h3>
          <p>Supported formats: CSV, Excel, JSON</p>
          <Button type="primary" icon={<UploadOutlined />} size="large">
            Select Files
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default DataUpload;