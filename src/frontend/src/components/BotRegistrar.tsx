import { useState } from 'react';
import { Send, CheckCircle, XCircle, Loader } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

const BotRegistrar = () => {
  const [handle, setHandle] = useState('');
  const [persona, setPersona] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'sending' | 'ok' | 'err'>('idle');

  const submit = async () => {
    if (!handle.trim() || !persona.trim() || !apiKey.trim()) return;

    setStatus('sending');
    setResponse(null);

    try {
      const res = await fetch(`${API_BASE}/bots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          handle: handle.trim(),
          persona_yaml: persona.trim(),
          api_key: apiKey.trim(),
        }),
      });

      const data = await res.json();
      setResponse(JSON.stringify(data, null, 2));
      setStatus(res.ok || res.status === 409 ? 'ok' : 'err');

      if (res.ok) {
        setHandle('');
        setPersona('');
        setApiKey('');
      }
    } catch (e) {
      setResponse(`CONNECTION REFUSED: ${e}`);
      setStatus('err');
    }
  };

  return (
    <div className="p-3 space-y-3 text-[10px]">
      <div className="flex items-center gap-2 pb-2 border-b border-terminal-border">
        <Send size={10} className="text-neon-cyan" />
        <span className="text-gray-600 uppercase tracking-[0.15em]">AGENT REGISTRAR</span>
      </div>

      {/* Handle */}
      <div>
        <label className="block text-gray-600 uppercase tracking-[0.15em] mb-1">HANDLE</label>
        <input
          type="text"
          value={handle}
          onChange={e => setHandle(e.target.value)}
          placeholder="e.g. ApexWhale"
          maxLength={50}
          className="w-full px-2 py-1.5 text-[11px]"
        />
      </div>

      {/* Persona */}
      <div>
        <label className="block text-gray-600 uppercase tracking-[0.15em] mb-1">PERSONA // YAML</label>
        <textarea
          value={persona}
          onChange={e => setPersona(e.target.value)}
          placeholder={"You are a quantitative trader.\nYou analyze BTC price action."}
          rows={5}
          className="w-full px-2 py-1.5 text-[11px] resize-none"
        />
      </div>

      {/* API Key */}
      <div>
        <label className="block text-gray-600 uppercase tracking-[0.15em] mb-1">API KEY</label>
        <input
          type="password"
          value={apiKey}
          onChange={e => setApiKey(e.target.value)}
          placeholder="secret-key-here"
          className="w-full px-2 py-1.5 text-[11px]"
        />
      </div>

      {/* Submit */}
      <button
        onClick={submit}
        disabled={status === 'sending' || !handle.trim() || !persona.trim() || !apiKey.trim()}
        className="w-full py-2 bg-neon-green/10 border border-neon-green/30 text-neon-green uppercase tracking-[0.15em] font-bold hover:bg-neon-green/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
      >
        {status === 'sending' ? (
          <><Loader size={10} className="animate-spin" /> TRANSMITTING...</>
        ) : (
          <><Send size={10} /> DEPLOY AGENT</>
        )}
      </button>

      {/* Response */}
      {response && (
        <div className={`border p-2 ${status === 'ok' ? 'border-neon-green/30' : 'border-alert-red/30'}`}>
          <div className="flex items-center gap-1 mb-1">
            {status === 'ok' ? (
              <><CheckCircle size={10} className="text-neon-green" /><span className="text-neon-green uppercase">SUCCESS</span></>
            ) : (
              <><XCircle size={10} className="text-alert-red" /><span className="text-alert-red uppercase">REJECTED</span></>
            )}
          </div>
          <pre className="text-[9px] text-gray-500 overflow-x-auto whitespace-pre-wrap break-all">
            {response}
          </pre>
        </div>
      )}
    </div>
  );
};

export default BotRegistrar;
