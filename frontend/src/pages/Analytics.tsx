import React from 'react';
import { Card, Empty } from 'antd';
import { BarChartOutlined } from '@ant-design/icons';

const Analytics: React.FC = () => {
  return (
    <div>
      <h1>Analytics</h1>
      <p>View and analyze your data with interactive charts and insights.</p>
      
      <Card style={{ marginTop: '24px' }}>
        <Empty
          image={<BarChartOutlined style={{ fontSize: '64px', color: '#d9d9d9' }} />}
          description={
            <span>
              No analysis results yet.<br />
              Upload data to start generating insights.
            </span>
          }
        />
      </Card>
    </div>
  );
};

export default Analytics;