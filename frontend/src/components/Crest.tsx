export default function Crest({ colour, secondary = "#ffffff", short, size = 36 }: { colour: string; secondary?: string; short: string; size?: number }) {
  const id = `c-${short}-${size}`;
  return (
    <svg width={size} height={size} viewBox="0 0 40 44" role="img" aria-label={`${short} crest`} className="crest">
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={colour} /><stop offset="1" stopColor={colour} stopOpacity=".72" /></linearGradient></defs>
      <path d="M20 2 36 7v13c0 11-7 18-16 22C11 38 4 31 4 20V7Z" fill={`url(#${id})`} stroke="rgba(255,255,255,.35)" strokeWidth="1.2" />
      <path d="M4 20h32" stroke={secondary} strokeOpacity=".5" strokeWidth="2" />
      <text x="20" y="27" textAnchor="middle" fontSize="10.5" fontWeight="700" fill="#fff" fontFamily="Segoe UI, sans-serif">{short}</text>
    </svg>
  );
}
