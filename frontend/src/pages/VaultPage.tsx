import React,{useEffect,useState} from 'react';
import {CalendarDays,CloudUpload,Download,FolderOpen,Images,Pencil,Plus,Search,Share2,SlidersHorizontal,Trash2,X} from 'lucide-react';
import {api} from '../lib/api';
import {bytes} from '../lib/format';
import type {Album,ApiEvent as Event,DeleteIntent,Photo,Security,Stats,TimelineGroup,View} from '../types';
import {BackupPanel} from '../components/BackupPanel';
import {DuplicatePanel} from '../components/DuplicatePanel';
import {IntegrityPanel} from '../components/IntegrityPanel';
import {UploadQueue} from '../components/UploadQueue';
import {DeleteDialog} from '../components/library/DeleteDialog';
import {FilterPanel} from '../components/library/FilterPanel';
import {PhotoDetail} from '../components/library/PhotoDetail';
import {PhotoGallery} from '../components/library/PhotoGallery';
import {MobileNavigation,Sidebar} from '../components/layout/Navigation';
import {VaultHeader} from '../components/layout/VaultHeader';
import {InsightsView} from '../components/InsightsView';
import {AlbumGrid,TimelineGrid} from '../components/library/CollectionViews';
import {BatchToolbar,LibraryToolbar} from '../components/library/LibraryControls';
import {useAlbums} from '../hooks/useAlbums';
import {useChunkedUpload} from '../hooks/useChunkedUpload';
import {usePhotoLibrary} from '../hooks/usePhotoLibrary';
import {useVaultActions} from '../hooks/useVaultActions';

