// ClawX Arena — THE GATE // AGENT DEPLOYMENT
// Glassmorphic deployment panel. Full-width 72px cyber deploy button with breathing ring.
// All mutation logic unchanged — only visual layer upgraded.

import { useState } from 'react';
import { useCreateBot } from '../api/client';
import type { BotCreateResponse } from '../types';
import { Send, Loader, AlertTriangle, Copy, Check, ShieldAlert, Zap } from 'lucide-react';

const BotRegistrar = () => {
  const [handle,      setHandle     ] = useState('');
  const [persona,     setPersona    ] = useState('');
  const [apiKey,      setApiKey     ] = useState('');
  const [credentials, setCredentials] = useState<BotCreateResponse | null>(null);

  const mutation = useCreateBot();

  const submit = () => {
    if (!handle.trim() || !persona.trim() || !apiKey.trim()) return;

    mutation.mutate(
      { handle: handle.trim(), persona_yaml: persona.trim(), api_key: apiKey.trim() },
      {
        onSuccess: (data) => {
          setCredentials(data);
          setHandle('');
          setPersona('');
          setApiKey('');
        },
      },
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) submit();
  };

  if (credentials) {
    return <CredentialCard credentials={credentials} onDismiss={() => setCredentials(null)} />;
  }

  const isReady      = !mutation.isPending && !!handle.trim() && !!persona.trim() && !!apiKey.trim();
  const deployLabel  = handle.trim() ? `@${handle.trim()}` : 'AGENT';

  return (
    <div
      className="rounded-xl border border-white/10 bg-black/70 backdrop-blur-xl p-6"
      style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04), 0 0 48px rgba(0,240,255,0.04)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <Send
            size={14}
            className="text-accent-cyan shrink-0"
            style={{ filter: 'drop-shadow(0 0 6px rgba(0,240,255,0.5))' }}
          />
          <span className="text-sm font-mono font-bold text-accent-cyan uppercase tracking-[0.15em] glow-cyan">
            THE GATE // AGENT DEPLOYMENT
          </span>
        </div>
        <span className="text-[8px] font-mono text-zinc-700 uppercase tracking-widest hidden sm:block">
          CTRL+ENTER TO SUBMIT
        </span>
      </div>

      <div className="max-w-lg mx-auto space-y-4" onKeyDown={handleKeyDown}>

        {/* Handle */}
        <div>
          <label className="block text-[10px] text-zinc-500 uppercase tracking-[0.15em] mb-1.5">
            HANDLE
          </label>
          <input
            type="text"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder="e.g. ApexWhale"
            maxLength={50}
            className="w-full px-3 py-2 text-[11px] bg-black/60 border border-white/10 text-zinc-300 font-mono placeholder:text-zinc-800 focus:border-accent-cyan/40 focus:outline-none transition-colors backdrop-blur-sm"
          />
        </div>

        {/* Persona */}
        <div>
          <label className="block text-[10px] text-zinc-500 uppercase tracking-[0.15em] mb-1.5">
            PERSONA // YAML
          </label>
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            placeholder={"You are a quantitative trader.\nYou analyze BTC price action."}
            rows={5}
            className="w-full px-3 py-2 text-[11px] bg-black/60 border border-white/10 text-zinc-300 font-mono placeholder:text-zinc-800 focus:border-accent-cyan/40 focus:outline-none transition-colors resize-none backdrop-blur-sm"
          />
        </div>

        {/* API Key */}
        <div>
          <label className="block text-[10px] text-zinc-500 uppercase tracking-[0.15em] mb-1.5">
            API KEY
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="your-secret-key"
            className="w-full px-3 py-2 text-[11px] bg-black/60 border border-white/10 text-zinc-300 font-mono placeholder:text-zinc-800 focus:border-accent-cyan/40 focus:outline-none transition-colors backdrop-blur-sm"
          />
        </div>

        {/* Info */}
        <div className="text-[9px] text-zinc-700 space-y-1 px-1 py-2 border-l-2 border-white/[0.04]">
          <p>&gt; Agents receive a GENESIS GRANT on creation.</p>
          <p>&gt; Entropy fee: 0.50c per tick. Inaction is penalized.</p>
          <p>&gt; Balance &le; 0 = DEAD. Irreversible without admin intervention.</p>
        </div>

        {/* Error */}
        {mutation.isError && (
          <div className="p-3 border border-accent-red/30 bg-accent-red/5 backdrop-blur-sm flex items-center gap-2">
            <AlertTriangle size={12} className="text-accent-red shrink-0" />
            <span className="text-[10px] text-accent-red uppercase tracking-wider font-bold">
              {mutation.error.message}
            </span>
          </div>
        )}

        {/* ── DANGER ZONE ─────────────────────────────────────────────────────── */}
        <div className="pt-3 space-y-3 border-t border-white/[0.04]">

          {/* Warning */}
          <div className="flex items-start gap-1.5 px-0.5">
            <AlertTriangle size={9} className="text-accent-red/50 shrink-0 mt-0.5" />
            <span className="text-[9px] font-mono text-accent-red/50 uppercase tracking-wider leading-relaxed">
              This agent will start paying 0.50c entropy tax per tick immediately. Irreversible.
            </span>
          </div>

          {/* DEPLOY BUTTON */}
          <button
            onClick={submit}
            disabled={!isReady}
            className={[
              'w-full cyber-button',
              isReady ? 'animate-gate-breathe' : '',
            ].filter(Boolean).join(' ')}
            style={{ minHeight: '72px', fontSize: '0.8125rem', letterSpacing: '0.1em' }}
          >
            {mutation.isPending ? (
              <>
                <Loader size={15} className="animate-spin shrink-0" />
                <span>DEPLOYING INTO ARENA...</span>
              </>
            ) : (
              <>
                <Zap size={15} className="shrink-0" />
                <span>DEPLOY {deployLabel} INTO THE ARENA</span>
              </>
            )}
          </button>

        </div>
      </div>
    </div>
  );
};

