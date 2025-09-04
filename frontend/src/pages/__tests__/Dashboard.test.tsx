import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from '../Dashboard';

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
          <h2>Dashboard Rendering Error</h2>
          <pre>{this.state.error?.message}</pre>
          <pre>{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

describe('Dashboard Component - TDD RED Phase Rendering Tests', () => {
  describe('Basic Component Rendering', () => {
    test('Dashboard component renders without crashing', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <Dashboard />
        </TestErrorBoundary>
      );
      
      // This test should FAIL if there are rendering errors
      expect(errors).toHaveLength(0);
      expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
      expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
    });

    test('renders main dashboard content', () => {
      render(<Dashboard />);
      
      // Should fail if main content doesn't render
      expect(screen.getByText('Welcome to PPV Fulfillment Monitor')).toBeInTheDocument();
      expect(screen.getByText('Your data science dashboard for monitoring and analyzing PPV fulfillment metrics.')).toBeInTheDocument();
    });
  });

  describe('Ant Design Components Rendering', () => {
    test('renders Ant Design Card components correctly', () => {
      render(<Dashboard />);
      
      // Test for Ant Design Card components - should fail if Cards don't render
      const cardElements = document.querySelectorAll('.ant-card');
      expect(cardElements.length).toBe(3); // Should have 3 cards
      
      // Each card should have proper structure
      cardElements.forEach(card => {
        expect(card).toBeInTheDocument();
        expect(card.querySelector('.ant-card-body')).toBeInTheDocument();
      });
    });

    test('renders Ant Design Statistic components correctly', () => {
      render(<Dashboard />);
      
      // Test for Ant Design Statistic components - should fail if Statistics don't render
      const statisticElements = document.querySelectorAll('.ant-statistic');
      expect(statisticElements.length).toBe(3); // Should have 3 statistics
      
      // Each statistic should have title and value
      statisticElements.forEach(statistic => {
        expect(statistic).toBeInTheDocument();
        expect(statistic.querySelector('.ant-statistic-title')).toBeInTheDocument();
        expect(statistic.querySelector('.ant-statistic-content')).toBeInTheDocument();
      });
    });

    test('renders Ant Design Row and Col components correctly', () => {
      render(<Dashboard />);
      
      // Test for Ant Design Grid components - should fail if Grid doesn't render
      const rowElement = document.querySelector('.ant-row');
      expect(rowElement).toBeInTheDocument();
      
      const colElements = document.querySelectorAll('.ant-col');
      expect(colElements.length).toBe(3); // Should have 3 columns
    });

    test('renders Ant Design Icons correctly', () => {
      render(<Dashboard />);
      
      // Test icons render in Statistics - should fail if @ant-design/icons has issues
      const iconElements = document.querySelectorAll('[class*="anticon"]');
      expect(iconElements.length).toBe(3); // Should have 3 icons (one per statistic)
      
      // Check for specific icons
      expect(document.querySelector('[class*="anticon-file-text"]')).toBeInTheDocument();
      expect(document.querySelector('[class*="anticon-bar-chart"]')).toBeInTheDocument();
      expect(document.querySelector('[class*="anticon-clock-circle"]')).toBeInTheDocument();
    });
  });

  describe('Statistics Content and Values', () => {
    test('renders correct statistic titles', () => {
      render(<Dashboard />);
      
      // Should fail if statistic titles don't render properly
      expect(screen.getByText('Total Data Files')).toBeInTheDocument();
      expect(screen.getByText('Analyses Completed')).toBeInTheDocument();
      expect(screen.getByText('Processing Queue')).toBeInTheDocument();
    });

    test('renders correct initial statistic values', () => {
      render(<Dashboard />);
      
      // Should fail if statistic values don't render properly
      const statisticValues = document.querySelectorAll('.ant-statistic-content-value');
      expect(statisticValues.length).toBe(3);
      
      // All initial values should be 0
      statisticValues.forEach(value => {
        expect(value.textContent).toBe('0');
      });
    });

    test('statistics have proper prefix icons', () => {
      render(<Dashboard />);
      
      // Should fail if statistic prefixes (icons) don't render
      const statisticPrefixes = document.querySelectorAll('.ant-statistic-content-prefix');
      expect(statisticPrefixes.length).toBe(3);
      
      // Each prefix should contain an icon
      statisticPrefixes.forEach(prefix => {
        const icon = prefix.querySelector('[class*="anticon"]');
        expect(icon).toBeInTheDocument();
      });
    });
  });

  describe('Layout and Styling', () => {
    test('applies correct gutter spacing to Row component', () => {
      render(<Dashboard />);
      
      // Should fail if Row gutter isn't applied correctly
      const rowElement = document.querySelector('.ant-row');
      expect(rowElement).toBeInTheDocument();
      
      // Check that columns have proper spacing
      const colElements = document.querySelectorAll('.ant-col');
      expect(colElements.length).toBe(3);
    });

    test('applies correct span to Col components', () => {
      render(<Dashboard />);
      
      // Should fail if columns don't have proper span classes
      const colElements = document.querySelectorAll('.ant-col-8');
      expect(colElements.length).toBe(3); // All should be span 8
    });

    test('applies margin top style to Row', () => {
      render(<Dashboard />);
      
      // Should fail if inline styles aren't applied
      const rowElement = document.querySelector('.ant-row') as HTMLElement;
      expect(rowElement).toBeInTheDocument();
      
      const style = window.getComputedStyle(rowElement);
      expect(style.marginTop).toBe('24px');
    });
  });

  describe('Ant Design Version Compatibility', () => {
    test('uses Ant Design v5 compatible APIs', () => {
      render(<Dashboard />);
      
      // Should fail if using deprecated v4 APIs
      expect(screen.queryByText('Warning')).not.toBeInTheDocument();
      
      // Check that Cards render with v5 structure
      const cards = document.querySelectorAll('.ant-card');
      cards.forEach(card => {
        expect(card.querySelector('.ant-card-body')).toBeInTheDocument();
      });
    });

    test('no deprecation warnings from Ant Design components', () => {
      render(<Dashboard />);
      
      // Should fail if there are Ant Design deprecation warnings
      const deprecationWarnings = consoleErrors.filter(err => 
        err.includes('deprecated') || err.includes('Warning')
      );
      expect(deprecationWarnings).toHaveLength(0);
    });
  });

  describe('JavaScript Runtime Errors', () => {
    test('no unhandled JavaScript errors during render', () => {
      render(<Dashboard />);
      
      // Should fail if there are JavaScript runtime errors
      const jsErrors = consoleErrors.filter(err => 
        err.includes('TypeError') || 
        err.includes('ReferenceError') || 
        err.includes('SyntaxError')
      );
      expect(jsErrors).toHaveLength(0);
    });

    test('all Dashboard imports load successfully', () => {
      // This test will fail if there are import/module loading issues
      expect(() => {
        require('../Dashboard');
      }).not.toThrow();
    });
  });

  describe('Component Mount and Unmount', () => {
    test('Dashboard component mounts and unmounts cleanly', () => {
      const { unmount } = render(<Dashboard />);
      
      // Should fail if component doesn't mount properly
      expect(screen.getByText('Welcome to PPV Fulfillment Monitor')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Accessibility and Structure', () => {
    test('renders proper heading hierarchy', () => {
      render(<Dashboard />);
      
      // Should fail if heading structure is incorrect
      const h1Element = screen.getByRole('heading', { level: 1 });
      expect(h1Element).toHaveTextContent('Welcome to PPV Fulfillment Monitor');
    });

    test('renders descriptive paragraph content', () => {
      render(<Dashboard />);
      
      // Should fail if descriptive content is missing
      const description = screen.getByText('Your data science dashboard for monitoring and analyzing PPV fulfillment metrics.');
      expect(description).toBeInTheDocument();
    });
  });
});