import React from 'react';
import { render } from '@testing-library/react';
import { describe, it } from 'vitest';
import App from './App';

describe('App', () => {
  it('renders App without crashing', () => {
    render(<App />);
  });
});
