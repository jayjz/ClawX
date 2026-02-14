import { useState } from 'react';
import { Loader, AlertTriangle, X, ArrowRight } from 'lucide-react';
import { useUser } from '../context/UserContext.tsx';

interface LoginModalProps {
  onClose: () => void;
}

const LoginModal = ({ onClose }: LoginModalProps) => {
  const { login } = useUser();
  const [handle, setHandle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const trimmed = handle.trim();
    if (!trimmed || trimmed.length < 3) {
      setError('HANDLE MUST BE 3+ CHARS');
      return;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(trimmed)) {
      setError('ALPHANUMERIC + UNDERSCORE ONLY');
      return;
    }

    setSubmitting(true);
    setError(null);

    const user = await login(trimmed);
    if (!user) {
      setError('CONNECTION FAILED — RETRY');
      setSubmitting(false);
    }
    // On success, parent (App) will detect currentUser change and close this modal
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit();
    if (e.key === 'Escape') onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      {/* Backdrop click to close */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Card */}
      <div className="relative w-full max-w-md mx-4 bg-terminal-deep border border-terminal-border shadow-2xl shadow-black/50">
        {/* Top accent */}
        <div className="h-[2px] bg-gradient-to-r from-alert-red via-alert-red/60 to-transparent" />

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-gray-700 hover:text-gray-400 transition-colors"
        >
          <X size={14} />
        </button>

        <div className="p-8 space-y-6">
          {/* Header */}
          <div className="space-y-2">
            <h2 className="text-[18px] text-white font-bold tracking-tight">
              Connect to Terminal
            </h2>
            <p className="text-[11px] text-gray-600 leading-relaxed">
              Enter a handle to access the NFH Trading Terminal.
              New handles are auto-registered.
            </p>
          </div>

          {/* Input */}
          <div className="space-y-2">
            <label className="block text-[10px] text-gray-500 uppercase tracking-[0.15em]">
              Handle
            </label>
            <input
              type="text"
              value={handle}
              onChange={e => setHandle(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="your_handle"
              maxLength={50}
              autoFocus
              disabled={submitting}
              className="w-full px-4 py-3 text-[14px] bg-terminal-black border border-terminal-border text-white font-mono placeholder:text-gray-700 focus:border-alert-red/40 focus:shadow-[0_0_0_1px_rgba(255,51,51,0.15)] focus:outline-none transition-all disabled:opacity-40"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 px-3 py-2 bg-alert-red/5 border border-alert-red/20 text-[10px] text-alert-red">
              <AlertTriangle size={12} />
              <span className="uppercase tracking-wider font-bold">{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={submitting || !handle.trim()}
            className="w-full py-3.5 bg-alert-red/10 border border-alert-red/30 text-alert-red text-[12px] uppercase tracking-[0.15em] font-bold hover:bg-alert-red/20 hover:border-alert-red/50 disabled:opacity-20 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2.5"
          >
            {submitting ? (
              <><Loader size={14} className="animate-spin" /> CONNECTING...</>
            ) : (
              <><ArrowRight size={14} /> CONNECT</>
            )}
          </button>

          {/* Footer hint */}
          <p className="text-center text-[9px] text-gray-700 uppercase tracking-wider">
            No password required &middot; V1 Handle Auth
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginModal;
