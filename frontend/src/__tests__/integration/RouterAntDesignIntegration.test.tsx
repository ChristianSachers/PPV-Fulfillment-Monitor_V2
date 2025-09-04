import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';
import App from '../../App';

// Mock console.error to catch rendering issues
const originalError = console.error;
const originalWarn = console.warn;
let consoleErrors: string[] = [];
let consoleWarnings: string[] = [];

beforeEach(() => {
  consoleErrors = [];
  consoleWarnings = [];
  console.error = (...args: any[]) => {
    consoleErrors.push(args.join(' '));
    originalError(...args);
  };
  console.warn = (...args: any[]) => {
    consoleWarnings.push(args.join(' '));
    originalWarn(...args);
  };
});

afterEach(() => {
  console.error = originalError;
  console.warn = originalWarn;
});

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
        <div data-testid="integration-error-boundary">
          <h2>Router-AntDesign Integration Error</h2>
          <pre>{this.state.error?.message}</pre>
          <pre>{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

const renderAppWithRouter = (initialEntries = ['/']) => {
  const errors: Error[] = [];
  const onError = (error: Error) => errors.push(error);
  
  const result = render(
    <MemoryRouter initialEntries={initialEntries}>
      <TestErrorBoundary onError={onError}>
        <App />
      </TestErrorBoundary>
    </MemoryRouter>
  );
  
  return { ...result, errors };
};

describe('Router-AntDesign Integration - TDD RED Phase Tests', () => {
  describe('App-Level Integration', () => {
    test('App renders completely without crashing on any route', () => {
      const routes = ['/', '/upload', '/analytics'];
      
      routes.forEach(route => {
        const { errors } = renderAppWithRouter([route]);
        
        // Should FAIL if routing causes rendering errors
        expect(errors).toHaveLength(0);
        expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
        expect(screen.queryByTestId('integration-error-boundary')).not.toBeInTheDocument();
      });
    });

    test('Ant Design Layout renders correctly with React Router', () => {
      renderAppWithRouter();
      
      // Should FAIL if Layout components don't render properly with routing
      const layoutElement = document.querySelector('.ant-layout');
      expect(layoutElement).toBeInTheDocument();
      
      const headerElement = document.querySelector('.ant-layout-header');
      expect(headerElement).toBeInTheDocument();
      
      const siderElement = document.querySelector('.ant-layout-sider');
      expect(siderElement).toBeInTheDocument();
      
      const contentElement = document.querySelector('.ant-layout-content');
      expect(contentElement).toBeInTheDocument();
    });

    test('Ant Design Menu integrates correctly with React Router', () => {
      renderAppWithRouter();
      
      // Should FAIL if Menu doesn't render with router context
      const menuElement = document.querySelector('.ant-menu');
      expect(menuElement).toBeInTheDocument();
      
      const menuItems = document.querySelectorAll('.ant-menu-item');
      expect(menuItems.length).toBe(3); // Dashboard, Upload, Analytics
    });
  });

  describe('Route-Specific Component Rendering', () => {
    test('Dashboard route renders all Ant Design components correctly', () => {
      renderAppWithRouter(['/']);
      
      // Should FAIL if Dashboard Ant Design components don't render
      expect(screen.getByText('Welcome to PPV Fulfillment Monitor')).toBeInTheDocument();
      
      const cardElements = document.querySelectorAll('.ant-card');
      expect(cardElements.length).toBe(3);
      
      const statisticElements = document.querySelectorAll('.ant-statistic');
      expect(statisticElements.length).toBe(3);
      
      const rowElement = document.querySelector('.ant-row');
      expect(rowElement).toBeInTheDocument();
    });

    test('Upload route renders all Ant Design components correctly', () => {
      renderAppWithRouter(['/upload']);
      
      // Should FAIL if DataUpload Ant Design components don't render
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
      
      const cardElement = document.querySelector('.ant-card');
      expect(cardElement).toBeInTheDocument();
      
      const buttonElements = document.querySelectorAll('.ant-btn');
      expect(buttonElements.length).toBeGreaterThan(0);
      
      const iconElements = document.querySelectorAll('[class*="anticon"]');
      expect(iconElements.length).toBeGreaterThan(0);
    });

    test('Analytics route renders all Ant Design components correctly', () => {
      renderAppWithRouter(['/analytics']);
      
      // Should FAIL if Analytics Ant Design components don't render  
      expect(screen.getByText('Analytics')).toBeInTheDocument();
      
      const cardElement = document.querySelector('.ant-card');
      expect(cardElement).toBeInTheDocument();
      
      const emptyElement = document.querySelector('.ant-empty');
      expect(emptyElement).toBeInTheDocument();
      
      const iconElement = document.querySelector('[class*="anticon-bar-chart"]');
      expect(iconElement).toBeInTheDocument();
    });
  });

  describe('Navigation Integration', () => {
    test('menu navigation works without breaking Ant Design rendering', () => {
      renderAppWithRouter(['/']);
      
      // Should start on Dashboard
      expect(screen.getByText('Welcome to PPV Fulfillment Monitor')).toBeInTheDocument();
      
      // Navigate to Upload (this tests navigation functionality if implemented)
      // For now just verify all routes render independently
      const { rerender } = renderAppWithRouter(['/upload']);
      expect(screen.getByText('Upload your data files for analysis and visualization.')).toBeInTheDocument();
      
      renderAppWithRouter(['/analytics']);
      expect(screen.getByText('View and analyze your data with interactive charts and insights.')).toBeInTheDocument();
    });

    test('URL changes don\'t break Ant Design component styling', () => {
      const routes = ['/', '/upload', '/analytics'];
      
      routes.forEach(route => {
        renderAppWithRouter([route]);
        
        // Should FAIL if CSS classes are missing on any route
        const layoutElement = document.querySelector('.ant-layout');
        expect(layoutElement).toBeInTheDocument();
        
        const antComponents = document.querySelectorAll('[class*="ant-"]');
        expect(antComponents.length).toBeGreaterThan(0);
      });
    });
  });

  describe('CSS Loading and Ant Design Styles', () => {
    test('Ant Design CSS loads correctly with routing', () => {
      renderAppWithRouter();
      
      // Should FAIL if Ant Design styles don't load
      const layoutElement = document.querySelector('.ant-layout') as HTMLElement;
      expect(layoutElement).toBeInTheDocument();
      
      // Check that element has computed styles (indicating CSS loaded)
      const computedStyle = window.getComputedStyle(layoutElement);
      expect(computedStyle.display).not.toBe('');
    });

    test('no CSS-related errors during route rendering', () => {
      const routes = ['/', '/upload', '/analytics'];
      
      routes.forEach(route => {
        renderAppWithRouter([route]);
        
        // Should FAIL if there are CSS loading errors
        const cssErrors = consoleErrors.filter(err => 
          err.includes('css') || 
          err.includes('stylesheet') || 
          err.includes('MIME') ||
          err.includes('Failed to load')
        );
        expect(cssErrors).toHaveLength(0);
      });
    });
  });

  describe('Ant Design Version Compatibility with Routing', () => {
    test('no Ant Design version conflicts across routes', () => {
      const routes = ['/', '/upload', '/analytics'];
      
      routes.forEach(route => {
        renderAppWithRouter([route]);
        
        // Should FAIL if there are version compatibility warnings
        const versionWarnings = consoleWarnings.filter(warn => 
          warn.includes('deprecated') || 
          warn.includes('Warning') ||
          warn.includes('version')
        );
        expect(versionWarnings).toHaveLength(0);
      });
    });

    test('Ant Design Menu uses v5 API correctly with routing', () => {
      renderAppWithRouter();
      
      // Should FAIL if Menu is using deprecated v4 API
      const menuElement = document.querySelector('.ant-menu');
      expect(menuElement).toBeInTheDocument();
      
      // In v5, Menu items should be rendered via items prop, not children
      const menuItems = document.querySelectorAll('.ant-menu-item');
      expect(menuItems.length).toBe(3);
      
      // Should not have deprecated warnings
      const deprecationWarnings = consoleErrors.filter(err => 
        err.includes('deprecated') || err.includes('Menu.Item')
      );
      expect(deprecationWarnings).toHaveLength(0);
    });
  });

  describe('JavaScript Module Loading', () => {
    test('all modules load successfully across routes', () => {
      const routes = ['/', '/upload', '/analytics'];
      
      routes.forEach(route => {
        expect(() => {
          renderAppWithRouter([route]);
        }).not.toThrow();
      });
    });

    test('no module loading errors in console', () => {
      const routes = ['/', '/upload', '/analytics'];
      
      routes.forEach(route => {
        renderAppWithRouter([route]);
        
        // Should FAIL if there are module loading errors
        const moduleErrors = consoleErrors.filter(err => 
          err.includes('Module not found') ||
          err.includes('Cannot resolve module') ||
          err.includes('Failed to import')
        );
        expect(moduleErrors).toHaveLength(0);
      });
    });
  });

  describe('Memory Leaks and Cleanup', () => {
    test('components mount and unmount cleanly on route changes', () => {
      const { rerender } = renderAppWithRouter(['/']);
      expect(screen.getByText('Welcome to PPV Fulfillment Monitor')).toBeInTheDocument();
      
      // Should FAIL if component cleanup causes errors
      expect(() => {
        rerender(
          <MemoryRouter initialEntries={['/upload']}>
            <TestErrorBoundary>
              <App />
            </TestErrorBoundary>
          </MemoryRouter>
        );
      }).not.toThrow();
      
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
    });

    test('no memory leaks or cleanup errors', () => {
      const routes = ['/', '/upload', '/analytics', '/', '/upload'];
      
      routes.forEach(route => {
        const { unmount } = renderAppWithRouter([route]);
        
        // Should FAIL if unmounting causes errors
        expect(() => unmount()).not.toThrow();
      });
    });
  });

  describe('Error Boundaries and Error Handling', () => {
    test('routing errors are caught by error boundaries', () => {
      // Test invalid route
      const { errors } = renderAppWithRouter(['/nonexistent']);
      
      // Should either handle gracefully or show proper error
      if (errors.length > 0) {
        expect(screen.getByTestId('integration-error-boundary')).toBeInTheDocument();
      } else {
        // Should render some default content
        const layoutElement = document.querySelector('.ant-layout');
        expect(layoutElement).toBeInTheDocument();
      }
    });

    test('component errors don\'t break entire app routing', () => {
      const { errors } = renderAppWithRouter();
      
      // Should FAIL if component errors break the entire routing system
      expect(errors).toHaveLength(0);
      expect(screen.queryByTestId('integration-error-boundary')).not.toBeInTheDocument();
    });
  });
});