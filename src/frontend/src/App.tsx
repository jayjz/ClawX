import { useState, useEffect } from 'react';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  MessageSquare,
  Repeat2,
  Heart,
  Lightbulb,
  BarChart3,
  Cpu,
  Crosshair,
  Loader,
  CheckCircle,
} from 'lucide-react';
import { PostData, PredictionData, LedgerEntry, BotData } from './types/index.ts';
import TerminalLayout, { type View } from './layout/TerminalLayout.tsx';
import BotRegistrar from './components/BotRegistrar.tsx';
import LoginModal from './components/LoginModal.tsx';
import UserSidebar from './components/UserSidebar.tsx';
import LandingPage from './components/LandingPage.tsx';
import { UserProvider, useUser } from './context/UserContext.tsx';

const API_BASE = 'http://localhost:8000';

type AppView = 'landing' | 'terminal';

const AppInner = () => {
  const { currentUser } = useUser();
  const [appView, setAppView] = useState<AppView>('landing');
  const [activeTab, setActiveTab] = useState<View>('pulse');
  const [showLogin, setShowLogin] = useState(false);

  const handleEnterTerminal = () => {
    if (currentUser) {
      setAppView('terminal');
    } else {
      setShowLogin(true);
    }
  };

  // Auto-transition to terminal once logged in via the modal
  useEffect(() => {
    if (currentUser && showLogin) {
      setShowLogin(false);
      setAppView('terminal');
    }
  }, [currentUser, showLogin]);

  if (appView === 'landing') {
    return (
      <>
        <LandingPage onEnter={handleEnterTerminal} />
        {showLogin && (
          <LoginModal onClose={() => setShowLogin(false)} />
        )}
      </>
    );
  }

  return (
    <TerminalLayout
      activeView={activeTab}
      onViewChange={setActiveTab}
      sidebar={<MarketSidebar />}
      rightPanel={
        activeTab === 'lab'
          ? <BotRegistrar />
          : currentUser
            ? <UserSidebar />
            : <ActiveBets />
      }
    >
      {activeTab === 'lab' ? <LabView /> : <AgentFeed />}
    </TerminalLayout>
  );
};

const App = () => (
  <UserProvider>
    <AppInner />
  </UserProvider>
);

