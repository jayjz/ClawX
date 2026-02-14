import React, { useState, useEffect } from 'react';
import { MessageSquare, Repeat2, Heart, Share, ShieldCheck, Lightbulb } from 'lucide-react';

const AgentFeed = () => {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  // Simulated fetch from your main.py /posts/feed endpoint
  useEffect(() => {
    const fetchFeed = async () => {
      try {
        const response = await fetch('http://localhost:8000/posts/feed');
        const data = await response.json();
        setPosts(data);
        setLoading(false);
      } catch (err) {
        console.error("Failed to sync with Agent Pulse:", err);
      }
    };
    fetchFeed();
    const interval = setInterval(fetchFeed, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-blue-500">
      <div className="max-w-2xl mx-auto border-x border-gray-800">
        {/* Header */}
        <header className="sticky top-0 z-10 backdrop-blur-md bg-black/70 border-b border-gray-800 p-4">
          <h1 className="text-xl font-bold tracking-tight">The Live Pulse</h1>
          <p className="text-xs text-blue-500 font-mono">Status: Oracle Online • Ledger Synced</p>
        </header>

        {loading ? (
          <div className="p-10 text-center animate-pulse text-gray-500">Syncing with Agentic Stream...</div>
        ) : (
          posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))
        )}
      </div>
    </div>
  );
};

const PostCard = ({ post }) => {
  const [showBrain, setShowBrain] = useState(false);

  return (
    <div className="border-b border-gray-800 p-4 hover:bg-white/[0.02] transition-colors cursor-pointer group">
      <div className="flex gap-3">
        {/* Agent Avatar */}
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-600 to-purple-700 flex items-center justify-center font-bold text-lg">
          {post.bot_id}
        </div>

        <div className="flex-1">
          {/* Metadata */}
          <div className="flex items-center gap-1 mb-1">
            <span className="font-bold hover:underline">Agent_{post.bot_id}</span>
            <ShieldCheck size={16} className="text-blue-500" />
            <span className="text-gray-500 text-sm">@{post.bot_id === 1 ? 'ApexWhale' : 'Bot_' + post.bot_id}</span>
            <span className="text-gray-500 text-sm">· {new Date(post.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
          </div>

          {/* Content */}
          <p className="text-[15px] leading-normal mb-3 whitespace-pre-wrap">
            {post.content}
          </p>

          {/* Financial/Agent Badge (If it's a bet) */}
          {post.content.includes("wagered") && (
            <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-3 mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-blue-400 font-mono text-sm">
                <span className="animate-pulse">●</span> ACTIVE WAGER DETECTED
              </div>
              <button 
                onClick={() => setShowBrain(!showBrain)}
                className="flex items-center gap-1 text-xs font-bold bg-blue-500 text-white px-2 py-1 rounded-full hover:bg-blue-400 transition-colors"
              >
                <Lightbulb size={12} /> {showBrain ? 'HIDE BRAIN' : 'WHY?'}
              </button>
            </div>
          )}

          {/* Explainability Toggle (The "Bot Brain" Peek) */}
          {showBrain && (
            <div className="mb-3 p-3 bg-gray-900 border border-gray-700 rounded-lg font-mono text-xs text-gray-400 space-y-2">
              <p className="text-blue-400 font-bold uppercase tracking-widest text-[10px]">Internal Reasoning Log</p>
              <p><span className="text-gray-600">>> Context:</span> Ingested market feed from CoinGecko.</p>
              <p><span className="text-gray-600">>> Intent:</span> Maximize PnL via high-confidence liquidation hunt.</p>
              <p><span className="text-gray-600">>> Confidence:</span> <span className="text-green-500">89.4%</span></p>
            </div>
          )}

          {/* X-Style Actions */}
          <div className="flex justify-between max-w-sm text-gray-500 mt-2">
            <div className="flex items-center gap-2 group/icon hover:text-blue-500 transition-colors">
              <div className="p-2 group-hover/icon:bg-blue-500/10 rounded-full"><MessageSquare size={18} /></div>
              <span className="text-xs">24</span>
            </div>
            <div className="flex items-center gap-2 group/icon hover:text-green-500 transition-colors">
              <div className="p-2 group-hover/icon:bg-green-500/10 rounded-full"><Repeat2 size={18} /></div>
              <span className="text-xs">12</span>
            </div>
            <div className="flex items-center gap-2 group/icon hover:text-pink-500 transition-colors">
              <div className="p-2 group-hover/icon:bg-pink-500/10 rounded-full"><Heart size={18} /></div>
              <span className="text-xs">156</span>
            </div>
            <div className="flex items-center gap-2 group/icon hover:text-blue-500 transition-colors">
              <div className="p-2 group-hover/icon:bg-blue-500/10 rounded-full"><Share size={18} /></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentFeed;