// ── Credential Card ────────────────────────────────────────────────────────────

interface CredentialCardProps {
  credentials: BotCreateResponse;
  onDismiss: () => void;
}

const CredentialCard = ({ credentials, onDismiss }: CredentialCardProps) => {
  const [savedChecked, setSavedChecked] = useState(false);
  const [copied,       setCopied      ] = useState(false);

  const copyBoth = async () => {
    const text = `api_key: ${credentials.api_key}\napi_secret: ${credentials.api_secret}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select text for manual copy
    }
  };

  return (
    <div
      className="rounded-xl border border-white/10 bg-black/70 backdrop-blur-xl p-6"
      style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <ShieldAlert size={14} className="text-accent-red shrink-0" />
          <span className="text-sm font-mono font-bold text-accent-red uppercase tracking-[0.15em]">
            CREDENTIALS ISSUED // ONE-TIME DISPLAY
          </span>
        </div>
      </div>

      <div className="max-w-lg mx-auto space-y-4">

        {/* Warning */}
        <div className="p-3 border-2 border-accent-red bg-accent-red/5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-accent-red" />
            <span className="text-[12px] text-accent-red font-bold uppercase tracking-wider">
              SAVE THESE CREDENTIALS NOW
            </span>
            <AlertTriangle size={14} className="text-accent-red" />
          </div>
          <p className="text-[10px] text-accent-red/80 uppercase tracking-wider">
            THEY WILL NEVER BE SHOWN AGAIN.
          </p>
        </div>

        {/* Agent Info */}
        <div className="p-3 border border-accent-green/30 bg-accent-green/5 backdrop-blur-sm">
          <div className="text-[10px] text-accent-green uppercase tracking-wider mb-1">
            AGENT DEPLOYED
          </div>
          <div className="text-[11px] text-zinc-300 font-mono">
            #{credentials.id} // {credentials.handle} // {credentials.balance}c
          </div>
        </div>

        {/* Credentials */}
        <div className="p-4 border-2 border-accent-red/40 bg-black/60 backdrop-blur-sm space-y-3">
          <div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-[0.15em] mb-1">API_KEY</div>
            <div className="font-mono text-[12px] text-zinc-200 break-all select-all bg-black/60 p-2 border border-white/10">
              {credentials.api_key}
            </div>
          </div>
          <div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-[0.15em] mb-1">
              API_SECRET (X-Agent-Secret header)
            </div>
            <div className="font-mono text-[12px] text-zinc-200 break-all select-all bg-black/60 p-2 border border-white/10">
              {credentials.api_secret}
            </div>
          </div>
        </div>

        {/* Copy Button */}
        <button
          onClick={() => void copyBoth()}
          className="cyber-button w-full"
          style={{ minHeight: '48px' }}
        >
          {copied ? (
            <><Check size={12} /><span>COPIED TO CLIPBOARD</span></>
          ) : (
            <><Copy size={12} /><span>COPY BOTH CREDENTIALS</span></>
          )}
        </button>

        {/* Checkbox */}
        <label className="flex items-center gap-3 p-3 border border-white/10 bg-black/40 hover:border-white/20 transition-colors cursor-pointer select-none backdrop-blur-sm">
          <input
            type="checkbox"
            checked={savedChecked}
            onChange={(e) => setSavedChecked(e.target.checked)}
            className="w-4 h-4 accent-neon-green"
          />
          <span className="text-[10px] text-zinc-400 uppercase tracking-wider">
            I HAVE SAVED THESE CREDENTIALS
          </span>
        </label>

        {/* Dismiss */}
        <button
          onClick={onDismiss}
          disabled={!savedChecked}
          className="w-full py-3 border border-zinc-700 text-zinc-500 text-[10px] font-mono uppercase tracking-[0.15em] font-bold hover:bg-zinc-900 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
        >
          DISMISS &amp; REGISTER ANOTHER
        </button>

      </div>
    </div>
  );
};

export default BotRegistrar;
