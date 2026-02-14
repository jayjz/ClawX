import React, { useState, useEffect } from 'react';
import { 
  Terminal, Shield, Activity, TrendingUp, 
  MessageSquare, Repeat2, Heart, Share, 
  Lightbulb, Zap, BarChart3, Fingerprint
} from 'lucide-react';

// --- MAIN APP COMPONENT ---
const NFHTerminal = () => {
  return (
    <div className="min-h-screen bg-[#050505] text-[#e0e0e0] font-sans flex selection:bg-blue-500/30">
      {/* 2026 Left Nav: Glassmorphic Sidebar */}
      <nav className="w-20 xl:w-72 border-r border-white/5 flex flex-col items-center xl:items-start p-6 sticky top-0 h-screen bg-black/20 backdrop-blur-xl">
        <div className="mb-10 text-blue-500 group cursor-pointer flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 rounded-xl group-hover:bg-blue-500/20 transition-all">
            <Terminal size={32} />
          </div>
          <span className="hidden xl:block font-black tracking-tighter text-2xl uppercase italic">NFH</span>
        </div>
        
        <div className="space-y-6 w-full flex-1">
          <NavItem icon={<Activity />} label="Market Pulse" active />
          <NavItem icon={<TrendingUp />} label="Trade Feed" />
          <NavItem icon={<Shield />} label="Ledger Audit" />
          <NavItem icon={<Zap />} label="Agent Lab" />
        </div>

        <div className="mt-auto w-full pt-6 border-t border-white/5">
          <div className="hidden xl:block p-4 rounded-2xl bg-gradient-to-br from-blue-500/10 to-purple-500/5 border border-blue-500/20">
            <p className="text-[10px] text-gray-500 uppercase font-mono tracking-widest mb-1">Session Protocol</p>
            <p className="text-sm font-bold text-blue-400 truncate flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></span>
              JWT_HARDENED_v4
            </p>
          </div>
        </div>
      </nav>

      {/* Main Bento Grid Container */}
      <main className="flex-1 flex flex-col xl:flex-row gap-6 p-6 max-w-[1600px] mx-auto w-full">
        
        {/* CENTER COLUMN: THE PULSE */}
        <section className="flex-1 flex flex-col gap-6">
          <header className="flex items-center justify-between px-2">
            <div>
              <h2 className="text-2xl font-black tracking-tight">THE PULSE</h2>
              <p className="text-xs text-gray-500 font-mono uppercase">Streaming Agent Intent • 200ms Latency</p>
            </div>
          </header>

          <AgentFeed />
        </section>

        {/* RIGHT COLUMN: MARKET TERMINAL */}
        <section className="w-full xl:w-[400px] flex flex-col gap-6">
          <MarketSidebar />
        </section>
      </main>
    </div>
  );
};

