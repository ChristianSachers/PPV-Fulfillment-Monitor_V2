import React from 'react';
import { Card, Row, Col, Statistic } from 'antd';
import { FileTextOutlined, BarChartOutlined, ClockCircleOutlined } from '@ant-design/icons';

const Dashboard: React.FC = () => {
  return (
    <div>
      <h1>Welcome to PPV Fulfillment Monitor</h1>
      <p>Your data science dashboard for monitoring and analyzing PPV fulfillment metrics.</p>
      
      <Row gutter={16} style={{ marginTop: '24px' }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="Total Data Files"
              value={0}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Analyses Completed"
              value={0}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Processing Queue"
              value={0}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;