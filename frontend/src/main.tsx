import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Sparkles} from 'lucide-react';
import './styles.css';import './interactions.css';import './slideshow.css';import './mobile.css';import './security.css';import './album-share.css';import './backup.css';import './confirm-dialog.css';
import {API} from './lib/api';
import {LoginPage} from './pages/LoginPage';
import {AlbumSharePage,SharePage} from './pages/SharePages';
import {VaultPage} from './pages/VaultPage';

function Root(){const[auth,setAuth]=useState<boolean|null>(null);useEffect(()=>{fetch(`${API}/auth/me`).then(response=>setAuth(response.ok)).catch(()=>setAuth(false))},[]);if(auth===null)return <main className="login-page"><Sparkles/></main>;return auth?<VaultPage onLogout={()=>setAuth(false)}/>:<LoginPage onLogin={()=>setAuth(true)}/>}
const albumShareToken=location.pathname.match(/^\/album-share\/([a-z0-9]+)$/)?.[1],shareToken=location.pathname.match(/^\/share\/([a-z0-9]+)$/)?.[1];
createRoot(document.getElementById('root')!).render(albumShareToken?<AlbumSharePage token={albumShareToken}/>:shareToken?<SharePage token={shareToken}/>:<Root/>);
