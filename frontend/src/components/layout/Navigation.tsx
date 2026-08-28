import {BarChart3, CalendarDays, FolderOpen, HardDrive, Heart, Images, LockKeyhole, ScanSearch, Share2, Sparkles, Trash2} from 'lucide-react';
import type {View} from '../../types';

const nav = [
  ['photos', Images, 'Photos'], ['timeline', CalendarDays, 'Timeline'], ['favorites', Heart, 'Favorites'],
  ['albums', FolderOpen, 'Albums'], ['duplicates', ScanSearch, 'Similar'], ['shared', Share2, 'Shared'],
  ['trash', Trash2, 'Trash'], ['insights', BarChart3, 'Insights'],
] as const;

type Props = {view: View; onSwitch: (view: View) => void; onLogout: () => void};

export function Sidebar({view, onSwitch, onLogout}: Props) {
  return <aside><div className="brand"><Sparkles/>PixelVault</div><nav>{nav.map(([key, Icon, label]) =>
    <button key={key} aria-current={view === key ? 'page' : undefined} className={view === key ? 'active' : ''} onClick={() => onSwitch(key)}><Icon/>{label}</button>
  )}</nav><button className="lock" onClick={onLogout}>Lock vault</button><div className="storage"><HardDrive/><div><strong>Storage</strong><small>SQLite-backed local vault</small><i><em/></i></div></div></aside>;
}

export function MobileNavigation({view, onSwitch, onLogout}: Props) {
  return <nav className="mobile-nav" aria-label="Mobile navigation">{nav.map(([key, Icon, label]) =>
    <button key={key} aria-label={label} aria-current={view === key ? 'page' : undefined} className={view === key ? 'active' : ''} onClick={() => onSwitch(key)}><Icon/><span>{label}</span></button>
  )}<button aria-label="Lock vault" onClick={onLogout}><LockKeyhole/><span>Lock</span></button></nav>;
}
