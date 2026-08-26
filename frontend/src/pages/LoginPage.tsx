import {useState} from 'react';
import {Sparkles} from 'lucide-react';
import {API} from '../lib/api';

export function LoginPage({onLogin}: {onLogin: () => void}) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    const response = await fetch(`${API}/auth/login`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({password}),
    });
    if (response.ok) onLogin();
    else setError('Incorrect vault password');
  }

  return <main className="login-page"><section>
    <div className="brand dark"><Sparkles/>PixelVault</div>
    <p>PRIVATE BY DESIGN</p><h1>Unlock your memories.</h1>
    <span>Your originals, albums and uploads are protected by a server-side session.</span>
    <form onSubmit={submit}><label>Vault password<input autoFocus type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Enter password"/></label>{error && <small>{error}</small>}<button type="submit">Unlock vault</button></form>
    <em>Demo password: demo1234</em>
  </section></main>;
}
