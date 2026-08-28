import {useState} from 'react';
import {BarChart3, CalendarDays, FolderOpen, HardDrive, Heart, Images, LockKeyhole, MoreHorizontal, ScanSearch, Share2, Sparkles, Trash2, X} from 'lucide-react';
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
  const [open, setOpen] = useState(false);
  const primary = nav.filter(([key]) => ['photos', 'timeline', 'favorites', 'albums'].includes(key));
  const secondary = nav.filter(([key]) => ['duplicates', 'shared', 'trash', 'insights'].includes(key));
  const choose = (key: View) => {setOpen(false); onSwitch(key);};
  return <>{open && <div className="mobile-more-backdrop" onClick={() => setOpen(false)}><section className="mobile-more" onClick={event => event.stopPropagation()}><header><div><small>PIXELVAULT</small><b>More destinations</b></div><button aria-label="Close menu" onClick={() => setOpen(false)}><X/></button></header>{secondary.map(([key, Icon, label]) => <button key={key} className={view === key ? 'active' : ''} onClick={() => choose(key)}><Icon/><span>{label}</span></button>)}<button className="mobile-lock" onClick={onLogout}><LockKeyhole/><span>Lock vault</span></button></section></div>}
    <nav className="mobile-nav" aria-label="Primary navigation">{primary.map(([key, Icon, label]) =>
      <button key={key} aria-label={label} aria-current={view === key ? 'page' : undefined} className={view === key ? 'active' : ''} onClick={() => choose(key)}><Icon/><span>{label}</span></button>
    )}<button aria-label="More destinations" aria-expanded={open} className={secondary.some(([key]) => key === view) || open ? 'active' : ''} onClick={() => setOpen(value => !value)}><MoreHorizontal/><span>More</span></button></nav></>;
}