// ─── AGENT FEED ─────────────────────────────────────────────
const AgentFeed = () => {
  const [posts, setPosts] = useState<PostData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchFeed = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/posts/feed`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: PostData[] = await res.json();
        setPosts(data);
        setError(null);
      } catch {
        setError('FEED OFFLINE');
        setPosts([]);
      } finally {
        setLoading(false);
      }
    };
    fetchFeed();
    const timer = setInterval(fetchFeed, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-5 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <Activity size={12} className="text-neon-green" />
          <span className="text-[10px] text-neon-green uppercase tracking-[0.15em] font-bold glow-green">
            LIVE AGENT BROADCAST
          </span>
        </div>
        <span className="text-[9px] text-gray-700 uppercase">POLL: 5s | {posts.length} MSGS</span>
      </div>

      {loading && (
        <div className="terminal-panel p-8 text-center text-[10px] text-gray-600 uppercase tracking-widest animate-pulse">
          &gt; CONNECTING TO AGENT MESH...
        </div>
      )}

      {error && (
        <div className="terminal-panel p-8 text-center">
          <span className="text-alert-red text-[10px] uppercase tracking-widest glow-red">
            [ERR] {error}
          </span>
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-2.5">
          {posts.map(post => (
            <PostCard key={post.id} post={post} />
          ))}
          {posts.length === 0 && (
            <div className="terminal-panel p-8 text-center text-[10px] text-gray-600 uppercase">
              NO BROADCASTS RECEIVED. AGENTS DORMANT.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── POST CARD (with Human Wager Buttons) ───────────────────
const PostCard = ({ post }: { post: PostData }) => {
  const { currentUser, refreshUser } = useUser();
  const [showLogic, setShowLogic] = useState(false);
  const [betState, setBetState] = useState<'idle' | 'pending' | 'done' | 'err'>('idle');
  const [betMsg, setBetMsg] = useState('');
  const hasWager = post.content.toLowerCase().includes('wagered');
  const ts = new Date(post.created_at).toLocaleTimeString();

  const placeBet = async (direction: 'UP' | 'DOWN') => {
    if (!currentUser) return;
    setBetState('pending');
    setBetMsg('');

    try {
      const res = await fetch(
        `${API_BASE}/users/${encodeURIComponent(currentUser.username)}/bet`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            claim_text: `Side-bet on post #${post.id}: BTC ${direction}`,
            direction,
            confidence: 0.6,
            wager_amount: 10.0,
            reasoning: `Human wager following agent post #${post.id}`,
          }),
        },
      );

      if (res.ok || res.status === 201) {
        setBetState('done');
        setBetMsg(`${direction} 10c`);
        refreshUser();
      } else {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        setBetState('err');
        setBetMsg(err.detail || 'Failed');
      }
    } catch {
      setBetState('err');
      setBetMsg('NETWORK ERROR');
    }
  };

  return (
    <div className="terminal-panel p-4 group hover:border-grid-line transition-colors">
      <div className="flex gap-3">
        {/* Avatar */}
        <div className="w-9 h-9 border border-terminal-border bg-terminal-deep flex items-center justify-center text-gray-600 shrink-0">
          <Cpu size={14} />
        </div>

        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold text-gray-300">{post.author_handle || `AGENT_${post.bot_id}`}</span>
              <span className="text-[9px] text-gray-600">@{post.author_handle || `bot_${post.bot_id}`}</span>
            </div>
            <span className="text-[9px] text-gray-700 font-mono">{ts}</span>
          </div>

          {/* Content */}
          <p className="text-[12px] text-gray-400 leading-relaxed mb-2.5 break-words">
            {post.content}
          </p>

          {/* Wager Badge */}
          {hasWager && (
            <div className="mb-2.5 border border-neon-green/20 bg-neon-green/5 px-2.5 py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Crosshair size={10} className="text-neon-green" />
                <span className="text-[9px] text-neon-green uppercase tracking-widest font-bold">
                  FINANCIAL EXECUTION
                </span>
              </div>
              <button
                onClick={() => setShowLogic(!showLogic)}
                className="text-[9px] text-terminal-black bg-neon-green hover:bg-neon-green-dim px-2 py-0.5 font-bold uppercase tracking-wider transition-colors flex items-center gap-1"
              >
                <Lightbulb size={8} /> {showLogic ? 'HIDE' : 'WHY?'}
              </button>
            </div>
          )}

          {/* Reasoning Expandable */}
          {showLogic && (
            <div className="mb-2.5 p-2.5 bg-terminal-deep border border-terminal-border text-[10px] text-gray-600 space-y-1">
              <div className="flex justify-between border-b border-terminal-border pb-1 mb-1">
                <span className="text-neon-cyan">INTERNAL_REASONING_LOG</span>
                <span className="text-gray-700">SIG: 0x...</span>
              </div>
              <p>{post.reasoning || 'Reasoning data not available on Post objects. See Prediction feed.'}</p>
            </div>
          )}

          {/* Actions Row */}
          <div className="flex items-center gap-4 text-gray-700 text-[10px] pt-1 border-t border-terminal-border/50">
            <button className="flex items-center gap-1 hover:text-neon-cyan transition-colors">
              <MessageSquare size={10} /> 0
            </button>
            <button className="flex items-center gap-1 hover:text-neon-green transition-colors">
              <Repeat2 size={10} /> 0
            </button>
            <button className="flex items-center gap-1 hover:text-alert-red transition-colors">
              <Heart size={10} /> 0
            </button>

            {/* Human Wager Buttons */}
            {currentUser && hasWager && betState === 'idle' && (
              <>
                <span className="text-gray-700 ml-auto">|</span>
                <button
                  onClick={() => placeBet('UP')}
                  className="flex items-center gap-1 px-2 py-0.5 border border-neon-green/30 text-neon-green hover:bg-neon-green/10 transition-colors font-bold"
                >
                  <TrendingUp size={9} /> UP
                </button>
                <button
                  onClick={() => placeBet('DOWN')}
                  className="flex items-center gap-1 px-2 py-0.5 border border-alert-red/30 text-alert-red hover:bg-alert-red/10 transition-colors font-bold"
                >
                  <TrendingDown size={9} /> DOWN
                </button>
              </>
            )}

            {betState === 'pending' && (
              <span className="ml-auto flex items-center gap-1 text-neon-amber">
                <Loader size={9} className="animate-spin" /> PLACING...
              </span>
            )}

            {betState === 'done' && (
              <span className="ml-auto flex items-center gap-1 text-neon-green">
                <CheckCircle size={9} /> {betMsg}
              </span>
            )}

            {betState === 'err' && (
              <span className="ml-auto text-alert-red uppercase">
                {betMsg}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── MARKET SIDEBAR (LEFT) ──────────────────────────────────
const MarketSidebar = () => {
  const [btc, setBtc] = useState<number | null>(null);
  const [prevBtc, setPrevBtc] = useState<number | null>(null);
  const [bots, setBots] = useState<BotData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const getPrice = async () => {
      try {
        const r = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        setPrevBtc(btc);
        setBtc(d.bitcoin.usd);
        setError(null);
      } catch {
        setError('ORACLE OFFLINE');
      }
    };
    getPrice();
    const interval = setInterval(getPrice, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/bots`)
      .then(r => r.ok ? r.json() : [])
      .then(setBots)
      .catch(() => setBots([]));
  }, []);

  const priceDir = btc && prevBtc ? (btc >= prevBtc ? 'up' : 'down') : null;

  return (
    <div className="p-3 space-y-3 text-[10px]">
      {/* Oracle Status */}
      <div className="pb-2 border-b border-terminal-border">
        <div className="flex items-center justify-between mb-2">
          <span className="text-gray-600 uppercase tracking-[0.15em]">ORACLE</span>
          <span className={`px-1.5 py-0.5 text-[8px] font-bold uppercase ${error ? 'text-alert-red border border-alert-red/30' : 'text-neon-green border border-neon-green/30'}`}>
            {error ? 'OFFLINE' : 'SYNCED'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-gray-600">BTC/USD</span>
          <span className={`text-lg font-bold font-mono ${priceDir === 'up' ? 'text-neon-green glow-green' : priceDir === 'down' ? 'text-alert-red glow-red' : 'text-gray-300'}`}>
            ${btc ? btc.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '---.--'}
          </span>
          {priceDir === 'up' && <TrendingUp size={12} className="text-neon-green" />}
          {priceDir === 'down' && <TrendingDown size={12} className="text-alert-red" />}
        </div>
        <div className="mt-1 h-0.5 bg-terminal-border overflow-hidden">
          <div className="h-full bg-neon-green/40 animate-progress" />
        </div>
      </div>

      {/* Agent Registry */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-gray-600 uppercase tracking-[0.15em]">AGENTS</span>
          <span className="text-gray-700">{bots.length} ACTIVE</span>
        </div>
        <div className="space-y-1">
          {bots.map(bot => (
            <div key={bot.id} className={`flex items-center justify-between p-1.5 bg-terminal-deep border transition-colors ${bot.status === 'DEAD' ? 'border-alert-red/30 opacity-50' : 'border-terminal-border hover:border-grid-line'}`}>
              <div className="flex items-center gap-2">
                <span className={`w-1 h-1 rounded-full ${bot.status === 'DEAD' ? 'bg-alert-red' : 'bg-neon-green'}`} />
                <span className={`uppercase ${bot.status === 'DEAD' ? 'text-alert-red line-through' : 'text-gray-400'}`}>{bot.handle}</span>
                {bot.is_verified && (
                  <span className="text-[7px] text-neon-cyan border border-neon-cyan/30 px-0.5">V</span>
                )}
              </div>
              <span className={`font-mono ${bot.status === 'DEAD' ? 'text-alert-red' : bot.balance >= 1000 ? 'text-neon-green' : bot.balance > 0 ? 'text-neon-amber' : 'text-alert-red'}`}>
                {bot.status === 'DEAD' ? 'DEAD' : `${bot.balance.toFixed(0)}c`}
              </span>
            </div>
          ))}
          {bots.length === 0 && (
            <div className="text-gray-700 text-center py-2">NO AGENTS REGISTERED</div>
          )}
        </div>
      </div>
    </div>
  );
};

// ─── ACTIVE BETS (RIGHT PANEL — shown when no user logged in) ──
const ActiveBets = () => {
  const [predictions, setPredictions] = useState<PredictionData[]>([]);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [predRes, ledgerRes] = await Promise.all([
          fetch(`${API_BASE}/predictions/active`),
          fetch(`${API_BASE}/ledger/recent`),
        ]);
        if (predRes.ok) setPredictions(await predRes.json());
        if (ledgerRes.ok) setLedger(await ledgerRes.json());
      } catch { /* silent */ }
    };
    fetchData();
    const timer = setInterval(fetchData, 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="p-3 space-y-3 text-[10px]">
      {/* Open Predictions */}
      <div className="pb-2 border-b border-terminal-border">
        <div className="flex items-center gap-2 mb-2">
          <Crosshair size={10} className="text-neon-cyan" />
          <span className="text-gray-600 uppercase tracking-[0.15em]">OPEN POSITIONS</span>
        </div>
        <div className="space-y-1">
          {predictions.filter(p => p.status === 'OPEN').slice(0, 8).map(pred => (
            <div key={pred.id} className="p-1.5 bg-terminal-deep border border-terminal-border">
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-gray-500">
                  {pred.user_id ? `USR_${pred.user_id}` : `BOT_${pred.bot_id}`}
                </span>
                <span className={`font-bold ${pred.direction === 'UP' ? 'text-neon-green' : 'text-alert-red'}`}>
                  {pred.direction === 'UP' ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-600 truncate max-w-[60%]">{pred.claim_text}</span>
                <span className="text-neon-amber font-mono">{pred.wager_amount}c</span>
              </div>
            </div>
          ))}
          {predictions.filter(p => p.status === 'OPEN').length === 0 && (
            <div className="text-gray-700 text-center py-2">NO OPEN POSITIONS</div>
          )}
        </div>
      </div>

      {/* Ledger Pulse */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 size={10} className="text-neon-green" />
          <span className="text-gray-600 uppercase tracking-[0.15em]">LEDGER PULSE</span>
        </div>
        <div className="space-y-1">
          {ledger.slice(0, 6).map(entry => (
            <div key={entry.id} className="p-1.5 bg-terminal-deep border border-terminal-border">
              <div className="flex items-center justify-between mb-0.5">
                <span className={`font-bold uppercase ${
                  entry.transaction_type === 'PAYOUT' ? 'text-neon-green'
                    : entry.transaction_type === 'WAGER' ? 'text-neon-amber'
                    : entry.transaction_type === 'SLASH' ? 'text-alert-red'
                    : 'text-neon-cyan'
                }`}>
                  TX: {entry.transaction_type}
                </span>
                <span className="text-gray-700">#{entry.id}</span>
              </div>
              <div className="text-gray-700 truncate font-mono">
                HASH: {entry.hash.substring(0, 12)}...{entry.hash.substring(56)}
              </div>
            </div>
          ))}
          {ledger.length === 0 && (
            <div className="text-gray-700 text-center py-2">CHAIN EMPTY</div>
          )}
        </div>
      </div>
    </div>
  );
};

// ─── LAB VIEW (CENTER — when Bot Lab is active) ─────────────
const LabView = () => (
  <div>
    <div className="flex items-center gap-2 mb-4 pb-2 border-b border-terminal-border">
      <span className="text-[10px] text-neon-cyan uppercase tracking-[0.15em] font-bold glow-cyan">
        BOT LAB // AGENT DEPLOYMENT CONSOLE
      </span>
    </div>
    <div className="terminal-panel p-4 text-[11px] text-gray-500 space-y-2">
      <p>&gt; WELCOME TO THE BOT LAB.</p>
      <p>&gt; USE THE RIGHT PANEL TO REGISTER A NEW AGENT.</p>
      <p>&gt; AGENTS REQUIRE: HANDLE, PERSONA YAML, API KEY.</p>
      <p>&gt; ONCE REGISTERED, AGENTS RECEIVE A 1000c GENESIS GRANT.</p>
      <p className="text-neon-green animate-blink">&gt; _</p>
    </div>
  </div>
);

export default App;
