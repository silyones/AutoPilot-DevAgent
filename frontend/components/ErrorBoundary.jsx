import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || 'Unknown error' };
  }

  componentDidCatch(error, info) {
    console.error('UI render error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="max-w-lg mx-auto mt-16 p-6 rounded-2xl border border-danger/40 bg-danger/10 text-[#FFD4DC]">
          <h2 className="font-bold mb-2">UI Error</h2>
          <p className="text-sm">{this.state.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
