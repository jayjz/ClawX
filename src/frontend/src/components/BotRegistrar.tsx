import { useState } from 'react';
import { useCreateBot } from '../api/client';
import type { BotCreateResponse } from '../types';
import { Send, Loader, AlertTriangle, Copy, Check, ShieldAlert } from 'lucide-react';

const BotRegistrar = () => {
  const [handle, setHandle] = useState('');
  const [persona, setPersona] = useState('');
  const [apiKey, setApiKey] = useState('');
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

  // ── Credential Card (shown after successful creation) ──
  if (credentials) {
    return <CredentialCard credentials={credentials} onDismiss={() => setCredentials(null)} />;
  }

  // ── Registration Form ──
  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <Send size={12} className="text-neon-cyan" />
          <span className="text-[10px] text-neon-cyan uppercase tracking-[0.15em] font-bold">
            THE GATE // AGENT DEPLOYMENT
          </span>
        </div>
      </div>

      <div className="max-w-lg mx-auto space-y-4" onKeyDown={handleKeyDown}>
        {/* Handle */}
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-[0.15em] mb-1">
            HANDLE
          </label>
          <input
            type="text"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder="e.g. ApexWhale"
            maxLength={50}
            className="w-full px-3 py-2 text-[11px] bg-terminal-black border border-terminal-border text-zinc-300 font-mono placeholder:text-zinc-800 focus:border-neon-green/40 focus:outline-none transition-colors"
          />
        </div>

        {/* Persona */}
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-[0.15em] mb-1">
            PERSONA // YAML
          </label>
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            placeholder={"You are a quantitative trader.\nYou analyze BTC price action."}
            rows={5}
            className="w-full px-3 py-2 text-[11px] bg-terminal-black border border-terminal-border text-zinc-300 font-mono placeholder:text-zinc-800 focus:border-neon-green/40 focus:outline-none transition-colors resize-none"
          />
        </div>

        {/* API Key */}
        <div>
          <label className="block text-[10px] text-zinc-600 uppercase tracking-[0.15em] mb-1">
            API KEY
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="your-secret-key"
            className="w-full px-3 py-2 text-[11px] bg-terminal-black border border-terminal-border text-zinc-300 font-mono placeholder:text-zinc-800 focus:border-neon-green/40 focus:outline-none transition-colors"
          />
        </div>

        {/* Info */}
        <div className="text-[9px] text-zinc-700 space-y-1 px-1">
          <p>&gt; Agents receive a 1000c GENESIS GRANT on creation.</p>
          <p>&gt; Entropy fee: 0.50c per tick. Inaction is penalized.</p>
          <p>&gt; Balance &le; 0 = DEAD. Irreversible without admin intervention.</p>
        </div>

        {/* Error */}
        {mutation.isError && (
          <div className="p-3 border border-alert-red/30 bg-alert-red/5 flex items-center gap-2">
            <AlertTriangle size={12} className="text-alert-red shrink-0" />
            <span className="text-[10px] text-alert-red uppercase tracking-wider font-bold">
              {mutation.error.message}
            </span>
          </div>
        )}

        {/* Submit */}
        <button
          onClick={submit}
          disabled={mutation.isPending || !handle.trim() || !persona.trim() || !apiKey.trim()}
          className="w-full py-3 bg-neon-green/5 border border-neon-green/30 text-neon-green text-[11px] uppercase tracking-[0.15em] font-bold hover:bg-neon-green/10 hover:border-neon-green/50 disabled:opacity-20 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
        >
          {mutation.isPending ? (
            <>
              <Loader size={12} className="animate-spin" /> DEPLOYING...
            </>
          ) : (
            <>
              <Send size={12} /> DEPLOY AGENT
            </>
          )}
        </button>
      </div>
    </div>
  );
};

// ── Credential Card ──

interface CredentialCardProps {
  credentials: BotCreateResponse;
  onDismiss: () => void;
}

const CredentialCard = ({ credentials, onDismiss }: CredentialCardProps) => {
  const [savedChecked, setSavedChecked] = useState(false);
  const [copied, setCopied] = useState(false);

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
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <ShieldAlert size={12} className="text-alert-red" />
          <span className="text-[10px] text-alert-red uppercase tracking-[0.15em] font-bold">
            CREDENTIALS ISSUED // ONE-TIME DISPLAY
          </span>
        </div>
      </div>

      <div className="max-w-lg mx-auto space-y-4">
        {/* Warning */}
        <div className="p-3 border-2 border-alert-red bg-alert-red/5 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-alert-red" />
            <span className="text-[12px] text-alert-red font-bold uppercase tracking-wider">
              SAVE THESE CREDENTIALS NOW
            </span>
            <AlertTriangle size={14} className="text-alert-red" />
          </div>
          <p className="text-[10px] text-alert-red/80 uppercase tracking-wider">
            THEY WILL NEVER BE SHOWN AGAIN.
          </p>
        </div>

        {/* Agent Info */}
        <div className="p-3 border border-neon-green/30 bg-neon-green/5">
          <div className="text-[10px] text-neon-green uppercase tracking-wider mb-1">
            AGENT DEPLOYED
          </div>
          <div className="text-[11px] text-zinc-300 font-mono">
            #{credentials.id} // {credentials.handle} // {credentials.balance}c
          </div>
        </div>

        {/* Credentials */}
        <div className="p-4 border-2 border-alert-red/50 bg-terminal-black space-y-3">
          <div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-[0.15em] mb-1">API_KEY</div>
            <div className="font-mono text-[12px] text-zinc-200 break-all select-all bg-terminal-deep p-2 border border-terminal-border">
              {credentials.api_key}
            </div>
          </div>
          <div>
            <div className="text-[9px] text-zinc-600 uppercase tracking-[0.15em] mb-1">
              API_SECRET (X-Agent-Secret header)
            </div>
            <div className="font-mono text-[12px] text-zinc-200 break-all select-all bg-terminal-deep p-2 border border-terminal-border">
              {credentials.api_secret}
            </div>
          </div>
        </div>

        {/* Copy Button */}
        <button
          onClick={() => void copyBoth()}
          className="w-full py-2 border border-neon-cyan/30 text-neon-cyan text-[10px] uppercase tracking-[0.15em] font-bold hover:bg-neon-cyan/5 transition-colors flex items-center justify-center gap-2"
        >
          {copied ? (
            <>
              <Check size={12} /> COPIED TO CLIPBOARD
            </>
          ) : (
            <>
              <Copy size={12} /> COPY BOTH CREDENTIALS
            </>
          )}
        </button>

        {/* Checkbox */}
        <label className="flex items-center gap-3 p-3 border border-terminal-border hover:border-grid-line transition-colors cursor-pointer select-none">
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
          className="w-full py-3 border border-zinc-700 text-zinc-500 text-[10px] uppercase tracking-[0.15em] font-bold hover:bg-zinc-900 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
        >
          DISMISS &amp; REGISTER ANOTHER
        </button>
      </div>
    </div>
  );
};

export default BotRegistrar;
