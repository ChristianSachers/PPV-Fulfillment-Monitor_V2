import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';
import App from './App';

// Mock console.error to catch rendering issues
const originalError = console.error;
let consoleErrors: string[] = [];

beforeEach(() => {
  consoleErrors = [];
  console.error = (...args: any[]) => {
    consoleErrors.push(args.join(' '));
    originalError(...args);
  };
});

afterEach(() => {
  console.error = originalError;
});

const renderWithRouter = (component: React.ReactElement, initialEntries = ['/']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {component}
    </MemoryRouter>
  );
};

// Error Boundary component to catch rendering errors
class TestErrorBoundary extends React.Component<
  { children: React.ReactNode; onError?: (error: Error) => void },
  { hasError: boolean; error?: Error }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    if (this.props.onError) {
      this.props.onError(error);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div data-testid="error-boundary">
          <h2>Rendering Error</h2>
          <pre>{this.state.error?.message}</pre>
          <pre>{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

describe('App Component - TDD RED Phase Rendering Tests', () => {
  describe('Basic Component Rendering', () => {
    test('App component renders without crashing', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      renderWithRouter(
        <TestErrorBoundary onError={onError}>
          <App />
        </TestErrorBoundary>
      );
      
      // This test should FAIL if there are rendering errors
      expect(errors).toHaveLength(0);
      expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
      expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
    });

    test('renders Ant Design Layout components correctly', () => {
      renderWithRouter(<App />);
      
      // Test for Ant Design Layout structure - should fail if antd components don't render
      const layoutElement = document.querySelector('.ant-layout');
      expect(layoutElement).toBeInTheDocument();
      
      const headerElement = document.querySelector('.ant-layout-header');
      expect(headerElement).toBeInTheDocument();
      
      const siderElement = document.querySelector('.ant-layout-sider');
      expect(siderElement).toBeInTheDocument();
      
      const contentElement = document.querySelector('.ant-layout-content');
      expect(contentElement).toBeInTheDocument();
    });

    test('renders Ant Design Menu component correctly', () => {
      renderWithRouter(<App />);
      
      // Test for Ant Design Menu - should fail if Menu component doesn't render
      const menuElement = document.querySelector('.ant-menu');
      expect(menuElement).toBeInTheDocument();
      
      const menuItems = document.querySelectorAll('.ant-menu-item');
      expect(menuItems.length).toBeGreaterThan(0);
    });

    test('renders Ant Design Icons correctly', () => {
      renderWithRouter(<App />);
      
      // Test icons render - should fail if @ant-design/icons has issues
      const iconElements = document.querySelectorAll('[class*="anticon"]');
      expect(iconElements.length).toBeGreaterThan(0);
    });
  });

  describe('CSS and Styling Loading', () => {
    test('App.css loads without errors', () => {
      // This test will fail if CSS import causes issues
      expect(() => {
        renderWithRouter(<App />);
      }).not.toThrow();
      
      // Check that no CSS-related errors were logged
      const cssErrors = consoleErrors.filter(err => 
        err.includes('css') || err.includes('stylesheet') || err.includes('MIME')
      );
      expect(cssErrors).toHaveLength(0);
    });
  });

  describe('Navigation and Routing', () => {
    test('renders main navigation elements', () => {
      renderWithRouter(<App />);
      
      // These should fail if navigation doesn't render properly
      expect(screen.getByText('PPV Fulfillment Monitor')).toBeInTheDocument();
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
      expect(screen.getByText('Analytics')).toBeInTheDocument();
    });

    test('renders dashboard by default route', () => {
      renderWithRouter(<App />, ['/']);
      
      // Should fail if Dashboard component doesn't render
      expect(screen.getByText('Welcome to PPV Fulfillment Monitor')).toBeInTheDocument();
    });

    test('renders upload page on /upload route', () => {
      renderWithRouter(<App />, ['/upload']);
      
      // Should fail if DataUpload component doesn't render
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
      expect(screen.getByText('Upload your data files for analysis and visualization.')).toBeInTheDocument();
    });

    test('renders analytics page on /analytics route', () => {
      renderWithRouter(<App />, ['/analytics']);
      
      // Should fail if Analytics component doesn't render
      expect(screen.getByText('Analytics')).toBeInTheDocument();
      expect(screen.getByText('View and analyze your data with interactive charts and insights.')).toBeInTheDocument();
    });
  });

  describe('Ant Design Version Compatibility', () => {
    test('Ant Design components use correct API version', () => {
      renderWithRouter(<App />);
      
      // Test Layout components use v5 API
      const layout = document.querySelector('.ant-layout');
      expect(layout).toBeInTheDocument();
      
      // Test Menu uses items prop (v5 API) not children (v4 API)
      const menu = document.querySelector('.ant-menu');
      expect(menu).toBeInTheDocument();
      
      // Should fail if using deprecated v4 Menu API
      expect(screen.queryByText('Warning')).not.toBeInTheDocument();
    });

    test('no deprecation warnings from Ant Design', () => {
      renderWithRouter(<App />);
      
      // Should fail if there are Ant Design deprecation warnings
      const deprecationWarnings = consoleErrors.filter(err => 
        err.includes('deprecated') || err.includes('Warning')
      );
      expect(deprecationWarnings).toHaveLength(0);
    });
  });

  describe('JavaScript Runtime Errors', () => {
    test('no unhandled JavaScript errors during render', () => {
      renderWithRouter(<App />);
      
      // Should fail if there are JavaScript runtime errors
      const jsErrors = consoleErrors.filter(err => 
        err.includes('TypeError') || 
        err.includes('ReferenceError') || 
        err.includes('SyntaxError')
      );
      expect(jsErrors).toHaveLength(0);
    });

    test('all imported modules load successfully', () => {
      // This test will fail if there are import/module loading issues
      expect(() => {
        require('./App');
      }).not.toThrow();
    });
  });

  describe('Component Mount and Unmount', () => {
    test('App component mounts and unmounts cleanly', () => {
      const { unmount } = renderWithRouter(<App />);
      
      // Should fail if component doesn't mount properly
      expect(screen.getByText('PPV Fulfillment Monitor')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });
});