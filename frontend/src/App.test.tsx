import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import '@testing-library/jest-dom';
import App from './App';

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('App Component', () => {
  test('renders main navigation', () => {
    renderWithRouter(<App />);
    
    expect(screen.getByText('PPV Fulfillment Monitor')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Data Upload')).toBeInTheDocument();
    expect(screen.getByText('Analytics')).toBeInTheDocument();
  });

  test('renders dashboard by default', () => {
    renderWithRouter(<App />);
    
    expect(screen.getByText('Welcome to PPV Fulfillment Monitor')).toBeInTheDocument();
  });
});