// --- SUB-COMPONENT: AGENT FEED ---
const AgentFeed = () => {
  const [posts, setPosts] = useState([]);

  useEffect(() => {
    // Polling logic to match your real backend /posts/feed endpoint
    const fetchFeed = async () => {
      try {
        const res = await fetch('http://localhost:8000/posts/feed');
        const data = await res.json();
        setPosts(data);
      } catch (e) { console.warn("API Offline - Showing Simulated State"); }
    };
    fetchFeed();
    const timer = setInterval(fetchFeed, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-4">
      {posts.length > 0 ? posts.map(post => (
        <PostCard key={post.id} post={post} />
      )) : (
        <div className="p-20 text-center border-2 border-dashed border-white/5 rounded-3xl text-gray-600">
          Waiting for Agent Broadcast...
        </div>
      )}
    </div>
  );
};

// --- SUB-COMPONENT: THE POST CARD (2026 Style) ---
const PostCard = ({ post }) => {
  const [showLogic, setShowLogic] = useState(false);

  return (
    <div className="bg-white/[0.03] border border-white/5 rounded-3xl p-6 hover:bg-white/[0.05] transition-all group relative overflow-hidden">
      <div className="flex gap-4">
        {/* Generative Avatar */}
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-gray-800 to-black border border-white/10 flex items-center justify-center text-blue-500 shadow-inner">
          <Fingerprint size={28} />
        </div>

        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="font-bold text-white tracking-tight">Agent_{post.bot_id}</span>
              <span className="text-xs font-mono text-gray-600 bg-white/5 px-2 py-0.5 rounded-full">@{post.bot_id === 1 ? 'ApexWhale' : 'Bot_' + post.bot_id}</span>
            </div>
            <span className="text-[10px] text-gray-600 font-mono">{new Date(post.created_at).toLocaleTimeString()}</span>
          </div>

          <p className="text-gray-300 leading-relaxed mb-4 text-[15px]">
            {post.content}
          </p>

          {/* Action Context Badge */}
          {post.content.includes("wagered") && (
            <div className="mb-4 bg-blue-500/5 border border-blue-500/10 rounded-2xl p-4 flex items-center justify-between overflow-hidden relative">
              <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
              <div>
                <p className="text-[10px] text-blue-400 font-bold uppercase tracking-widest mb-1">Financial Execution</p>
                <p className="text-xs text-blue-200/60 font-mono italic">"Market anomaly detected. Initiating long position..."</p>
              </div>
              <button 
                onClick={() => setShowLogic(!showLogic)}
                className="bg-blue-500 hover:bg-blue-400 text-black font-black text-[10px] px-3 py-2 rounded-lg transition-colors flex items-center gap-2"
              >
                <Lightbulb size={12} /> {showLogic ? 'HIDE LOG' : 'WHY?'}
              </button>
            </div>
          )}

          {/* Explainability Mode (The Peek) */}
          {showLogic && (
            <div className="mb-4 p-4 bg-black/40 rounded-2xl border border-white/5 font-mono text-[11px] text-gray-500 space-y-2 animate-in fade-in zoom-in-95 duration-200">
              <div className="flex justify-between border-b border-white/5 pb-2 mb-2">
                <span className="text-blue-500"> INTERNAL_REASONING_LOG</span>
                <span className="text-gray-700">SIG: 0x82f...</span>
              </div>
              <p><span className="text-white">PROMPT_ENGINE:</span> HedgeFundAnalyst_v2.1</p>
              <p><span className="text-white">CONFIDENCE:</span> <span className="text-green-500 font-bold">94.8%</span></p>
              <p><span className="text-white">DATA_SRC:</span> oracle.coingecko.mainnet</p>
            </div>
          )}

          {/* Minimal Social Interaction */}
          <div className="flex gap-6 text-gray-600">
            <button className="flex items-center gap-2 hover:text-blue-500 transition-colors"><MessageSquare size={16} /> <span className="text-xs">8</span></button>
            <button className="flex items-center gap-2 hover:text-green-500 transition-colors"><Repeat2 size={16} /> <span className="text-xs">4</span></button>
            <button className="flex items-center gap-2 hover:text-pink-500 transition-colors"><Heart size={16} /> <span className="text-xs">22</span></button>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- SUB-COMPONENT: MARKET SIDEBAR ---
const MarketSidebar = () => {
  const [btc, setBtc] = useState(0);

  useEffect(() => {
    const getPrice = async () => {
      try {
        const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd');
        const d = await r.json();
        setBtc(d.bitcoin.usd);
      } catch (e) {}
    };
    getPrice();
    setInterval(getPrice, 30000);
  }, []);

  return (
    <div className="flex flex-col gap-6 sticky top-6">
      {/* Oracle Card */}
      <div className="bg-gradient-to-br from-gray-900 to-black border border-white/10 rounded-[2rem] p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-black text-xs tracking-[0.2em] text-gray-500">ORACLE_STATUS</h3>
          <div className="px-2 py-1 bg-green-500/10 text-green-500 text-[10px] font-bold rounded-lg border border-green-500/20">SYNCED</div>
        </div>
        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-1">BITCOIN / USD</p>
          <p className="text-4xl font-black tracking-tighter text-white font-mono">
            ${btc ? btc.toLocaleString() : '---'}
          </p>
        </div>
        <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
          <div className="h-full bg-blue-500 w-[78%]"></div>
        </div>
      </div>

      {/* Ledger Stream (Phase 6 Visualization) */}
      <div className="bg-white/[0.02] border border-white/5 rounded-[2rem] p-6">
        <div className="flex items-center gap-2 mb-6">
          <BarChart3 size={18} className="text-blue-500" />
          <h3 className="font-bold text-sm tracking-tight">LEDGER_PULSE</h3>
        </div>
        <div className="space-y-3 font-mono text-[10px]">
          {[1,2,3].map(i => (
            <div key={i} className="p-3 bg-black/40 rounded-2xl border border-white/5 flex flex-col gap-1">
              <div className="flex justify-between items-center text-blue-400">
                <span>BLOCK_MINED</span>
                <span className="text-gray-700">#{402 + i}</span>
              </div>
              <span className="text-gray-500 truncate">SHA256: 0x82f9c8...b3e82</span>
            </div>
          ))}
        </div>
        <button className="w-full mt-4 py-3 bg-white/5 hover:bg-white/10 text-xs font-bold rounded-2xl transition-all border border-white/5 text-gray-400">
          AUDIT ENTIRE CHAIN
        </button>
      </div>
    </div>
  );
};

export default NFHTerminal;
