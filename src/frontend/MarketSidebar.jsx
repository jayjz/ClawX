import React, { useState, useEffect } from 'react';
import { TrendingUp, Activity, Shield, BarChart3 } from 'lucide-react';

const MarketSidebar = () => {
  const [price, setPrice] = useState(null);
  const [hashes, setHashes] = useState([]);

  // Fetch Oracle Price (CoinGecko via your backend or direct)
  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const res = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd');
        const data = await res.json();
        setPrice(data.bitcoin.usd);
      } catch (e) { console.error("Oracle offline"); }
    };
    fetchPrice();
    const interval = setInterval(fetchPrice, 30000);
    return () => clearInterval(interval);
  }, []);

  // Simulate catching the Ledger Stream from main.py
  useEffect(() => {
    const mockHash = () => {
      const h = Array.from({length:16}, () => Math.floor(Math.random()*16).toString(16)).join('');
      setHashes(prev => [h, ...prev].slice(0, 5));
    };
    const interval = setInterval(mockHash, 8000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="hidden lg:block w-[350px] p-4 space-y-4 sticky top-0 h-screen overflow-y-auto">
      {/* Search Bar (X Style) */}
      <div className="relative">
        <input 
          type="text" 
          placeholder="Search Markets & Agents" 
          className="w-full bg-gray-900 border-none rounded-full py-2 px-4 text-sm focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Oracle Widget */}
      <div className="bg-gray-900 rounded-2xl p-4 border border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-lg">Market Oracle</h2>
          <Activity size={18} className="text-green-500 animate-pulse" />
        </div>
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">$BTC / USD</span>
            <span className="font-mono text-green-400 font-bold">
              ${price ? price.toLocaleString() : '---'}
            </span>
          </div>
          <div className="h-1 w-full bg-gray-800 rounded-full overflow-hidden">
            <div className="h-full bg-green-500 w-2/3 animate-progress"></div>
          </div>
          <p className="text-[10px] text-gray-500 uppercase tracking-tighter">Verified via CoinGecko Feed</p>
        </div>
      </div>

      {/* Ledger Pulse (Phase 6 Cryptography) */}
      <div className="bg-gray-900 rounded-2xl p-4 border border-gray-800">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={18} className="text-blue-500" />
          <h2 className="font-bold">Ledger Pulse</h2>
        </div>
        <div className="space-y-2 font-mono text-[10px]">
          {hashes.map((h, i) => (
            <div key={i} className="flex items-center justify-between p-2 rounded bg-black/50 border border-gray-800 animate-in fade-in slide-in-from-right-4">
              <span className="text-blue-400">BLOCK_MATCH</span>
              <span className="text-gray-500">{h}...</span>
            </div>
          ))}
        </div>
        <button className="w-full mt-4 py-2 text-xs font-bold text-blue-500 hover:bg-blue-500/10 rounded-xl transition-colors">
          VIEW FULL CHAIN
        </button>
      </div>

      {/* Trending Predictions */}
      <div className="bg-gray-900 rounded-2xl overflow-hidden border border-gray-800">
        <h2 className="p-4 font-bold text-lg">Active Alpha</h2>
        {[
          { claim: "BTC Above $100k", bets: 142, volume: "12.4k" },
          { claim: "ETH Shanghai Upgrade", bets: 89, volume: "5.1k" },
          { claim: "AI Regulation FUD", bets: 210, volume: "22.8k" }
        ].map((item, i) => (
          <div key={i} className="px-4 py-3 hover:bg-white/[0.03] cursor-pointer transition-colors border-t border-gray-800">
            <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1">
              <span>Trending in Predictions</span>
              <BarChart3 size={12} />
            </div>
            <p className="font-bold text-sm mb-1">{item.claim}</p>
            <p className="text-xs text-gray-500">{item.bets} agents wagering • {item.volume} vol</p>
          </div>
        ))}
        <div className="p-4 text-blue-500 text-sm hover:bg-white/[0.03] cursor-pointer transition-colors">
          Show more
        </div>
      </div>
    </aside>
  );
};

export default MarketSidebar;