export function VaultPage({onLogout}:{onLogout:()=>void}){
 const[timeline,setTimeline]=useState<TimelineGroup[]>([]),[stats,setStats]=useState<Stats|null>(null),[security,setSecurity]=useState<Security|null>(null),[events,setEvents]=useState<Event[]>([]),[drag,setDrag]=useState(false),[view,setView]=useState<View>('photos'),[search,setSearch]=useState(''),[notice,setNotice]=useState(''),[selected,setSelected]=useState<Photo|null>(null),[checked,setChecked]=useState<string[]>([]),[activeAlbum,setActiveAlbum]=useState<Album|null>(null),[activeMonth,setActiveMonth]=useState<string|null>(null),[playing,setPlaying]=useState(false),[confirming,setConfirming]=useState<DeleteIntent|null>(null);
 const[filtersOpen,setFiltersOpen]=useState(false),[dateFrom,setDateFrom]=useState(''),[dateTo,setDateTo]=useState(''),[minSize,setMinSize]=useState(''),[orientation,setOrientation]=useState('any'),[sort,setSort]=useState('newest');
 const filterCount=[dateFrom,dateTo,minSize,orientation!=='any',sort!=='newest'].filter(Boolean).length;
 const{albums,loadAlbums}=useAlbums();
 const libraryEnabled=view!=='insights'&&view!=='duplicates'&&!(view==='timeline'&&!activeMonth)&&!(view==='albums'&&!activeAlbum);
 const{photos,setPhotos,nextCursor,total,load,loadMore}=usePhotoLibrary({enabled:libraryEnabled,view,search,albumId:activeAlbum?.id,month:activeMonth||undefined,dateFrom,dateTo,minSize,orientation,sort});
 const{progress,uploadState,speeds,uploadErrors,accept,toggleUpload}=useChunkedUpload(()=>load());
 useEffect(()=>{if(view==='insights'){api.get<Stats>('/stats').then(setStats);api.get<{items:Event[]}>('/events').then(payload=>setEvents(payload.items));api.get<Security>('/security').then(setSecurity)}else if(view==='timeline'&&!activeMonth){api.get<{items:TimelineGroup[]}>('/timeline').then(payload=>setTimeline(payload.items))}},[view,activeMonth]);
 const movePhoto=(step:number)=>setSelected(current=>{if(!current||!photos.length)return current;const index=photos.findIndex(photo=>photo.id===current.id);return photos[(index+step+photos.length)%photos.length]});
 useEffect(()=>{if(!selected)return;const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){setSelected(null);setPlaying(false)}if(event.key==='ArrowLeft')movePhoto(-1);if(event.key==='ArrowRight')movePhoto(1)};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[selected,photos]);
 useEffect(()=>{if(!confirming)return;const key=(event:KeyboardEvent)=>{if(event.key==='Escape')setConfirming(null)};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[confirming]);
 useEffect(()=>{if(!playing||!selected)return;const timer=setInterval(()=>movePhoto(1),3500);return()=>clearInterval(timer)},[playing,selected,photos]);
 const{performAction,action,batch,batchCaptureDate,createNewAlbum,renameCurrent,editAlbumDescription,setAlbumCover,removeFromCurrentAlbum,retryProcessing,deleteCurrent,exportSelection,exportAlbum,shareAlbum,revokeAlbumShare}=useVaultActions({checked,setChecked,activeAlbum,setActiveAlbum,setConfirming,setNotice,setPhotos,load,loadAlbums});
 const toggle=(id:string)=>setChecked(current=>current.includes(id)?current.filter(value=>value!==id):[...current,id]);
 const monthLabel=(month:string)=>month==='unknown'?'Unknown date':new Date(`${month}-01T00:00:00`).toLocaleDateString(undefined,{month:'long',year:'numeric'});const labels:Record<View,string>={photos:'All photos',favorites:'Favorites',shared:'Shared links',trash:'Trash',albums:activeAlbum?.name||'Albums',timeline:activeMonth?monthLabel(activeMonth):'Timeline',duplicates:'Similar photos',insights:'Performance'};
 const switchView=(key:View)=>{setView(key);setActiveAlbum(null);setActiveMonth(null);setChecked([])};
 const lockVault=async()=>{await api.post('/auth/logout');onLogout()};
 return <div className="app"><Sidebar view={view} onSwitch={switchView} onLogout={lockVault}/><main>{confirming&&<DeleteDialog intent={confirming} onCancel={()=>setConfirming(null)} onConfirm={async()=>{const intent=confirming;setConfirming(null);await performAction(intent.id,intent.kind);if(intent.kind==='trash'&&activeAlbum)setActiveAlbum(current=>current?{...current,photo_count:Math.max(0,current.photo_count-1)}:current);await loadAlbums()}}/>}
 {notice&&<div className="toast" onClick={()=>setNotice('')}>{notice}</div>}{selected&&<PhotoDetail photo={selected} photoCount={photos.length} playing={playing} onClose={()=>{setSelected(null);setPlaying(false)}} onMove={movePhoto} onTogglePlay={()=>setPlaying(value=>!value)} onSaved={updated=>{setSelected(updated);setPhotos(items=>items.map(item=>item.id===updated.id?updated:item));setNotice('Photo details saved')}}/>}
 <VaultHeader view={view} label={labels[view]} activeAlbum={activeAlbum} onFiles={accept} onCreateAlbum={createNewAlbum} onShareAlbum={shareAlbum} onRevokeAlbum={revokeAlbumShare} onDescribeAlbum={editAlbumDescription} onExportAlbum={exportAlbum} onRenameAlbum={renameCurrent} onDeleteAlbum={deleteCurrent}/>
 {view==='duplicates'?<DuplicatePanel onOpen={photo=>setSelected(photo)}/>:view==='insights'&&stats?<InsightsView stats={stats} events={events} security={security} onLogout={onLogout}/>:view==='timeline'&&!activeMonth?<TimelineGrid groups={timeline} monthLabel={monthLabel} onOpen={setActiveMonth}/>:view==='albums'&&!activeAlbum?<AlbumGrid albums={albums} onOpen={setActiveAlbum} onRename={renameCurrent}/>:<>
 {activeAlbum?.description&&<p className="album-description">{activeAlbum.description}</p>}<LibraryToolbar activeAlbum={activeAlbum} activeMonth={activeMonth} albumBack={()=>setActiveAlbum(null)} monthBack={()=>setActiveMonth(null)} search={search} setSearch={setSearch} filtersOpen={filtersOpen} setFiltersOpen={setFiltersOpen} filterCount={filterCount} loaded={photos.length} total={total}/>{filtersOpen&&<FilterPanel dateFrom={dateFrom} setDateFrom={setDateFrom} dateTo={dateTo} setDateTo={setDateTo} minSize={minSize} setMinSize={setMinSize} orientation={orientation} setOrientation={setOrientation} sort={sort} setSort={setSort} filterCount={filterCount}/>}<BatchToolbar checked={checked} albums={albums} activeAlbum={activeAlbum} onSetCover={async id=>{await setAlbumCover(id);setChecked([])}} onShare={async id=>{await action(id,'share');setChecked([])}} onExport={exportSelection} onSetDate={batchCaptureDate} onBatch={batch} onClear={()=>setChecked([])}/>
 {view==='photos'&&<section className={`drop ${drag?'active':''}`} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);accept(e.dataTransfer.files)}}><CloudUpload/><b>Drop photos anywhere to upload</b><span>3 concurrent chunks · retry-safe · resumable</span></section>}<UploadQueue progress={progress} uploadState={uploadState} speeds={speeds} uploadErrors={uploadErrors} onToggle={toggleUpload}/>
 <PhotoGallery photos={photos} checked={checked} view={view} inAlbum={!!activeAlbum} onOpen={setSelected} onToggle={toggle} onAction={action} onRemoveFromAlbum={removeFromCurrentAlbum} onRetryProcessing={retryProcessing}/>{nextCursor!==null&&<button className="load-more" onClick={loadMore}>Load more photos</button>}</>}
 </main><MobileNavigation view={view} onSwitch={switchView} onLogout={lockVault}/></div>}
