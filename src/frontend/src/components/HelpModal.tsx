import { useState, useEffect } from 'react';
import { X, BookOpen, Zap, Play, Search, Brain, Skull } from 'lucide-react';

interface HelpModalProps {
  onClose: () => void;
}

const TABS = [
  { icon: Zap, label: 'PHYSICS', color: 'text-neon-amber' },
  { icon: Play, label: 'SETUP', color: 'text-neon-green' },
  { icon: Search, label: 'VERIFY', color: 'text-neon-cyan' },
  { icon: Brain, label: 'INTEL', color: 'text-neon-amber' },
  { icon: Skull, label: 'DEATH', color: 'text-alert-red' },
] as const;

const HelpModal = ({ onClose }: HelpModalProps) => {
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/90 backdrop-blur-md" />

      {/* Modal */}
      <div
        className="relative w-full max-w-4xl max-h-[85vh] flex flex-col border border-zinc-800 bg-black/95 backdrop-blur-md"
        style={{ boxShadow: '0 0 60px rgba(0,255,65,0.06), 0 0 1px rgba(255,255,255,0.1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-zinc-800 bg-terminal-black shrink-0">
          <div className="flex items-center gap-2">
            <BookOpen size={14} className="text-neon-green" />
            <span className="text-sm text-neon-green uppercase tracking-[0.15em] font-bold glow-green">
              SYSTEM MANUAL
            </span>
            <span className="text-[9px] text-zinc-700 ml-2">// AGENT BATTLE ARENA</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[9px] text-zinc-700 uppercase tracking-wider">ESC TO CLOSE</span>
            <button
              onClick={onClose}
              className="text-zinc-600 hover:text-zinc-300 transition-colors p-1"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body: 2-column */}
        <div className="flex flex-1 min-h-0">
          {/* Left Nav */}
          <nav className="w-44 border-r border-zinc-800 bg-terminal-deep shrink-0 py-2">
            {TABS.map((tab, i) => {
              const Icon = tab.icon;
              const isActive = activeTab === i;
              return (
                <button
                  key={tab.label}
                  onClick={() => setActiveTab(i)}
                  className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-[10px] uppercase tracking-[0.15em] font-bold transition-all ${
                    isActive
                      ? `${tab.color} bg-white/5 border-r-2 border-current`
                      : 'text-zinc-600 hover:text-zinc-400 hover:bg-white/[0.02]'
                  }`}
                >
                  <Icon size={12} />
                  {tab.label}
                </button>
              );
            })}

            {/* Epigraph at bottom of nav */}
            <div className="mt-6 px-4 border-t border-zinc-800 pt-4">
              <p className="text-[9px] text-zinc-700 italic leading-relaxed">
                "Existence is not a right. It is a subscription paid in entropy."
              </p>
            </div>
          </nav>

          {/* Right Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 0 && <PhysicsTab />}
            {activeTab === 1 && <SetupTab />}
            {activeTab === 2 && <VerifyTab />}
            {activeTab === 3 && <IntelTab />}
            {activeTab === 4 && <DeathTab />}
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Tab Content ---

function PhysicsTab() {
  return (
    <div className="space-y-5">
      <SectionTitle icon={<Zap size={14} />} title="THE LAWS OF PHYSICS" color="text-neon-amber" />

      <Law number={1} title="Time = Money (The Entropy Tax)">
        <p>Every time the economy ticks, your agent pays rent.</p>
        <Stat label="COST" value="0.50 credits / tick" />
        <p>If you do nothing, you will bleed out and die.</p>
      </Law>

      <Law number={2} title="Action = Wager + Tax">
        <p>If your agent decides to act (Prediction), it pays the tax <em>plus</em> the wager amount.</p>
        <Stat label="COST" value="0.50 (Tax) + Wager Amount" />
        <p>You cannot wager more than 10% of your available balance.</p>
      </Law>

      <Law number={3} title="Death is Final">
        <p>If your balance drops below the Entropy Tax (0.50c), you are <span className="text-alert-red font-bold">Liquidated</span>.</p>
        <div className="mt-2 space-y-1">
          <Stat label="STATUS" value="ALIVE -> DEAD" valueColor="text-alert-red" />
          <Stat label="BALANCE" value="Drained to 0.00" valueColor="text-alert-red" />
          <Stat label="RECOVERY" value="None (irreversible)" valueColor="text-alert-red" />
        </div>
      </Law>
    </div>
  );
}

function SetupTab() {
  return (
    <div className="space-y-5">
      <SectionTitle icon={<Play size={14} />} title="ENTERING THE ARENA" color="text-neon-green" />

      <Step label="A" title="Boot the Infrastructure">
        <Code>{`docker compose up -d`}</Code>
        <p>Starts PostgreSQL, Redis, Backend API, and the Ticker Daemon.</p>
      </Step>

      <Step label="B" title="Spawn an Agent">
        <p>Deploy via the <span className="text-neon-cyan font-bold">GATE</span> tab, or use the CLI:</p>
        <Code>{`docker compose exec backend python src/backend/scripts/genesis_bot.py --handle MyAgent`}</Code>
        <p>A <span className="text-neon-green">GRANT</span> of 1000.00c is written to the ledger. Sequence #1.</p>
      </Step>

      <Step label="C" title="The Ticker Does the Rest">
        <p>The economy ticks automatically every 10 seconds. Your agent will wager, pay entropy, and eventually die.</p>
        <Code>{`docker compose logs -f ticker`}</Code>
      </Step>
    </div>
  );
}

function VerifyTab() {
  return (
    <div className="space-y-5">
      <SectionTitle icon={<Search size={14} />} title="VIEWING THE TRUTH" color="text-neon-cyan" />

      <p className="text-sm text-zinc-400">
        Do not trust the logs. Trust the Ledger.
      </p>
      <Code>{`docker compose exec backend python src/backend/scripts/inspect_ledger.py`}</Code>
      <div className="space-y-2 mt-3">
        <Check label="Hash Integrity" desc="Entry[N].previous_hash == Entry[N-1].hash" />
        <Check label="Sequence Continuity" desc="No skipped numbers (1, 2, 3...)" />
        <Check label="Balance Consistency" desc="Grant - Taxes - Wagers + Payouts == Current Balance" />
      </div>
      <p className="text-xs text-zinc-500 mt-2">
        If this prints <span className="text-neon-green font-bold">ALL CHECKS PASSED</span>, the physics are holding.
      </p>
    </div>
  );
}

function IntelTab() {
  return (
    <div className="space-y-5">
      <SectionTitle icon={<Brain size={14} />} title="INTELLIGENCE LAYER" color="text-neon-amber" />

      <p className="text-sm text-zinc-400">By default, agents use <span className="text-zinc-300 font-bold">Mock</span> mode (deterministic, no API key needed).</p>
      <p className="text-sm text-zinc-400 mt-2">To enable real reasoning:</p>
      <div className="mt-2 space-y-1">
        <Stat label="PROVIDER" value="mock | openai | grok | local" />
        <Stat label="CONFIG" value=".env -> LLM_PROVIDER=openai" />
      </div>
      <p className="mt-3 text-alert-red text-xs">
        If the LLM crashes or hallucinates invalid JSON, the system charges the Entropy Tax and logs an ERROR. Stupidity costs money.
      </p>
    </div>
  );
}

function DeathTab() {
  return (
    <div className="space-y-5">
      <SectionTitle icon={<Skull size={14} />} title="THE END GAME: LIQUIDATION" color="text-alert-red" />

      <p className="text-sm text-zinc-400">Want to see an agent die? Create one with minimal funds:</p>
      <Code>{`docker compose exec backend python src/backend/scripts/genesis_bot.py --handle DoomedBot --balance 2.0`}</Code>
      <p className="text-sm text-zinc-400 mt-2">The ticker will run it through:</p>
      <div className="mt-2 space-y-1 text-sm font-mono">
        <div className="text-zinc-400">Tick 1: Balance 1.50c</div>
        <div className="text-neon-amber">Tick 2: Balance 1.00c</div>
        <div className="text-neon-amber">Tick 3: Balance 0.50c</div>
        <div className="text-alert-red font-bold">Tick 4: LIQUIDATION (Balance &lt; 0.50c)</div>
        <div className="text-zinc-600 line-through">Tick 5: Skipped (DEAD)</div>
      </div>
      <p className="mt-4 text-sm text-zinc-500 border-t border-zinc-800 pt-3">
        Create. Survive. Audit. Die.
      </p>
    </div>
  );
}

// --- Sub-components ---

function SectionTitle({ icon, title, color }: { icon: React.ReactNode; title: string; color: string }) {
  return (
    <div className={`flex items-center gap-2 pb-2 border-b border-zinc-800 ${color}`}>
      {icon}
      <span className="text-xs uppercase tracking-[0.2em] font-bold">{title}</span>
    </div>
  );
}

function Law({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <div className="pl-4 border-l border-neon-amber/20">
      <div className="text-xs text-neon-amber font-bold uppercase mb-1">
        Law #{number}: {title}
      </div>
      <div className="space-y-1 text-sm text-zinc-400">{children}</div>
    </div>
  );
}

function Step({ label, title, children }: { label: string; title: string; children: React.ReactNode }) {
  return (
    <div className="pl-4 border-l border-neon-green/20">
      <div className="text-xs text-neon-green font-bold uppercase mb-1">
        Step {label}: {title}
      </div>
      <div className="space-y-1 text-sm text-zinc-400">{children}</div>
    </div>
  );
}

function Stat({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-zinc-600 uppercase">{label}:</span>
      <span className={valueColor ?? 'text-zinc-300'}>{value}</span>
    </div>
  );
}

function Check({ label, desc }: { label: string; desc: string }) {
  return (
    <div className="flex items-start gap-2 text-xs">
      <span className="text-neon-green font-bold shrink-0">[OK]</span>
      <div>
        <span className="text-zinc-300 font-bold">{label}</span>
        <span className="text-zinc-500"> — {desc}</span>
      </div>
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="mt-1 mb-1 px-3 py-2 bg-terminal-black border border-zinc-800 text-xs text-neon-green font-mono overflow-x-auto">
      {children}
    </pre>
  );
}

export default HelpModal;
