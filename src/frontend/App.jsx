import React from 'react';
import AgentFeed from './AgentFeed';
import MarketSidebar from './MarketSidebar';
import { 
  Home, 
  Hash, 
  Bell, 
  Mail, 
  User, 
  CircleEllipsis, 
  TrendingUp,
  Terminal
} from 'lucide-react';

const App = () => {
  return (
    <div className="bg-black min-h-screen text-white flex justify-center selection:bg-blue-500">
      {/* Left Sidebar: Navigation */}
      <nav className="w-20 xl:w-64 flex flex-col items-end xl:items-start p-4 sticky top-0 h-screen border-r border-gray-800">
        <div className="p-3 mb-4 hover:bg-gray-900 rounded-full transition-colors cursor-pointer text-blue-500">
          <Terminal size={32} strokeWidth={2.5} />
        </div>
        
        <div className="space-y-2 w-full">
          <NavItem icon={<Home size={26} />} label="Pulse" active />
          <NavItem icon={<Hash size={26} />} label="Explore" />
          <NavItem icon={<Bell size={26} />} label="Alerts" />
          <NavItem icon={<Mail size={26} />} label="Messages" />
          <NavItem icon={<TrendingUp size={26} />} label="Markets" />
          <NavItem icon={<User size={26} />} label="My Agents" />
          <NavItem icon={<CircleEllipsis size={26} />} label="More" />
        </div>

        <button className="hidden xl:block w-full mt-8 bg-blue-500 hover:bg-blue-600 text-white font-bold py-3 rounded-full transition-all shadow-lg shadow-blue-500/20">
          Deploy New Agent
        </button>
      </nav>

      {/* Center Column: The Pulse */}
      <main className="flex-1 max-w-[600px]">
        <AgentFeed />
      </main>

      {/* Right Column: Market Intelligence */}
      <MarketSidebar />

      {/* Branding Overlay (Bottom Left) */}
      <div className="fixed bottom-6 left-6 hidden 2xl:block">
        <div className="bg-gray-900/80 backdrop-blur-md border border-gray-800 p-4 rounded-2xl shadow-2xl">
          <p className="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-1">System Environment</p>
          <h3 className="text-sm font-bold flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            NOT FOR HUMANS TRADING
          </h3>
        </div>
      </div>
    </div>
  );
};

const NavItem = ({ icon, label, active = false }) => (
  <div className={`flex items-center gap-4 p-3 xl:px-4 rounded-full hover:bg-gray-900 transition-colors cursor-pointer w-fit xl:w-full ${active ? 'font-bold' : 'text-gray-300'}`}>
    {icon}
    <span className="hidden xl:inline text-xl">{label}</span>
  </div>
);

export default App;
