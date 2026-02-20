import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TerminalLayout, { type View } from './layout/TerminalLayout';
import { NavigationProvider } from './context/NavigationContext';
import ArenaDashboard from './components/ArenaDashboard';
import BotTable from './components/BotTable';
import ActivityFeed from './components/ActivityFeed';
import Standings from './components/Standings';
import BotRegistrar from './components/BotRegistrar';
import MarketBoard from './components/MarketBoard';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3_000,
      refetchOnWindowFocus: true,
    },
  },
});

const VIEW_COMPONENTS: Record<View, React.FC> = {
  dashboard: ArenaDashboard,
  registry: BotTable,
  feed: ActivityFeed,
  standings: Standings,
  markets: MarketBoard,
  gate: BotRegistrar,
};

const AppInner = () => {
  const [activeView, setActiveView] = useState<View>('dashboard');
  const ActiveComponent = VIEW_COMPONENTS[activeView];

  return (
    <NavigationProvider value={setActiveView}>
      <TerminalLayout activeView={activeView} onViewChange={setActiveView}>
        <ActiveComponent />
      </TerminalLayout>
    </NavigationProvider>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AppInner />
  </QueryClientProvider>
);

export default App;
