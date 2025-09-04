import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import Analytics from '../Analytics';

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
          <h2>Analytics Rendering Error</h2>
          <pre>{this.state.error?.message}</pre>
          <pre>{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

describe('Analytics Component - TDD RED Phase Rendering Tests', () => {
  describe('Component Existence and Basic Rendering', () => {
    test('Analytics component exists and can be imported', () => {
      // This test will fail if Analytics component doesn't exist
      expect(() => {
        require('../Analytics');
      }).not.toThrow();
    });

    test('Analytics component renders without crashing', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <Analytics />
        </TestErrorBoundary>
      );
      
      // This test should FAIL if there are rendering errors
      expect(errors).toHaveLength(0);
      expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
      expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
    });

    test('renders main analytics content', () => {
      render(<Analytics />);
      
      // Should fail if main content doesn't render
      expect(screen.getByText('Analytics')).toBeInTheDocument();
      expect(screen.getByText('View and analyze your data with interactive charts and insights.')).toBeInTheDocument();
    });
  });

  describe('Ant Design Components Rendering', () => {
    test('renders Ant Design Card component correctly', () => {
      render(<Analytics />);
      
      // Test for Ant Design Card component - should fail if Card doesn't render
      const cardElement = document.querySelector('.ant-card');
      expect(cardElement).toBeInTheDocument();
      expect(cardElement?.querySelector('.ant-card-body')).toBeInTheDocument();
    });

    test('renders Ant Design Empty component correctly', () => {
      render(<Analytics />);
      
      // Test for Ant Design Empty component - should fail if Empty doesn't render
      const emptyElement = document.querySelector('.ant-empty');
      expect(emptyElement).toBeInTheDocument();
      
      // Check Empty component structure
      expect(emptyElement?.querySelector('.ant-empty-image')).toBeInTheDocument();
      expect(emptyElement?.querySelector('.ant-empty-description')).toBeInTheDocument();
    });

    test('renders Ant Design Icon correctly in Empty component', () => {
      render(<Analytics />);
      
      // Test icon renders - should fail if @ant-design/icons has issues
      const iconElement = document.querySelector('[class*="anticon-bar-chart"]');
      expect(iconElement).toBeInTheDocument();
      
      // Check icon styling
      const iconStyle = window.getComputedStyle(iconElement as Element);
      expect(iconStyle.fontSize).toBe('64px');
      expect(iconStyle.color).toBe('rgb(217, 217, 217)'); // #d9d9d9 converted to rgb
    });
  });

  describe('Content and Messaging', () => {
    test('renders correct empty state message', () => {
      render(<Analytics />);
      
      // Should fail if empty state content doesn't render properly
      expect(screen.getByText('No analysis results yet.')).toBeInTheDocument();
      expect(screen.getByText('Upload data to start generating insights.')).toBeInTheDocument();
    });

    test('renders multi-line description correctly', () => {
      render(<Analytics />);
      
      // Should fail if the span with line breaks doesn't render
      const descriptionElement = screen.getByText((content, element) => {
        return element?.tagName.toLowerCase() === 'span' && 
               content.includes('No analysis results yet.');
      });
      expect(descriptionElement).toBeInTheDocument();
    });
  });

  describe('Layout and Styling', () => {
    test('applies correct margin top style to Card', () => {
      render(<Analytics />);
      
      // Should fail if inline styles aren't applied
      const cardElement = document.querySelector('.ant-card') as HTMLElement;
      expect(cardElement).toBeInTheDocument();
      
      const style = window.getComputedStyle(cardElement);
      expect(style.marginTop).toBe('24px');
    });

    test('Empty component has custom icon configuration', () => {
      render(<Analytics />);
      
      // Should fail if custom Empty image isn't rendered correctly
      const emptyImage = document.querySelector('.ant-empty-image');
      expect(emptyImage).toBeInTheDocument();
      
      // The custom icon should be inside the image area
      const customIcon = emptyImage?.querySelector('[class*="anticon-bar-chart"]');
      expect(customIcon).toBeInTheDocument();
    });
  });

  describe('Ant Design Version Compatibility', () => {
    test('uses Ant Design v5 compatible APIs', () => {
      render(<Analytics />);
      
      // Should fail if using deprecated v4 APIs
      expect(screen.queryByText('Warning')).not.toBeInTheDocument();
      
      // Check that Card renders with v5 structure
      const card = document.querySelector('.ant-card');
      expect(card?.querySelector('.ant-card-body')).toBeInTheDocument();
    });

    test('Empty component uses v5 compatible image prop', () => {
      render(<Analytics />);
      
      // Should fail if Empty component doesn't accept custom React element as image
      const emptyElement = document.querySelector('.ant-empty');
      expect(emptyElement).toBeInTheDocument();
      
      // Custom icon should be rendered in image area
      const customIconInImage = document.querySelector('.ant-empty-image [class*="anticon-bar-chart"]');
      expect(customIconInImage).toBeInTheDocument();
    });

    test('no deprecation warnings from Ant Design components', () => {
      render(<Analytics />);
      
      // Should fail if there are Ant Design deprecation warnings
      const deprecationWarnings = consoleErrors.filter(err => 
        err.includes('deprecated') || err.includes('Warning')
      );
      expect(deprecationWarnings).toHaveLength(0);
    });
  });

  describe('JavaScript Runtime Errors', () => {
    test('no unhandled JavaScript errors during render', () => {
      render(<Analytics />);
      
      // Should fail if there are JavaScript runtime errors
      const jsErrors = consoleErrors.filter(err => 
        err.includes('TypeError') || 
        err.includes('ReferenceError') || 
        err.includes('SyntaxError')
      );
      expect(jsErrors).toHaveLength(0);
    });

    test('all Analytics imports load successfully', () => {
      // This test will fail if there are import/module loading issues
      expect(() => {
        require('../Analytics');
      }).not.toThrow();
    });
  });

  describe('Component Mount and Unmount', () => {
    test('Analytics component mounts and unmounts cleanly', () => {
      const { unmount } = render(<Analytics />);
      
      // Should fail if component doesn't mount properly
      expect(screen.getByText('Analytics')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Accessibility and Structure', () => {
    test('renders proper heading hierarchy', () => {
      render(<Analytics />);
      
      // Should fail if heading structure is incorrect
      const h1Element = screen.getByRole('heading', { level: 1 });
      expect(h1Element).toHaveTextContent('Analytics');
    });

    test('renders descriptive paragraph content', () => {
      render(<Analytics />);
      
      // Should fail if descriptive content is missing
      const description = screen.getByText('View and analyze your data with interactive charts and insights.');
      expect(description).toBeInTheDocument();
    });

    test('Empty component provides meaningful description for screen readers', () => {
      render(<Analytics />);
      
      // Should fail if Empty component doesn't have proper description
      const emptyDescription = document.querySelector('.ant-empty-description');
      expect(emptyDescription).toBeInTheDocument();
      expect(emptyDescription?.textContent).toContain('No analysis results yet');
    });
  });

  describe('Future Enhancement Readiness', () => {
    test('page structure ready for chart components', () => {
      render(<Analytics />);
      
      // Should fail if basic structure isn't ready for adding charts
      const mainDiv = document.querySelector('div');
      expect(mainDiv).toBeInTheDocument();
      
      const card = document.querySelector('.ant-card');
      expect(card).toBeInTheDocument();
      
      // Card should have space for future chart content
      const cardBody = card?.querySelector('.ant-card-body');
      expect(cardBody).toBeInTheDocument();
    });
  });
});