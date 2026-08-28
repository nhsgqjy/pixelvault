import {useMemo, useState} from 'react';
import {CalendarDays, Download, FolderOpen, FolderPlus, Heart, Images, Plus, Search, Share2, SlidersHorizontal, Trash2, X} from 'lucide-react';
import {api} from '../../lib/api';
import type {Album} from '../../types';

export function LibraryToolbar({activeAlbum, activeMonth, monthBack, albumBack, search, setSearch, filtersOpen, setFiltersOpen, filterCount, loaded, total}: {activeAlbum: Album | null; activeMonth: string | null; monthBack: () => void; albumBack: () => void; search: string; setSearch: (value: string) => void; filtersOpen: boolean; setFiltersOpen: (value: boolean) => void; filterCount: number; loaded: number; total: number}) {
  return <section className="toolbar">{activeAlbum && <button className="back" onClick={albumBack}>← All albums</button>}{activeMonth && <button className="back" onClick={monthBack}>← Full timeline</button>}<label className="search"><Search/><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search names, descriptions or tags"/></label><button className={`filter-toggle ${filterCount ? 'active' : ''}`} onClick={() => setFiltersOpen(!filtersOpen)}><SlidersHorizontal/>Filters{filterCount > 0 && <b>{filterCount}</b>}</button><span>{loaded} loaded · {total} total</span></section>;
}

type BatchProps = {checked: string[]; albums: Album[]; activeAlbum: Album | null; onSetCover: (id: string) => void; onShare: (id: string) => void; onExport: () => void; onSetDate: () => void; onBatch: (action: string, albumId?: string) => Promise<boolean>; onCreateAlbum: (name: string) => Promise<Album | null>; onClear: () => void};
export function BatchToolbar(props: BatchProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const matchingAlbums = useMemo(() => props.albums.filter(album => album.name.toLowerCase().includes(search.trim().toLowerCase())), [props.albums, search]);
  if (!props.checked.length) return null;
  const addToAlbum = async (albumId: string) => {if (await props.onBatch('add_album', albumId)) setPickerOpen(false);};
  const createAndAdd = async (event: React.FormEvent) => {event.preventDefault(); const name = newName.trim(); if (!name) return; setCreating(true); const album = await props.onCreateAlbum(name); if (album) await addToAlbum(album.id); setCreating(false);};
  return <>
    <section className="batch selection-card">
      <header><div><b>{props.checked.length} selected</b><span>Choose what to do with these photos</span></div><button className="selection-done" onClick={props.onClear}>Done</button></header>
      <div className="selection-preview">{props.checked.slice(0, 3).map(id => <img key={id} src={api.url(`/photos/${id}/thumbnail`)} alt="Selected photo"/>)}{props.checked.length > 3 && <span>+{props.checked.length - 3}</span>}</div>
      <button className="album-primary" onClick={() => setPickerOpen(true)}><FolderPlus/>Add to album</button>
      <div className="selection-actions">
        {props.activeAlbum && props.checked.length === 1 && <button onClick={() => props.onSetCover(props.checked[0])}><Images/><span>Cover</span></button>}
        <button disabled={props.checked.length !== 1} title={props.checked.length !== 1 ? 'Share supports one photo at a time' : undefined} onClick={() => props.onShare(props.checked[0])}><Share2/><span>Share</span></button>
        <button onClick={() => props.onBatch('favorite')}><Heart/><span>Favorite</span></button>
        <button onClick={props.onExport}><Download/><span>Download</span></button>
        <button onClick={props.onSetDate}><CalendarDays/><span>Date</span></button>
        {props.activeAlbum && <button onClick={() => props.onBatch('remove_album', props.activeAlbum!.id)}><X/><span>Remove</span></button>}
        <button className="danger" onClick={() => props.onBatch('trash')}><Trash2/><span>Trash</span></button>
      </div>
    </section>
    {pickerOpen && <div className="album-picker-backdrop" onMouseDown={() => setPickerOpen(false)}><section className="album-picker" role="dialog" aria-modal="true" aria-labelledby="album-picker-title" onMouseDown={event => event.stopPropagation()}>
      <header><div><small>ORGANIZE PHOTOS</small><h2 id="album-picker-title">Add to album</h2></div><button aria-label="Close" onClick={() => setPickerOpen(false)}><X/></button></header>
      <label className="album-search"><Search/><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search albums"/></label>
      <form className="album-create" onSubmit={createAndAdd}><input value={newName} onChange={event => setNewName(event.target.value)} placeholder="New album name"/><button disabled={creating || !newName.trim()}><Plus/>{creating ? 'Creating…' : 'Create & add'}</button></form>
      <div className="album-picker-list">{matchingAlbums.map(album => <button key={album.id} onClick={() => addToAlbum(album.id)}>{album.cover_photo_id ? <img src={api.url(`/photos/${album.cover_photo_id}/thumbnail`)} alt=""/> : <i><FolderOpen/></i>}<span><b>{album.name}</b><small>{album.photo_count} photos</small></span><Plus/></button>)}{!matchingAlbums.length && <p>No matching albums</p>}</div>
    </section></div>}
  </>;
}
