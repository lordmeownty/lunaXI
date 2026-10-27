export default function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? "compact" : ""}`} aria-label="Luna XI">
      <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden>
        <defs><linearGradient id="bm" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#479ef5" /><stop offset="1" stopColor="#0f6cbd" /></linearGradient></defs>
        <rect width="32" height="32" rx="8" fill="url(#bm)" />
        <path d="M20.5 8.5a8 8 0 1 0 3 12.6A6.6 6.6 0 0 1 20.5 8.5Z" fill="#fff" />
        <circle cx="22.5" cy="11" r="1.6" fill="#fff" opacity=".8" />
      </svg>
      {!compact && <span className="brand-word">Luna<b>XI</b></span>}
    </div>
  );
}
