import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RiskCard } from '../components/citizen/RiskCard';
import { DemoClient } from '../api/demo';
import { fixtureScenario } from '../demo/__fixtures__/fixture';

async function pointRisk(frame: number) {
  const c = new DemoClient(structuredClone(fixtureScenario), { storage: null, initialFrame: frame });
  return c.pointRisk(26.1676, 91.7699);
}

describe('<RiskCard>', () => {
  it('renders level, score, place and explanation in English', async () => {
    const data = await pointRisk(3);
    render(<RiskCard data={data} lang="en" />);
    expect(screen.getByTestId('citizen-level')).toHaveTextContent('Severe risk — act now');
    expect(screen.getByTestId('citizen-score')).toHaveTextContent(String(Math.round(data.risk.score)));
    expect(screen.getByText(/Anil Nagar, Guwahati/)).toBeInTheDocument();
    expect(screen.getByText(data.risk.explanation)).toBeInTheDocument();
    expect(screen.getByTestId('citizen-risk-card')).toHaveAttribute('data-level', 'red');
  });

  it('renders Hindi chrome and a stale warning', async () => {
    const data = { ...(await pointRisk(0)), stale: true };
    render(<RiskCard data={data} lang="hi" />);
    expect(screen.getByTestId('citizen-level')).toHaveTextContent('सतर्क रहें');
    expect(screen.getByRole('status')).toHaveTextContent('डेटा पुराना');
  });
});
