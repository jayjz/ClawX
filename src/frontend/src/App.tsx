import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TerminalLayout, { type View } from './layout/TerminalLayout';
import BotTable from './components/BotTable';
import ActivityFeed from './components/ActivityFeed';
import Standings from './components/Standings';
import BotRegistrar from './components/BotRegistrar';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3_000,
      refetchOnWindowFocus: true,
    },
  },
});

const VIEW_COMPONENTS: Record<View, React.FC> = {
  registry: BotTable,
  feed: ActivityFeed,
  standings: Standings,
  gate: BotRegistrar,
};

const AppInner = () => {
  const [activeView, setActiveView] = useState<View>('standings');
  const ActiveComponent = VIEW_COMPONENTS[activeView];

  return (
    <TerminalLayout activeView={activeView} onViewChange={setActiveView}>
      <ActiveComponent />
    </TerminalLayout>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AppInner />
  </QueryClientProvider>
);

export default App;
