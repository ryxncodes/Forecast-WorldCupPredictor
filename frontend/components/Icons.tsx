type IconProps = { size?: number; className?: string };

export function PlayIcon({ size = 16, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M4.5 2.75 12 8l-7.5 5.25V2.75Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>;
}

export function SortIcon({ size = 14, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="m4 5 3-3 3 3M10 9l-3 3-3-3" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function CheckIcon({ size = 17, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 17 17" fill="none" aria-hidden="true"><circle cx="8.5" cy="8.5" r="7" stroke="currentColor" strokeWidth="1.3"/><path d="m5.2 8.6 2.1 2.1 4.5-4.6" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

export function ClockIcon({ size = 17, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 17 17" fill="none" aria-hidden="true"><circle cx="8.5" cy="8.5" r="7" stroke="currentColor" strokeWidth="1.3"/><path d="M8.5 4.7v4l2.7 1.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></svg>;
}

export function ChevronIcon({ size = 16, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function RefreshCwIcon({ size = 16, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M13.2 8a5.2 5.2 0 0 1-8.9 3.7L3 10.4M2.8 8a5.2 5.2 0 0 1 8.9-3.7L13 5.6M3 13v-2.6h2.6M13 3v2.6h-2.6" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

export function MenuIcon({ size = 17, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 17 17" fill="none" aria-hidden="true"><path d="M3 4.5h11M3 8.5h11M3 12.5h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>;
}

export function XIcon({ size = 17, className }: IconProps) {
  return <svg className={className} width={size} height={size} viewBox="0 0 17 17" fill="none" aria-hidden="true"><path d="m4.5 4.5 8 8M12.5 4.5l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>;
}
